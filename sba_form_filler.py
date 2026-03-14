"""
SBA 7(a) Express Loan Form Auto-Filler — Phase 1 MVP
Fills SBA Form 1919 and Form 413 from a borrower JSON profile.

Usage:
    python3 sba_form_filler.py                        # fill forms with default profile
    python3 sba_form_filler.py --profile custom.json  # use a custom profile
    python3 sba_form_filler.py --inspect              # print all PDF field names (for debugging)
"""

import json
import os
import sys
import argparse
import requests
try:
    from fillpdf import fillpdfs
except Exception:
    fillpdfs = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FORMS_DIR = os.path.join(BASE_DIR, "forms")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

SBA_FORMS = {
    "1919": {
        "filename": "SBA_Form_1919.pdf",
        "url": "https://www.sba.gov/sites/default/files/2025-03/2025.02.27%20Form%201919%20-%20Updates%20%28FINAL%29_03-12-2025%20%281%29.pdf",
    },
    "413": {
        "filename": "SBA_Form_413.pdf",
        "url": "https://www.sba.gov/sites/default/files/2025-02/SBAForm413.pdf",
    },
}

# ---------------------------------------------------------------------------
# Field maps: borrower profile keys → PDF field names
# These were derived by inspecting the official SBA fillable PDFs.
# Run with --inspect to verify or update these for new form versions.
# ---------------------------------------------------------------------------

def build_1919_fields(profile: dict, owner_index: int = 0) -> dict:
    """Map borrower profile to SBA Form 1919 field names (verified against 2025 PDF)."""
    biz = profile["business"]
    owner = profile["owners"][owner_index]
    all_owners = profile["owners"]

    # Entity type checkbox — set the matching field to "Yes"
    entity_type = biz.get("entity_type", "").upper()
    entity_checkboxes = {
        "llc":         "LLC" in entity_type,
        "ccorp":       "C CORP" in entity_type or entity_type == "CORP",
        "scorp":       "S CORP" in entity_type,
        "partnership": "PARTNERSHIP" in entity_type,
        "soleprop":    "SOLE" in entity_type,
    }

    # Loan purpose checkboxes
    purpose = biz.get("loan_purpose", "").lower()
    fields = {
        # Business info
        "applicantname":        biz.get("legal_name", ""),
        "dba":                  biz.get("dba", ""),
        "busTIN":               biz.get("ein", ""),
        "PrimarIndustry":       biz.get("naics_code", ""),
        "busphone":             biz.get("phone", ""),
        "yearbeginoperations":  biz.get("date_established", ""),
        "busAddr":              f"{biz.get('address_street','')} {biz.get('address_city','')} {biz.get('address_state','')} {biz.get('address_zip','')}",
        "existEmp":             biz.get("num_employees", ""),
        "pocName":              f"{owner.get('first_name','')} {owner.get('last_name','')}",
        "pocEmail":             owner.get("email", ""),

        # Entity type checkboxes (SBA PDFs use "On" for checked state)
        "llc":                  "On" if entity_checkboxes["llc"] else "Off",
        "ccorp":                "On" if entity_checkboxes["ccorp"] else "Off",
        "scorp":                "On" if entity_checkboxes["scorp"] else "Off",
        "partnership":          "On" if entity_checkboxes["partnership"] else "Off",
        "soleprop":             "On" if entity_checkboxes["soleprop"] else "Off",

        # Loan purpose — working capital is most common for brokerages
        "workCap":              "On" if "working capital" in purpose else "Off",
        "capitalAmt":           biz.get("loan_amount_requested", "") if "working capital" in purpose else "",

        # Owner table (up to 5 owners; populate from owners list)
        **{f"ownName{i+1}":  f"{o.get('first_name','')} {o.get('last_name','')} " for i, o in enumerate(all_owners[:5])},
        **{f"ownTitle{i+1}": o.get("title", "") for i, o in enumerate(all_owners[:5])},
        **{f"ownPerc{i+1}":  o.get("ownership_pct", "") for i, o in enumerate(all_owners[:5])},
        **{f"ownTin{i+1}":   o.get("ssn", "") for i, o in enumerate(all_owners[:5])},
        **{f"ownHome{i+1}":  f"{o.get('address_street','')} {o.get('address_city','')} {o.get('address_state','')} {o.get('address_zip','')}" for i, o in enumerate(all_owners[:5])},

        # Disclosure questions (q1–q4 are the key eligibility ones)
        # q1 = delinquent federal debt, q2 = prior default, q3 = criminal history, q4 = incarcerated/parole
        "q1Yes": "On" if owner.get("delinquent_federal_debt") else "Off",
        "q1No":  "On" if not owner.get("delinquent_federal_debt") else "Off",
        "q2Yes": "On" if owner.get("prior_default") else "Off",
        "q2No":  "On" if not owner.get("prior_default") else "Off",
        "q3Yes": "On" if owner.get("criminal_history") else "Off",
        "q3No":  "On" if not owner.get("criminal_history") else "Off",
        "q4Yes": "On" if (owner.get("currently_incarcerated") or owner.get("probation_parole")) else "Off",
        "q4No":  "On" if not (owner.get("currently_incarcerated") or owner.get("probation_parole")) else "Off",

        # Signatory
        "repName":  f"{owner.get('first_name','')} {owner.get('last_name','')}",
        "repTitle": owner.get("title", ""),
    }
    return fields


def build_413_fields(profile: dict, owner_index: int = 0) -> dict:
    """Map borrower profile to SBA Form 413 field names (verified against 2025 PDF)."""
    fin = profile["personal_financials"][owner_index]
    owner = profile["owners"][owner_index]
    biz = profile["business"]

    # Compute derived values
    total_assets = (
        float(fin.get("cash_and_savings", 0))
        + float(fin.get("ira_401k", 0))
        + float(fin.get("real_estate_value", 0))
        + float(fin.get("auto_value", 0))
        + float(fin.get("other_assets", 0))
    )
    total_liabilities = (
        float(fin.get("real_estate_mortgage", 0))
        + float(fin.get("auto_loan_balance", 0))
        + float(fin.get("credit_cards_balance", 0))
        + float(fin.get("other_liabilities", 0))
    )
    net_worth = total_assets - total_liabilities

    def fmt(v):
        return f"{float(v):,.0f}"

    # Entity type checkbox
    entity_type = biz.get("entity_type", "").upper()

    return {
        # Section header — loan type checkbox
        "7\\(a\\) loan/04 loan/Surety Bonds": "On",

        # Applicant info
        "Name":                             f"{owner.get('first_name', '')} {owner.get('last_name', '')}",
        "Business Name of Applicant/Borrower": biz.get("legal_name", ""),
        "Home Address":                     owner.get("address_street", ""),
        "City, State, & Zip Code":          f"{owner.get('address_city', '')}, {owner.get('address_state', '')} {owner.get('address_zip', '')}",
        "Business Phone xxx-xxx-xxxx":      biz.get("phone", ""),
        "Home Phone xxx-xxx-xxxx":          owner.get("phone", ""),
        "This information is current as of month/day/year": fin.get("as_of_date", ""),
        "Social Security No":               owner.get("ssn", ""),

        # Entity type checkboxes
        "Business Type: LLC":               "On" if "LLC" in entity_type else "Off",
        "Business Type: Corporation":       "On" if "CORP" in entity_type and "S" not in entity_type else "Off",
        "Business Type: S-Corp":            "On" if "S CORP" in entity_type or "SCORP" in entity_type else "Off",
        "Business Type: Partnership":       "On" if "PARTNERSHIP" in entity_type else "Off",
        "Business Type: Sole Proprietor":   "On" if "SOLE" in entity_type else "Off",

        # Section 1 — Assets
        "Cash on Hand & in banks":          fmt(fin.get("cash_and_savings", 0)),
        "IRA or Other Retirement Account":  fmt(fin.get("ira_401k", 0)),
        "Real Estate":                      fmt(fin.get("real_estate_value", 0)),
        "Automobiles":                      fmt(fin.get("auto_value", 0)),
        "Other Assets":                     fmt(fin.get("other_assets", 0)),
        "TotalAssets":                      fmt(total_assets),

        # Section 2 — Liabilities
        "Mortgages on Real Estate":         fmt(fin.get("real_estate_mortgage", 0)),
        "Installment Account \\(Auto\\)":   fmt(fin.get("auto_loan_balance", 0)),
        "Other Liabilities":                fmt(fin.get("other_liabilities", 0)),
        "TotalLiabilities":                 fmt(total_liabilities),
        "Net Worth":                        fmt(net_worth),

        # Section 3 — Income
        "Salary":                           fmt(fin.get("annual_salary", 0)),
        "Other Income":                     fmt(fin.get("other_income", 0)),
        "Description of Other Income in Section 1: Alimony or child support payments should not be disclosed in Other Income unless it is desired to have such payments counted toward total incomeRow1": fin.get("other_income_source", ""),

        # Real estate detail (Property A = primary residence if applicable)
        "Property AType of Real Estate eg Primary Residence Other Residence Rental Property Land etc": "Primary Residence" if float(fin.get("real_estate_value", 0)) > 0 else "",
        "Property AAddress":                owner.get("address_street", "") if float(fin.get("real_estate_value", 0)) > 0 else "",
        "Property APresent Market Value":   fmt(fin.get("real_estate_value", 0)) if float(fin.get("real_estate_value", 0)) > 0 else "",
        "Property AMortgage Balance":       fmt(fin.get("real_estate_mortgage", 0)) if float(fin.get("real_estate_mortgage", 0)) > 0 else "",

        # Print name for signature line
        "Print Name":                       f"{owner.get('first_name', '')} {owner.get('last_name', '')}",
    }


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def download_form(form_id: str) -> str:
    """Download an SBA form PDF if not already present. Returns local path."""
    info = SBA_FORMS[form_id]
    path = os.path.join(FORMS_DIR, info["filename"])
    if os.path.exists(path):
        print(f"  [✓] Form {form_id} already downloaded: {info['filename']}")
        return path

    print(f"  [↓] Downloading SBA Form {form_id}...")
    r = requests.get(info["url"], timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    print(f"  [✓] Saved to {path}")
    return path


def inspect_fields(pdf_path: str):
    """Print all field names found in a PDF (for mapping/debugging)."""
    fields = fillpdfs.get_form_fields(pdf_path)
    if not fields:
        print("  No fillable fields found in this PDF.")
        return
    print(f"\n  Fields in {os.path.basename(pdf_path)} ({len(fields)} total):\n")
    for name, value in fields.items():
        print(f"    {repr(name)}: {repr(value)}")


def fill_form(template_path: str, output_path: str, field_map: dict):
    """Fill a PDF form and save to output_path."""
    # Get actual fields in the PDF to find best matches
    actual_fields = fillpdfs.get_form_fields(template_path)
    if not actual_fields:
        print(f"  [!] No fillable fields found in {os.path.basename(template_path)}")
        print(f"      This PDF may be flattened. Try downloading a fresh copy.")
        return

    # Match our field map to actual field names (case-insensitive fuzzy match)
    matched = {}
    unmatched = []
    for our_key, value in field_map.items():
        # Try exact match first
        if our_key in actual_fields:
            matched[our_key] = value
            continue
        # Try case-insensitive match
        found = False
        for actual_key in actual_fields:
            if our_key.lower() == actual_key.lower():
                matched[actual_key] = value
                found = True
                break
        if not found:
            unmatched.append(our_key)

    if unmatched:
        print(f"  [!] {len(unmatched)} fields not matched (run --inspect to check field names):")
        for k in unmatched:
            print(f"      - {k}")

    print(f"  [✓] Filling {len(matched)}/{len(field_map)} fields...")
    fillpdfs.write_fillable_pdf(template_path, output_path, matched)
    print(f"  [✓] Saved: {output_path}")


def print_review_prompt(output_files: list):
    """Print a review checklist for the user."""
    print("\n" + "=" * 60)
    print("  REVIEW CHECKLIST — Please verify before signing")
    print("=" * 60)
    print("""
  1. Open each filled PDF listed below
  2. Verify all personal info (name, SSN, DOB, address)
  3. Verify all business info (EIN, entity type, loan amount)
  4. Check Yes/No disclosure answers are correct
  5. Review financial figures on Form 413
  6. Sign and date each form where indicated

  *** DO NOT submit until all information is verified ***
    """)
    print("  Filled PDFs:")
    for f in output_files:
        print(f"    → {f}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SBA 7(a) Express Form Auto-Filler")
    parser.add_argument("--profile", default=os.path.join(BASE_DIR, "borrower_profile.json"),
                        help="Path to borrower JSON profile")
    parser.add_argument("--inspect", action="store_true",
                        help="Print all PDF field names and exit (no filling)")
    parser.add_argument("--owner", type=int, default=0,
                        help="Owner index to fill forms for (0 = first owner)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nSBA Form Auto-Filler — Phase 1 MVP")
    print("-" * 40)

    # Download forms
    print("\n[1] Checking/downloading SBA forms...")
    paths = {}
    for form_id in ["1919", "413"]:
        try:
            paths[form_id] = download_form(form_id)
        except Exception as e:
            print(f"  [!] Could not download Form {form_id}: {e}")
            print(f"      Place the PDF manually in: {FORMS_DIR}/{SBA_FORMS[form_id]['filename']}")

    # Inspect mode
    if args.inspect:
        print("\n[INSPECT MODE] Printing all PDF field names...\n")
        for form_id, path in paths.items():
            print(f"--- SBA Form {form_id} ---")
            inspect_fields(path)
        return

    # Load borrower profile
    print(f"\n[2] Loading borrower profile: {args.profile}")
    with open(args.profile) as f:
        profile = json.load(f)

    num_owners = len(profile.get("owners", []))
    print(f"  Found {num_owners} owner(s). Filling forms for owner index {args.owner}: "
          f"{profile['owners'][args.owner]['first_name']} {profile['owners'][args.owner]['last_name']}")

    # Fill forms
    output_files = []

    if "1919" in paths:
        print(f"\n[3] Filling SBA Form 1919 (Borrower Information)...")
        fields_1919 = build_1919_fields(profile, args.owner)
        out_1919 = os.path.join(OUTPUT_DIR, f"SBA_1919_filled_{profile['owners'][args.owner]['last_name']}.pdf")
        fill_form(paths["1919"], out_1919, fields_1919)
        output_files.append(out_1919)

    if "413" in paths:
        print(f"\n[4] Filling SBA Form 413 (Personal Financial Statement)...")
        fields_413 = build_413_fields(profile, args.owner)
        out_413 = os.path.join(OUTPUT_DIR, f"SBA_413_filled_{profile['owners'][args.owner]['last_name']}.pdf")
        fill_form(paths["413"], out_413, fields_413)
        output_files.append(out_413)

    # Review prompt
    if output_files:
        print_review_prompt(output_files)
        print("  Next step: open PDFs, verify, then sign manually or use an e-signature")
        print("             service (DocuSign, HelloSign) before submitting to your lender.\n")


if __name__ == "__main__":
    main()
