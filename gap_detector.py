"""
Gap Detector — gap_detector.py
Analyzes a borrower profile for missing fields, inconsistencies,
and lender risk flags. Returns a prioritized list of gaps.
"""

import os
try:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
except Exception:
    anthropic = None
    client = None

# ---------------------------------------------------------------------------
# Gap types and severity
# ---------------------------------------------------------------------------

# severity: "blocking" | "warning" | "info"

REQUIRED_BUSINESS_FIELDS = [
    ("legal_name",            "Business legal name"),
    ("ein",                   "Employer Identification Number (EIN)"),
    ("entity_type",           "Entity type (LLC, Corp, etc.)"),
    ("date_established",      "Date business was established"),
    ("state_of_organization", "State of organization"),
    ("address_street",        "Business street address"),
    ("address_city",          "Business city"),
    ("address_state",         "Business state"),
    ("address_zip",           "Business ZIP code"),
    ("phone",                 "Business phone number"),
    ("loan_amount_requested", "Loan amount requested"),
    ("loan_purpose",          "Purpose of the loan"),
]

REQUIRED_OWNER_FIELDS = [
    ("first_name",   "First name"),
    ("last_name",    "Last name"),
    ("title",        "Title / role"),
    ("ownership_pct","Ownership percentage"),
    ("ssn",          "Social Security Number"),
    ("dob",          "Date of birth"),
    ("phone",        "Phone number"),
    ("address_street","Home street address"),
    ("address_city", "Home city"),
    ("address_state","Home state"),
    ("address_zip",  "Home ZIP code"),
]

REQUIRED_FINANCIAL_FIELDS = [
    ("as_of_date",   "As-of date for personal financial statement"),
]

SBA_EXPRESS_MAX = 500_000


def run_rule_gaps(profile: dict, meta: dict) -> list:
    """Run deterministic rule-based gap checks. Returns list of gap dicts."""
    gaps = []
    biz = profile.get("business", {})
    owners = profile.get("owners", [])
    fins = profile.get("personal_financials", [])

    def add(severity, category, field, message, tip=""):
        gaps.append({
            "severity": severity,
            "category": category,
            "field":    field,
            "message":  message,
            "tip":      tip,
        })

    # --- Business required fields ---
    for field_key, label in REQUIRED_BUSINESS_FIELDS:
        if not biz.get(field_key, "").strip():
            add("blocking", "missing_field", f"business.{field_key}",
                f"Missing: {label}", f"Add {label} to complete Form 1919")

    # --- Loan amount cap ---
    try:
        amount = float(biz.get("loan_amount_requested", 0))
        if amount > SBA_EXPRESS_MAX:
            add("warning", "inconsistency", "business.loan_amount_requested",
                f"Loan amount ${amount:,.0f} exceeds SBA 7(a) Express cap of $500,000",
                "Confirm with borrower. Amounts over $500K require standard 7(a) underwriting.")
    except (ValueError, TypeError):
        pass

    # --- Owner checks ---
    if not owners:
        add("blocking", "missing_field", "owners",
            "No owners defined. At least one owner with 20%+ ownership is required.")

    for i, owner in enumerate(owners):
        label_prefix = f"Owner {i+1} ({owner.get('first_name','')} {owner.get('last_name','')})"
        for field_key, label in REQUIRED_OWNER_FIELDS:
            if not str(owner.get(field_key, "")).strip():
                add("blocking", "missing_field", f"owner{i}.{field_key}",
                    f"{label_prefix}: Missing {label}")

    # --- Ownership % sum ---
    try:
        total_pct = sum(float(o.get("ownership_pct", 0)) for o in owners)
        if owners and abs(total_pct - 100) > 1:
            add("warning", "inconsistency", "owners.ownership_pct",
                f"Ownership percentages sum to {total_pct:.0f}% (should be 100%)",
                "Verify ownership split with borrower and adjust.")
    except (ValueError, TypeError):
        pass

    # --- Personal financials ---
    for i, owner in enumerate(owners):
        fin = fins[i] if i < len(fins) else {}
        name = f"{owner.get('first_name','')} {owner.get('last_name','')}".strip()
        if not fin:
            add("blocking", "missing_field", f"fin{i}",
                f"No personal financial data for {name or f'Owner {i+1}'}",
                "Required for Form 413. Ask borrower for assets, liabilities, and income.")
        else:
            for field_key, label in REQUIRED_FINANCIAL_FIELDS:
                if not str(fin.get(field_key, "")).strip():
                    add("blocking", "missing_field", f"fin{i}.{field_key}",
                        f"{name}: Missing {label} on personal financial statement")

    # --- Confidence flags from meta ---
    for field_key, field_data in meta.items():
        if isinstance(field_data, dict) and field_data.get("confidence") == "low":
            conflicts = field_data.get("conflicts", [])
            msg = f"Low-confidence value for {field_key}: '{field_data.get('value','')[:50]}'"
            if conflicts:
                msg += f" ({len(conflicts)} conflicting source(s))"
            add("warning", "low_confidence", field_key, msg,
                f"Source: {field_data.get('source_text','')[:80]}")

    # --- Conflict flags from meta ---
    for field_key, field_data in meta.items():
        if isinstance(field_data, dict) and field_data.get("conflicts"):
            conflict_vals = [c["value"] for c in field_data["conflicts"]]
            add("warning", "conflict", field_key,
                f"Conflicting values for {field_key}: '{field_data['value']}' vs {conflict_vals}",
                "Review source documents and confirm the correct value with the borrower.")

    return gaps


def run_ai_gaps(profile: dict) -> list:
    """
    AI pass to catch soft inconsistencies and lender risk flags
    that rule-based checks miss.
    Returns list of additional gap dicts.
    """
    import json

    profile_summary = json.dumps(profile, indent=2)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        tools=[{
            "name": "flag_issues",
            "description": "Flag logical inconsistencies, lender risk signals, or missing context in this SBA loan application profile",
            "input_schema": {
                "type": "object",
                "required": ["issues"],
                "properties": {
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["severity", "field", "message", "tip"],
                            "properties": {
                                "severity": {"type": "string", "enum": ["blocking", "warning", "info"]},
                                "field":    {"type": "string"},
                                "message":  {"type": "string"},
                                "tip":      {"type": "string"},
                            },
                            "additionalProperties": False,
                        }
                    }
                },
                "additionalProperties": False,
            }
        }],
        tool_choice={"type": "tool", "name": "flag_issues"},
        messages=[{
            "role": "user",
            "content": f"""Review this SBA 7(a) Express loan application profile and flag any issues
that would concern an SBA lender or underwriter. Look for:
- Logical inconsistencies (e.g., entity says LLC but EIN looks like SSN)
- Timeline issues (e.g., business established after most recent tax return year)
- Loan purpose doesn't match business type
- Missing context that a lender would ask about
- Financial red flags (e.g., zero revenue, income way below living expenses)
- Regulatory flags (e.g., delinquent federal debt, criminal history)
- Anything that would slow down or kill the application at the lender

Only flag real issues — don't invent problems. Return empty list if the profile looks clean.

Profile:
{profile_summary}"""
        }]
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "flag_issues":
            return [{"category": "ai_flag", **issue} for issue in block.input.get("issues", [])]
    return []


def detect_gaps(profile: dict, meta: dict, run_ai: bool = True) -> list:
    """
    Full gap detection pass.
    Returns sorted list of gaps: blocking first, then warnings, then info.
    """
    gaps = run_rule_gaps(profile, meta)
    if run_ai and profile:
        try:
            ai_gaps = run_ai_gaps(profile)
            gaps.extend(ai_gaps)
        except Exception as e:
            gaps.append({
                "severity": "info",
                "category": "system",
                "field": "",
                "message": f"AI gap check skipped: {e}",
                "tip": "",
            })

    order = {"blocking": 0, "warning": 1, "info": 2}
    gaps.sort(key=lambda g: order.get(g["severity"], 3))
    return gaps


def readiness_score(profile: dict, meta: dict) -> int:
    """
    Returns 0–100 readiness score.
    100 = all required fields present with medium+ confidence, no blocking gaps.
    """
    gaps = run_rule_gaps(profile, meta)
    blocking = [g for g in gaps if g["severity"] == "blocking"]
    warnings = [g for g in gaps if g["severity"] == "warning"]

    # Count total required fields
    total_required = len(REQUIRED_BUSINESS_FIELDS)
    owners = profile.get("owners", [])
    total_required += len(owners) * len(REQUIRED_OWNER_FIELDS)
    total_required += len(owners)  # one as_of_date per owner

    if total_required == 0:
        return 0

    # Deduct for blocking gaps
    score = 100 - int((len(blocking) / max(total_required, 1)) * 80)
    # Deduct for warnings
    score -= int((len(warnings) / max(total_required, 1)) * 20)

    return max(0, min(100, score))
