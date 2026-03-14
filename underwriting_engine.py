"""
Underwriting Engine — underwriting_engine.py
Scores each SBA 7(a) Express application from 0–1000.
We are a broker, not a lender. This engine pre-qualifies files,
estimates approval probability, and routes to the best-fit lender.
No API key required — rule-based scoring only.
"""

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

BASE_SCORE = 500

# Credit factor (primary guarantor FICO)
CREDIT_SCORES = {
    "740+":   300,
    "720-739": 240,
    "700-719": 180,
    "680-699": 120,
    "660-679":  60,
    "650-659":   0,
    "below_650": -150,
}

# Financial factor (DSCR)
DSCR_SCORES = {
    "above_1.5":  200,
    "1.35-1.5":   160,
    "1.25-1.35":  120,
    "1.15-1.25":   40,
    "1.0-1.15":  -40,
    "below_1.0": -150,
}

# Business age factor
AGE_SCORES = {
    "10+":   150,
    "5-10":  100,
    "3-5":    60,
    "2-3":    20,
    "1-2":   -50,
    "under_1": -120,
}

# Industry factor
INDUSTRY_SCORES = {
    "healthcare":             100,
    "professional_services":   80,
    "manufacturing":           60,
    "wholesale":               60,
    "technology":              60,
    "transportation":          40,
    "other":                   20,
    "retail":                 -20,
    "construction":           -40,
    "restaurant_food_service": -60,
    "gambling_adult":        -200,   # SBA ineligible
}

# Owner experience factor
EXPERIENCE_SCORES = {
    "10+":  50,
    "5-10": 35,
    "3-5":  20,
    "1-3":   5,
    "under_1": -20,
}

# Hard-stop flags — trigger immediate decline before scoring
HARD_STOPS = [
    "delinquent_federal_debt",
    "ineligible_business_type",
    "prohibited_loan_purpose",
    "prior_sba_default",
    "active_bankruptcy",
]

# ---------------------------------------------------------------------------
# Decision tiers
# ---------------------------------------------------------------------------

TIERS = [
    (750, "Auto-Approve",           "green",  "Strong application — clears all criteria. Package and route to matched lender."),
    (600, "Manual Review — Likely Yes",  "blue",   "Solid file with minor gaps. Senior LO review recommended before submission."),
    (500, "Manual Review — Compensate",  "yellow", "Borderline file. Needs offsetting strengths. Credit committee review."),
    (400, "Manual Review — Likely No",   "orange", "Material weaknesses present. Committee review; consider alt product redirect."),
    (0,   "Auto-Decline",           "red",    "Below minimum standards across multiple factors. Decline with reason codes."),
]

# ---------------------------------------------------------------------------
# Lender routing (simplified credit-box matching)
# ---------------------------------------------------------------------------

LENDER_ROUTES = [
    {
        "name": "Newtek Bank",
        "min_score": 700,
        "min_fico_tier": "680-699",
        "notes": "Strong Express lender. Prefers DSCR ≥ 1.25, business age ≥ 2 yrs.",
        "turnaround": "5–7 business days",
    },
    {
        "name": "Live Oak Bank",
        "min_score": 650,
        "min_fico_tier": "660-679",
        "notes": "Industry-specialist lender. Excellent for healthcare, professional services, vet-owned.",
        "turnaround": "7–10 business days",
    },
    {
        "name": "Harvest Small Business Finance",
        "min_score": 550,
        "min_fico_tier": "650-659",
        "notes": "Willing to consider compensating factors. Good for borderline files with strong collateral.",
        "turnaround": "10–14 business days",
    },
    {
        "name": "CDC Small Business Finance",
        "min_score": 400,
        "min_fico_tier": "below_650",
        "notes": "Community lender. Mission-driven. Best for underserved markets and lower scores.",
        "turnaround": "14–21 business days",
    },
]


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def score_application(inputs: dict) -> dict:
    """
    Score an SBA 7(a) Express application.

    inputs dict keys (all optional — missing = worst-case assumption):
        fico_tier       : str  — one of CREDIT_SCORES keys
        dscr_tier       : str  — one of DSCR_SCORES keys
        business_age_tier: str — one of AGE_SCORES keys
        industry        : str  — one of INDUSTRY_SCORES keys
        experience_tier : str  — one of EXPERIENCE_SCORES keys
        hard_stops      : list — list of hard-stop flag strings
        delinquent_federal_debt : bool
        criminal_history        : bool (not auto-decline but penalizes)
        positive_cash_flow      : bool
        collateral_available    : bool
        notes           : str  — free-form context

    Returns dict with:
        score           : int  (0–1000, capped)
        tier            : str
        tier_color      : str
        tier_description: str
        hard_stop       : bool
        hard_stop_reason: str | None
        factor_breakdown: list of dicts
        lender_matches  : list of dicts
        recommendation  : str
    """
    hard_stops_triggered = inputs.get("hard_stops", [])
    if inputs.get("delinquent_federal_debt"):
        hard_stops_triggered.append("delinquent_federal_debt")

    if hard_stops_triggered:
        return {
            "score": 0,
            "tier": "Auto-Decline",
            "tier_color": "red",
            "tier_description": "Hard stop triggered before scoring.",
            "hard_stop": True,
            "hard_stop_reason": f"Hard stop: {', '.join(hard_stops_triggered).replace('_', ' ').title()}",
            "factor_breakdown": [],
            "lender_matches": [],
            "recommendation": "Application cannot proceed. Advise borrower on specific disqualifying factor(s) and explore alternative products.",
        }

    score = BASE_SCORE
    breakdown = []

    # Credit
    fico_tier = inputs.get("fico_tier", "")
    credit_pts = CREDIT_SCORES.get(fico_tier, 0)
    score += credit_pts
    breakdown.append({
        "factor": "Credit (FICO)",
        "tier_label": fico_tier or "Not provided",
        "points": credit_pts,
        "max": 300,
        "weight": "High",
        "note": "Primary guarantor credit score. Strongest single factor.",
    })

    # Financial / DSCR
    dscr_tier = inputs.get("dscr_tier", "")
    dscr_pts = DSCR_SCORES.get(dscr_tier, 0)
    score += dscr_pts
    cash_flow_bonus = 20 if inputs.get("positive_cash_flow") and not dscr_tier else 0
    score += cash_flow_bonus
    breakdown.append({
        "factor": "Financial (DSCR)",
        "tier_label": dscr_tier or "Not provided",
        "points": dscr_pts + cash_flow_bonus,
        "max": 200,
        "weight": "High",
        "note": "Debt Service Coverage Ratio. SBA standard is ≥ 1.25x.",
    })

    # Business age
    age_tier = inputs.get("business_age_tier", "")
    age_pts = AGE_SCORES.get(age_tier, 0)
    score += age_pts
    breakdown.append({
        "factor": "Business Age",
        "tier_label": age_tier.replace("_", " ") if age_tier else "Not provided",
        "points": age_pts,
        "max": 150,
        "weight": "Medium",
        "note": "Older businesses carry lower risk. Under 2 years may require projections.",
    })

    # Industry
    industry = inputs.get("industry", "")
    industry_pts = INDUSTRY_SCORES.get(industry, 0)
    score += industry_pts
    breakdown.append({
        "factor": "Industry",
        "tier_label": industry.replace("_", " ").title() if industry else "Not provided",
        "points": industry_pts,
        "max": 100,
        "weight": "Medium",
        "note": "SBA risk classification by industry. Restaurants and construction score lower.",
    })

    # Owner experience
    exp_tier = inputs.get("experience_tier", "")
    exp_pts = EXPERIENCE_SCORES.get(exp_tier, 0)
    score += exp_pts
    breakdown.append({
        "factor": "Owner Experience",
        "tier_label": exp_tier.replace("_", " ") if exp_tier else "Not provided",
        "points": exp_pts,
        "max": 50,
        "weight": "Low",
        "note": "Management and industry experience. Compensating factor for borderline files.",
    })

    # Collateral compensating factor
    if inputs.get("collateral_available"):
        score += 30
        breakdown.append({
            "factor": "Collateral",
            "tier_label": "Available",
            "points": 30,
            "max": 30,
            "weight": "Compensating",
            "note": "Collateral availability is a positive compensating factor.",
        })

    # Criminal history (not a hard stop but penalizes)
    if inputs.get("criminal_history"):
        score -= 50
        breakdown.append({
            "factor": "Criminal History",
            "tier_label": "Disclosed",
            "points": -50,
            "max": 0,
            "weight": "Penalty",
            "note": "Criminal history disclosed. Not an automatic decline but reduces score and requires explanation.",
        })

    score = max(0, min(1000, score))

    # Determine tier
    tier_name, tier_color, tier_desc = "Auto-Decline", "red", ""
    for threshold, name, color, desc in TIERS:
        if score >= threshold:
            tier_name, tier_color, tier_desc = name, color, desc
            break

    # Lender routing
    lender_matches = [
        l for l in LENDER_ROUTES
        if score >= l["min_score"]
    ]

    # Recommendation text
    if score >= 750:
        rec = "File is strong. Generate the lender package and submit to the top matched lender."
    elif score >= 600:
        rec = "File looks good. Address any open gaps, then submit for senior LO review before packaging."
    elif score >= 500:
        rec = "Borderline file. Identify compensating factors (collateral, experience, strong industry) before committee review."
    elif score >= 400:
        rec = "File has material weaknesses. Consider redirecting to an alternative product (SBA Microloan, CDFI, or conventional line of credit)."
    else:
        rec = "File does not meet minimum standards. Issue a decline with reason codes and discuss alternative financing options with the borrower."

    return {
        "score": score,
        "tier": tier_name,
        "tier_color": tier_color,
        "tier_description": tier_desc,
        "hard_stop": False,
        "hard_stop_reason": None,
        "factor_breakdown": breakdown,
        "lender_matches": lender_matches,
        "recommendation": rec,
    }


def score_from_profile(profile: dict) -> dict:
    """
    Derive underwriting inputs from a borrower profile dict
    and run the scoring engine.
    Used when profile data is available from document extraction.
    """
    owners = profile.get("owners", [])
    fins = profile.get("personal_financials", [{}])
    biz = profile.get("business", {})
    fin = fins[0] if fins else {}

    inputs = {}

    # Hard stops from profile flags
    hard_stops = []
    for owner in owners:
        if owner.get("delinquent_federal_debt"):
            hard_stops.append("delinquent_federal_debt")
    inputs["hard_stops"] = hard_stops

    inputs["criminal_history"] = any(o.get("criminal_history") for o in owners)

    # Business age
    established = biz.get("date_established", "")
    if established:
        try:
            from datetime import datetime
            est_year = int(established.split("/")[-1]) if "/" in established else int(established[:4])
            age_years = datetime.now().year - est_year
            if age_years >= 10:
                inputs["business_age_tier"] = "10+"
            elif age_years >= 5:
                inputs["business_age_tier"] = "5-10"
            elif age_years >= 3:
                inputs["business_age_tier"] = "3-5"
            elif age_years >= 2:
                inputs["business_age_tier"] = "2-3"
            elif age_years >= 1:
                inputs["business_age_tier"] = "1-2"
            else:
                inputs["business_age_tier"] = "under_1"
        except Exception:
            pass

    # Positive cash flow from personal financials
    try:
        salary = float(fin.get("annual_salary", 0) or 0)
        inputs["positive_cash_flow"] = salary > 0
    except Exception:
        pass

    return score_application(inputs)
