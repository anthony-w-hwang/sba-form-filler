"""
SBA 7(a) Express Loan Application — Web Intake UI
Run with: streamlit run app.py
"""

import json
import os
import io
import zipfile
import streamlit as st
from sba_form_filler import (
    download_form,
    build_1919_fields,
    build_413_fields,
    fill_form,
    SBA_FORMS,
    FORMS_DIR,
    OUTPUT_DIR,
)

st.set_page_config(
    page_title="SBA 7(a) Express Loan Application",
    page_icon="🏦",
    layout="centered",
)

STEPS = [
    "Business Information",
    "Owners",
    "Personal Financials",
    "Review & Generate",
]

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "step": 0,
        "business": {},
        "owners": [{}],
        "personal_financials": [{}],
        "output_files": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def progress_bar():
    step = st.session_state.step
    cols = st.columns(len(STEPS))
    for i, (col, label) in enumerate(zip(cols, STEPS)):
        if i < step:
            col.markdown(f"<div style='text-align:center;color:#4CAF50;font-size:12px'>✓ {label}</div>", unsafe_allow_html=True)
        elif i == step:
            col.markdown(f"<div style='text-align:center;color:#1f77b4;font-weight:bold;font-size:12px'>● {label}</div>", unsafe_allow_html=True)
        else:
            col.markdown(f"<div style='text-align:center;color:#aaa;font-size:12px'>○ {label}</div>", unsafe_allow_html=True)
    st.markdown("---")


def nav_buttons(back=True, next_label="Next →", next_disabled=False):
    col1, col2 = st.columns([1, 1])
    go_back = False
    go_next = False
    if back:
        with col1:
            go_back = st.button("← Back", use_container_width=True)
    with col2:
        go_next = st.button(next_label, use_container_width=True, disabled=next_disabled, type="primary")
    return go_back, go_next


# ---------------------------------------------------------------------------
# Step 0 — Business Information
# ---------------------------------------------------------------------------

def step_business():
    st.header("Business Information")
    b = st.session_state.business

    col1, col2 = st.columns(2)
    with col1:
        b["legal_name"]          = st.text_input("Legal Business Name *", value=b.get("legal_name", ""))
        b["ein"]                 = st.text_input("EIN (xx-xxxxxxx) *", value=b.get("ein", ""))
        b["date_established"]    = st.text_input("Date Established (MM/DD/YYYY) *", value=b.get("date_established", ""))
        b["state_of_organization"] = st.text_input("State of Organization *", value=b.get("state_of_organization", ""))
        b["naics_code"]          = st.text_input("NAICS Code", value=b.get("naics_code", ""))
    with col2:
        b["dba"]                 = st.text_input("DBA (if any)", value=b.get("dba", ""))
        b["phone"]               = st.text_input("Business Phone *", value=b.get("phone", ""))
        b["email"]               = st.text_input("Business Email", value=b.get("email", ""))
        b["entity_type"]         = st.selectbox("Entity Type *",
                                      ["LLC", "S Corp", "C Corp", "Partnership", "Sole Proprietor"],
                                      index=["LLC", "S Corp", "C Corp", "Partnership", "Sole Proprietor"].index(b.get("entity_type", "LLC")))
        b["num_employees"]       = st.text_input("Current Employees", value=b.get("num_employees", ""))

    st.subheader("Business Address")
    col1, col2 = st.columns(2)
    with col1:
        b["address_street"]      = st.text_input("Street Address *", value=b.get("address_street", ""))
        b["address_city"]        = st.text_input("City *", value=b.get("address_city", ""))
    with col2:
        b["address_state"]       = st.text_input("State *", value=b.get("address_state", ""))
        b["address_zip"]         = st.text_input("ZIP Code *", value=b.get("address_zip", ""))

    st.subheader("Loan Request")
    col1, col2 = st.columns(2)
    with col1:
        b["loan_amount_requested"] = st.text_input("Loan Amount ($) *", value=b.get("loan_amount_requested", ""))
    with col2:
        b["loan_purpose"]        = st.text_input("Purpose of Loan *", value=b.get("loan_purpose", "Working capital and business expansion"))

    st.session_state.business = b

    required = [b.get("legal_name"), b.get("ein"), b.get("date_established"),
                b.get("state_of_organization"), b.get("phone"),
                b.get("address_street"), b.get("address_city"),
                b.get("address_state"), b.get("address_zip"),
                b.get("loan_amount_requested"), b.get("loan_purpose")]
    ready = all(required)

    _, go_next = nav_buttons(back=False, next_disabled=not ready)
    if not ready:
        st.caption("* Required fields must be filled to continue.")
    if go_next:
        st.session_state.step = 1
        st.rerun()


# ---------------------------------------------------------------------------
# Step 1 — Owners
# ---------------------------------------------------------------------------

def step_owners():
    st.header("Owners & Principals")
    st.caption("Add all owners with 20%+ ownership. Each will need to sign Form 1919.")

    owners = st.session_state.owners

    # Add / remove owner buttons
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("+ Add Owner", use_container_width=True):
            owners.append({})
            st.rerun()

    for i, owner in enumerate(owners):
        with st.expander(f"Owner {i+1}: {owner.get('first_name','')} {owner.get('last_name','')}".strip() or f"Owner {i+1}", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                owner["first_name"]   = st.text_input("First Name *", value=owner.get("first_name", ""), key=f"fn_{i}")
            with col2:
                owner["last_name"]    = st.text_input("Last Name *", value=owner.get("last_name", ""), key=f"ln_{i}")
            with col3:
                owner["title"]        = st.text_input("Title *", value=owner.get("title", ""), key=f"title_{i}")

            col1, col2, col3 = st.columns(3)
            with col1:
                owner["ownership_pct"] = st.text_input("Ownership % *", value=owner.get("ownership_pct", ""), key=f"pct_{i}")
            with col2:
                owner["ssn"]          = st.text_input("SSN (xxx-xx-xxxx) *", value=owner.get("ssn", ""), key=f"ssn_{i}")
            with col3:
                owner["dob"]          = st.text_input("Date of Birth (MM/DD/YYYY) *", value=owner.get("dob", ""), key=f"dob_{i}")

            col1, col2 = st.columns(2)
            with col1:
                owner["phone"]        = st.text_input("Phone *", value=owner.get("phone", ""), key=f"ph_{i}")
            with col2:
                owner["email"]        = st.text_input("Email", value=owner.get("email", ""), key=f"em_{i}")

            st.markdown("**Home Address**")
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                owner["address_street"] = st.text_input("Street", value=owner.get("address_street", ""), key=f"str_{i}")
            with col2:
                owner["address_city"]   = st.text_input("City", value=owner.get("address_city", ""), key=f"cty_{i}")
            with col3:
                owner["address_state"]  = st.text_input("State", value=owner.get("address_state", ""), key=f"st_{i}")
            with col4:
                owner["address_zip"]    = st.text_input("ZIP", value=owner.get("address_zip", ""), key=f"zip_{i}")

            st.markdown("**Disclosure Questions**")
            col1, col2 = st.columns(2)
            with col1:
                owner["us_citizen"]             = st.checkbox("U.S. Citizen or Lawful Resident", value=owner.get("us_citizen", True), key=f"cit_{i}")
                owner["criminal_history"]        = st.checkbox("Criminal history (any felony conviction)", value=owner.get("criminal_history", False), key=f"crim_{i}")
                owner["currently_incarcerated"]  = st.checkbox("Currently incarcerated", value=owner.get("currently_incarcerated", False), key=f"inc_{i}")
            with col2:
                owner["probation_parole"]        = st.checkbox("On probation or parole", value=owner.get("probation_parole", False), key=f"prob_{i}")
                owner["prior_sba_loan"]          = st.checkbox("Prior SBA loan", value=owner.get("prior_sba_loan", False), key=f"sba_{i}")
                owner["prior_default"]           = st.checkbox("Prior SBA loan default", value=owner.get("prior_default", False), key=f"def_{i}")
                owner["delinquent_federal_debt"] = st.checkbox("Delinquent on federal debt", value=owner.get("delinquent_federal_debt", False), key=f"fed_{i}")

            if len(owners) > 1:
                if st.button(f"Remove Owner {i+1}", key=f"rm_{i}"):
                    owners.pop(i)
                    if len(st.session_state.personal_financials) > len(owners):
                        st.session_state.personal_financials.pop(i)
                    st.rerun()

    st.session_state.owners = owners

    # Ensure personal_financials list is same length as owners
    while len(st.session_state.personal_financials) < len(owners):
        st.session_state.personal_financials.append({})

    all_required = all(
        o.get("first_name") and o.get("last_name") and o.get("title") and
        o.get("ownership_pct") and o.get("ssn") and o.get("dob") and o.get("phone")
        for o in owners
    )

    go_back, go_next = nav_buttons(next_disabled=not all_required)
    if not all_required:
        st.caption("* Required fields must be filled for all owners to continue.")
    if go_back:
        st.session_state.step = 0
        st.rerun()
    if go_next:
        st.session_state.step = 2
        st.rerun()


# ---------------------------------------------------------------------------
# Step 2 — Personal Financials
# ---------------------------------------------------------------------------

def step_financials():
    st.header("Personal Financial Statements")
    st.caption("Required for each owner with 20%+ ownership (SBA Form 413).")

    owners = st.session_state.owners
    fins = st.session_state.personal_financials

    for i, owner in enumerate(owners):
        name = f"{owner.get('first_name','')} {owner.get('last_name','')}".strip()
        fin = fins[i]

        with st.expander(f"Financials for {name}", expanded=True):
            fin["as_of_date"] = st.text_input("As of Date (MM/DD/YYYY) *",
                                               value=fin.get("as_of_date", ""),
                                               key=f"aod_{i}")

            st.markdown("**Assets**")
            col1, col2, col3 = st.columns(3)
            with col1:
                fin["cash_and_savings"] = st.text_input("Cash & Savings ($)", value=fin.get("cash_and_savings", "0"), key=f"cash_{i}")
                fin["ira_401k"]         = st.text_input("IRA / 401k ($)", value=fin.get("ira_401k", "0"), key=f"ira_{i}")
            with col2:
                fin["real_estate_value"] = st.text_input("Real Estate Value ($)", value=fin.get("real_estate_value", "0"), key=f"rev_{i}")
                fin["auto_value"]        = st.text_input("Vehicle Value ($)", value=fin.get("auto_value", "0"), key=f"av_{i}")
            with col3:
                fin["other_assets"]      = st.text_input("Other Assets ($)", value=fin.get("other_assets", "0"), key=f"oa_{i}")

            st.markdown("**Liabilities**")
            col1, col2, col3 = st.columns(3)
            with col1:
                fin["real_estate_mortgage"] = st.text_input("Mortgage Balance ($)", value=fin.get("real_estate_mortgage", "0"), key=f"mort_{i}")
            with col2:
                fin["auto_loan_balance"]    = st.text_input("Auto Loan Balance ($)", value=fin.get("auto_loan_balance", "0"), key=f"alb_{i}")
            with col3:
                fin["credit_cards_balance"] = st.text_input("Credit Card Balance ($)", value=fin.get("credit_cards_balance", "0"), key=f"cc_{i}")

            st.markdown("**Income**")
            col1, col2, col3 = st.columns(3)
            with col1:
                fin["annual_salary"]    = st.text_input("Annual Salary ($)", value=fin.get("annual_salary", "0"), key=f"sal_{i}")
            with col2:
                fin["other_income"]     = st.text_input("Other Annual Income ($)", value=fin.get("other_income", "0"), key=f"oi_{i}")
            with col3:
                fin["other_income_source"] = st.text_input("Source of Other Income", value=fin.get("other_income_source", ""), key=f"ois_{i}")

            # Live net worth preview
            try:
                total_assets = sum(float(fin.get(k, 0) or 0) for k in
                    ["cash_and_savings", "ira_401k", "real_estate_value", "auto_value", "other_assets"])
                total_liabilities = sum(float(fin.get(k, 0) or 0) for k in
                    ["real_estate_mortgage", "auto_loan_balance", "credit_cards_balance"])
                net_worth = total_assets - total_liabilities
                st.info(f"**Estimated Net Worth:** ${net_worth:,.0f}  |  Assets: ${total_assets:,.0f}  |  Liabilities: ${total_liabilities:,.0f}")
            except ValueError:
                pass

    st.session_state.personal_financials = fins

    all_ready = all(f.get("as_of_date") for f in fins)

    go_back, go_next = nav_buttons(next_label="Review & Generate →", next_disabled=not all_ready)
    if not all_ready:
        st.caption("* As of Date is required for all owners.")
    if go_back:
        st.session_state.step = 1
        st.rerun()
    if go_next:
        st.session_state.step = 3
        st.rerun()


# ---------------------------------------------------------------------------
# Step 3 — Review & Generate
# ---------------------------------------------------------------------------

def step_review():
    st.header("Review & Generate Forms")

    profile = {
        "business": st.session_state.business,
        "owners": st.session_state.owners,
        "personal_financials": st.session_state.personal_financials,
    }

    # Summary card
    biz = profile["business"]
    st.subheader("Business")
    col1, col2, col3 = st.columns(3)
    col1.metric("Legal Name", biz.get("legal_name", "—"))
    col2.metric("Loan Amount", f"${float(biz.get('loan_amount_requested', 0)):,.0f}")
    col3.metric("Entity Type", biz.get("entity_type", "—"))

    st.subheader("Owners")
    for o in profile["owners"]:
        st.write(f"• **{o.get('first_name','')} {o.get('last_name','')}** — {o.get('title','')} ({o.get('ownership_pct','')}%)")

    st.subheader("Personal Financials")
    for i, (o, f) in enumerate(zip(profile["owners"], profile["personal_financials"])):
        name = f"{o.get('first_name','')} {o.get('last_name','')}".strip()
        try:
            total_assets = sum(float(f.get(k, 0) or 0) for k in
                ["cash_and_savings", "ira_401k", "real_estate_value", "auto_value", "other_assets"])
            total_liabilities = sum(float(f.get(k, 0) or 0) for k in
                ["real_estate_mortgage", "auto_loan_balance", "credit_cards_balance"])
            net_worth = total_assets - total_liabilities
            st.write(f"• **{name}** — Net Worth: ${net_worth:,.0f}")
        except ValueError:
            st.write(f"• **{name}** — (check financial inputs)")

    st.markdown("---")
    st.warning("**Please review all information above before generating.** The filled PDFs will contain sensitive personal data (SSN, financials). You must sign each form before submitting to a lender.")

    col1, col2 = st.columns(2)
    with col1:
        go_back = st.button("← Edit", use_container_width=True)
    with col2:
        generate = st.button("Generate Forms", use_container_width=True, type="primary")

    if go_back:
        st.session_state.step = 2
        st.rerun()

    if generate:
        with st.spinner("Downloading SBA forms and filling fields..."):
            os.makedirs(FORMS_DIR, exist_ok=True)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # Download forms if needed
            paths = {}
            for form_id in ["1919", "413"]:
                try:
                    paths[form_id] = download_form(form_id)
                except Exception as e:
                    st.error(f"Could not download Form {form_id}: {e}")
                    return

            # Save profile to disk (useful for reuse / debugging)
            profile_path = os.path.join(OUTPUT_DIR, "borrower_profile_last.json")
            with open(profile_path, "w") as f:
                json.dump(profile, f, indent=2)

            output_files = []
            errors = []

            for i, owner in enumerate(profile["owners"]):
                last = owner.get("last_name", f"owner{i}")

                if "1919" in paths:
                    out = os.path.join(OUTPUT_DIR, f"SBA_1919_filled_{last}.pdf")
                    try:
                        fill_form(paths["1919"], out, build_1919_fields(profile, i))
                        output_files.append(("1919", last, out))
                    except Exception as e:
                        errors.append(f"Form 1919 for {last}: {e}")

                if "413" in paths:
                    out = os.path.join(OUTPUT_DIR, f"SBA_413_filled_{last}.pdf")
                    try:
                        fill_form(paths["413"], out, build_413_fields(profile, i))
                        output_files.append(("413", last, out))
                    except Exception as e:
                        errors.append(f"Form 413 for {last}: {e}")

        if errors:
            for err in errors:
                st.error(err)

        if output_files:
            st.success(f"Generated {len(output_files)} form(s) successfully!")

            # Build ZIP for download
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for form_id, last, path in output_files:
                    zf.write(path, os.path.basename(path))
            zip_buffer.seek(0)

            st.download_button(
                label="⬇ Download All Forms (ZIP)",
                data=zip_buffer,
                file_name=f"SBA_Forms_{biz.get('legal_name','').replace(' ','_')}.zip",
                mime="application/zip",
                use_container_width=True,
            )

            st.markdown("---")
            st.subheader("Review Checklist")
            st.markdown("""
Before signing and submitting to your lender:

- [ ] Verify legal business name, EIN, and address
- [ ] Confirm loan amount and stated purpose
- [ ] Check all owner names, SSNs, and ownership percentages
- [ ] Review Yes/No disclosure answers on Form 1919
- [ ] Verify asset, liability, and income figures on Form 413
- [ ] Sign and date each form where indicated
- [ ] Attach supporting documents (tax returns, P&L, balance sheet)

**Do not submit unsigned forms to a lender.**
            """)

            col1, col2 = st.columns(2)
            with col1:
                st.info("**Next:** Open the ZIP, review each PDF, and sign manually or via e-signature (DocuSign / HelloSign).")
            with col2:
                if st.button("Start Over", use_container_width=True):
                    for k in ["step", "business", "owners", "personal_financials", "output_files"]:
                        del st.session_state[k]
                    st.rerun()


# ---------------------------------------------------------------------------
# App shell
# ---------------------------------------------------------------------------

st.title("SBA 7(a) Express Loan Application")
st.caption("Auto-fills SBA Form 1919 (Borrower Information) and Form 413 (Personal Financial Statement)")

progress_bar()

step = st.session_state.step
if step == 0:
    step_business()
elif step == 1:
    step_owners()
elif step == 2:
    step_financials()
elif step == 3:
    step_review()
