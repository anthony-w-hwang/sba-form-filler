"""
Underwriting Engine — underwriting_engine.py
Scores each SBA 7(a) Express application from 0–1000.
We are a broker, not a lender. This engine pre-qualifies files,
estimates approval probability, and routes to the best-fit lender.
Based on SBA SOP 50 10 8 (effective June 1, 2025).
No API key required — rule-based scoring only.
"""

# ---------------------------------------------------------------------------
# Scoring constants  (Base = 500, total adjustable = ±800+, capped 0–1000)
# ---------------------------------------------------------------------------

BASE_SCORE = 500

# ── Credit: Personal FICO  (±200 pts) ──────────────────────────────────────
FICO_SCORES = {
    "760+":    200,
    "740-759": 170,
    "720-739": 140,
    "700-719": 100,
    "680-699":  60,
    "660-679":  20,
    "650-659":   0,
    "below_650": -150,
}

# ── Credit: FICO SBSS (SBA Small Business Scoring Service, 0–300) (±100 pts)
# SBA mandate: ≥165 for expedited path. Most PLP lenders require 180+.
SBSS_SCORES = {
    "above_220":  100,
    "200-220":     75,
    "180-199":     50,
    "165-179":     20,
    "below_165":  -100,  # Below SBA minimum — requires full manual underwrite
}

# ── Credit: Business Credit / D&B Paydex  (0–100, compensating factor) ────
PAYDEX_SCORES = {
    "80+":    30,
    "70-79":  15,
    "50-69":   0,
    "below_50": -20,
}

# ── Financial: Entity-level DSCR  (±100 pts) ───────────────────────────────
DSCR_ENTITY_SCORES = {
    "above_1.5":   100,
    "1.35-1.5":     80,
    "1.25-1.35":    60,
    "1.15-1.25":    20,
    "1.0-1.15":   -40,
    "below_1.0":  -100,
}

# ── Financial: Global Cash Flow DSCR  (±100 pts) ───────────────────────────
# Consolidates all income sources and obligations across borrower universe.
# SBA SOP 50 10 8 minimum: 1.10x. PLP lenders typically require 1.25x+.
DSCR_GLOBAL_SCORES = {
    "above_1.5":   100,
    "1.35-1.5":     80,
    "1.25-1.35":    60,
    "1.10-1.25":    20,
    "1.0-1.10":   -40,
    "below_1.0":  -100,
}

# ── Financial: Debt-to-Tangible Net Worth (Leverage)  (±50 pts) ────────────
# Formula: Total Liabilities ÷ (Equity − Intangibles). High leverage = risk.
LEVERAGE_SCORES = {
    "below_1":    50,
    "1-2":        35,
    "2-3":        15,
    "3-4":         0,
    "4-5":       -25,
    "above_5":   -50,
}

# ── Financial: Working Capital / Current Ratio  (±40 pts) ──────────────────
# Formula: Current Assets ÷ Current Liabilities. Below 1.0 = can't cover ST obligations.
CURRENT_RATIO_SCORES = {
    "above_2":    40,
    "1.5-2":      25,
    "1.25-1.5":   15,
    "1.0-1.25":    5,
    "below_1":   -40,
}

# ── Financial: Revenue Trend  (±50 pts) ────────────────────────────────────
REVENUE_TREND_SCORES = {
    "strong_growth":    50,   # >15% YoY growth
    "moderate_growth":  25,   # 5-15% YoY
    "flat":              0,   # <5% change
    "slight_decline":  -25,   # 5-15% decline
    "significant_decline": -50, # >15% decline
}

# ── Business Age  (±150 pts) ───────────────────────────────────────────────
AGE_SCORES = {
    "10+":     150,
    "5-10":    100,
    "3-5":      60,
    "2-3":      20,
    "1-2":     -50,
    "under_1": -120,
}

# ── Industry Risk  (±100 pts) ──────────────────────────────────────────────
INDUSTRY_SCORES = {
    "healthcare":              100,
    "professional_services":    80,
    "technology":               70,
    "manufacturing":            60,
    "wholesale":                60,
    "education":                50,
    "transportation":           40,
    "other":                    20,
    "retail":                  -20,
    "construction":            -40,
    "restaurant_food_service": -60,
    "gambling_adult":          -200,
}

# ── Owner Experience  (±50 pts) ─────────────────────────────────────────────
EXPERIENCE_SCORES = {
    "10+":     50,
    "5-10":    35,
    "3-5":     20,
    "1-3":      5,
    "under_1": -20,
}

# ── Personal Net Worth & Liquidity  (±50 pts) ──────────────────────────────
NET_WORTH_SCORES = {
    "strong_positive":  50,   # Net worth > 2x loan amount
    "moderate_positive": 25,  # Net worth > loan amount
    "slight_positive":    5,  # Positive but less than loan amount
    "near_zero":        -15,  # < $25K positive
    "negative":         -50,  # Guarantor net worth is negative
}

# ── Revenue Concentration Risk  (penalty, 0 to -75) ─────────────────────────
CONCENTRATION_PENALTIES = {
    "none":               0,   # No single customer >15%
    "moderate":         -25,   # One customer 15-30%
    "significant":      -50,   # One customer 30-50%
    "highly_concentrated": -75, # One customer >50%
}

# ---------------------------------------------------------------------------
# Hard stops — trigger immediate decline before scoring
# ---------------------------------------------------------------------------

HARD_STOP_DESCRIPTIONS = {
    "delinquent_federal_debt":        "Delinquent Federal Debt — current unpaid federal debt (IRS, student loans, prior SBA, etc.)",
    "federal_debarment":              "Federal Debarment/Suspension — principal or business is currently debarred or suspended from federal programs",
    "active_bankruptcy":              "Active Bankruptcy — open bankruptcy proceeding for business or any principal",
    "prior_sba_default_with_loss":    "Prior SBA Default with Loss — previous SBA loan that resulted in a federal guaranty loss (unless formally waived)",
    "currently_incarcerated_probation": "Incarcerated / On Probation or Parole — principal is currently incarcerated, on probation, or on parole",
    "pending_felony_indictment":      "Pending Felony Indictment — outstanding indictment against a principal (even without conviction)",
    "illegal_business_activity":      "Illegal Business Activity — any portion of operations is illegal under federal, state, or local law",
    "ineligible_business_type":       "Ineligible Business Type — business falls under 13 CFR § 120.110 ineligibility (nonprofit, passive investment, lender, gambling >1/3 revenue, etc.)",
    "citizenship_failure":            "Citizenship/Residency Failure — less than 95% of ownership held by U.S. citizens, nationals, or LPRs (SOP 50 10 8 requirement effective Jan 1, 2026)",
    "sba_express_cap_exceeded":       "SBA Express Cap Exceeded — outstanding SBA Express guaranteed balance plus this loan would exceed $500K",
}

# ---------------------------------------------------------------------------
# Decision tiers
# ---------------------------------------------------------------------------

TIERS = [
    (750, "Auto-Approve",                "green",  "Strong application — clears all criteria. Package and route to matched lender."),
    (600, "Manual Review — Likely Yes",  "blue",   "Solid file with minor gaps or borderline factors. Senior LO review before submission."),
    (500, "Manual Review — Compensate",  "yellow", "Borderline file. Needs offsetting strengths. Credit committee review required."),
    (400, "Manual Review — Likely No",   "orange", "Material weaknesses present. Committee review; likely redirect to alt product."),
    (0,   "Auto-Decline",                "red",    "Below minimum standards across multiple factors. Decline with reason codes."),
]

# ---------------------------------------------------------------------------
# Lender routing
# ---------------------------------------------------------------------------

LENDER_ROUTES = [
    {
        "name": "Live Oak Bank",
        "min_score": 700,
        "min_sbss": 180,
        "notes": "Top PLP Express lender. Specializes in healthcare, professional services, and veteran-owned businesses. Strong on DSCR ≥ 1.25x.",
        "turnaround": "5–7 business days",
    },
    {
        "name": "Newtek Bank",
        "min_score": 650,
        "min_sbss": 165,
        "notes": "High-volume Express lender. Accepts broader industries. Good for solid files needing fast processing.",
        "turnaround": "5–10 business days",
    },
    {
        "name": "Harvest Small Business Finance",
        "min_score": 550,
        "min_sbss": 165,
        "notes": "Willing to consider compensating factors. Good for borderline files with strong collateral or management experience.",
        "turnaround": "10–14 business days",
    },
    {
        "name": "CDC Small Business Finance",
        "min_score": 400,
        "min_sbss": 0,
        "notes": "Community development lender. Mission-driven. Best for underserved markets, lower scores, and community-impact businesses.",
        "turnaround": "14–21 business days",
    },
]


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def score_application(inputs: dict) -> dict:
    """
    Score an SBA 7(a) Express application per SOP 50 10 8 framework.

    inputs dict keys:
        # HARD STOPS
        hard_stops              : list  — explicit hard stop flags
        delinquent_federal_debt : bool
        federal_debarment       : bool
        active_bankruptcy       : bool
        prior_sba_default       : bool
        currently_incarcerated  : bool
        pending_indictment      : bool
        illegal_business        : bool
        ineligible_business_type: bool
        citizenship_failure     : bool
        sba_cap_exceeded        : bool

        # CREDIT
        fico_tier               : str  — key from FICO_SCORES
        sbss_tier               : str  — key from SBSS_SCORES
        paydex_tier             : str  — key from PAYDEX_SCORES
        open_collections        : bool
        tax_liens               : bool
        bankruptcy_discharged   : bool
        years_since_bankruptcy  : int
        criminal_history        : bool
        criminal_on_probation   : bool  (hard stop if True)

        # FINANCIAL
        dscr_entity_tier        : str  — key from DSCR_ENTITY_SCORES
        dscr_global_tier        : str  — key from DSCR_GLOBAL_SCORES
        leverage_tier           : str  — key from LEVERAGE_SCORES
        current_ratio_tier      : str  — key from CURRENT_RATIO_SCORES
        revenue_trend           : str  — key from REVENUE_TREND_SCORES
        revenue_concentration   : str  — key from CONCENTRATION_PENALTIES
        positive_cash_flow      : bool

        # BUSINESS
        business_age_tier       : str  — key from AGE_SCORES
        industry                : str  — key from INDUSTRY_SCORES
        is_startup              : bool  (< 2 years, triggers equity injection check)
        is_franchise            : bool
        franchise_on_sba_directory: bool
        existing_sba_balance    : float
        annual_revenue          : float

        # OWNER / GUARANTOR
        experience_tier         : str  — key from EXPERIENCE_SCORES
        net_worth_tier          : str  — key from NET_WORTH_SCORES
        equity_injection_available: bool  (required for startups/acquisitions)
        citizenship_status      : str  — "citizen", "lpr", "other"
        key_person_risk         : bool  (single owner, business depends on them)

        # LOAN STRUCTURE
        collateral_available    : bool
        collateral_type         : str  — "real_estate", "equipment", "other", "none"
        use_of_proceeds_eligible: bool
        loan_purpose            : str  — "working_capital", "equipment", "real_estate", "acquisition", "refinance", "other"
    """

    # ── Collect hard stops ─────────────────────────────────────────────────
    triggered = list(inputs.get("hard_stops", []))
    if inputs.get("delinquent_federal_debt"):
        triggered.append("delinquent_federal_debt")
    if inputs.get("federal_debarment"):
        triggered.append("federal_debarment")
    if inputs.get("active_bankruptcy"):
        triggered.append("active_bankruptcy")
    if inputs.get("prior_sba_default"):
        triggered.append("prior_sba_default_with_loss")
    if inputs.get("currently_incarcerated"):
        triggered.append("currently_incarcerated_probation")
    if inputs.get("pending_indictment"):
        triggered.append("pending_felony_indictment")
    if inputs.get("illegal_business"):
        triggered.append("illegal_business_activity")
    if inputs.get("ineligible_business_type"):
        triggered.append("ineligible_business_type")
    if inputs.get("citizenship_failure"):
        triggered.append("citizenship_failure")
    if inputs.get("sba_cap_exceeded"):
        triggered.append("sba_express_cap_exceeded")

    if triggered:
        reasons = [HARD_STOP_DESCRIPTIONS.get(t, t.replace("_", " ").title()) for t in triggered]
        return {
            "score": 0,
            "tier": "Auto-Decline",
            "tier_color": "red",
            "tier_description": "Hard stop triggered — application is ineligible before scoring.",
            "hard_stop": True,
            "hard_stop_reasons": reasons,
            "hard_stop_reason": reasons[0],
            "factor_breakdown": [],
            "flags": [],
            "lender_matches": [],
            "recommendation": "Application cannot proceed. Advise borrower on the specific disqualifying factor(s) listed below and explore alternative products.",
        }

    score = BASE_SCORE
    breakdown = []
    flags = []   # advisory warnings that don't stop the app but need attention

    # ── Credit: Personal FICO ──────────────────────────────────────────────
    fico_tier = inputs.get("fico_tier", "")
    fico_pts = FICO_SCORES.get(fico_tier, 0)
    score += fico_pts
    breakdown.append({
        "factor":      "Personal FICO",
        "category":    "Credit",
        "tier_label":  fico_tier or "Not provided",
        "points":      fico_pts,
        "max":         200,
        "weight":      "High",
        "note":        "Primary guarantor personal credit score. Single strongest predictor of repayment.",
    })

    # ── Credit: FICO SBSS ─────────────────────────────────────────────────
    sbss_tier = inputs.get("sbss_tier", "")
    sbss_pts = SBSS_SCORES.get(sbss_tier, 0)
    score += sbss_pts
    if sbss_tier == "below_165":
        flags.append("SBSS below SBA minimum (165) — application requires full manual underwriting; no expedited processing path available.")
    breakdown.append({
        "factor":      "FICO SBSS",
        "category":    "Credit",
        "tier_label":  sbss_tier or "Not provided",
        "points":      sbss_pts,
        "max":         100,
        "weight":      "High",
        "note":        "SBA Small Business Scoring Service. SBA minimum: 165. Most PLP lenders require 180+. Combines personal credit, business bureau data, and business financials.",
    })

    # ── Credit: Business Credit / D&B Paydex ─────────────────────────────
    paydex_tier = inputs.get("paydex_tier", "")
    paydex_pts = PAYDEX_SCORES.get(paydex_tier, 0)
    score += paydex_pts
    if paydex_pts != 0 or paydex_tier:
        breakdown.append({
            "factor":      "Business Credit (D&B Paydex)",
            "category":    "Credit",
            "tier_label":  paydex_tier or "Not provided",
            "points":      paydex_pts,
            "max":         30,
            "weight":      "Compensating",
            "note":        "Business payment history with vendors/suppliers. 80+ = pays on time. Separate from personal credit.",
        })

    # ── Credit: Derogatory flags ───────────────────────────────────────────
    if inputs.get("open_collections"):
        score -= 30
        breakdown.append({
            "factor":     "Open Collections",
            "category":   "Credit",
            "tier_label": "Present",
            "points":     -30,
            "max":        0,
            "weight":     "Penalty",
            "note":       "Open collection accounts on personal credit report. Number, recency, and dollar amount reviewed by lender.",
        })
        flags.append("Open collections present — lender will require explanation letter and may require resolution before closing.")

    if inputs.get("tax_liens"):
        score -= 50
        breakdown.append({
            "factor":     "Tax Liens",
            "category":   "Credit",
            "tier_label": "Active",
            "points":     -50,
            "max":        0,
            "weight":     "Penalty",
            "note":       "Federal or state tax liens are a significant negative. Must be paid, on a payment plan, or subordinated. Unresolved federal tax liens may constitute delinquent federal debt.",
        })
        flags.append("Tax liens present — may constitute delinquent federal debt. Must be resolved or formally in payment plan before closing.")

    if inputs.get("bankruptcy_discharged"):
        years = inputs.get("years_since_bankruptcy", 0)
        if years < 2:
            score -= 100
            breakdown.append({
                "factor":     "Prior Bankruptcy",
                "category":   "Credit",
                "tier_label": f"Discharged ({years} yr ago)",
                "points":     -100,
                "max":        0,
                "weight":     "Penalty",
                "note":       "Recent bankruptcy discharge. SBA requires 2+ years post-discharge minimum; most PLP lenders require 3–5 years.",
            })
            flags.append(f"Bankruptcy discharged {years} year(s) ago — most PLP lenders require 3–5 years post-discharge. Severely limits lender options.")
        elif years < 5:
            score -= 40
            breakdown.append({
                "factor":     "Prior Bankruptcy",
                "category":   "Credit",
                "tier_label": f"Discharged ({years} yrs ago)",
                "points":     -40,
                "max":        0,
                "weight":     "Penalty",
                "note":       "Prior bankruptcy discharged. Some lenders require 5+ years seasoning.",
            })
            flags.append(f"Bankruptcy discharged {years} years ago — some PLP lenders require 5+ year seasoning. Verify with target lender.")
        else:
            score -= 10
            breakdown.append({
                "factor":     "Prior Bankruptcy",
                "category":   "Credit",
                "tier_label": f"Discharged ({years}+ yrs ago)",
                "points":     -10,
                "max":        0,
                "weight":     "Minor Penalty",
                "note":       "Prior bankruptcy, well-seasoned. Less impact if credit rebuilt since discharge.",
            })

    if inputs.get("criminal_history"):
        score -= 50
        breakdown.append({
            "factor":     "Criminal History",
            "category":   "Credit",
            "tier_label": "Disclosed",
            "points":     -50,
            "max":        0,
            "weight":     "Penalty",
            "note":       "Criminal history disclosed. Not an automatic decline but requires full disclosure and explanation. Severity depends on type, recency, and rehabilitation evidence.",
        })
        flags.append("Criminal history — borrower must complete SBA Form 912. Lender will evaluate type, recency, and evidence of rehabilitation. Felonies are more heavily scrutinized.")

    # ── Financial: Entity DSCR ────────────────────────────────────────────
    dscr_e_tier = inputs.get("dscr_entity_tier", "")
    dscr_e_pts = DSCR_ENTITY_SCORES.get(dscr_e_tier, 0)
    score += dscr_e_pts
    breakdown.append({
        "factor":      "DSCR (Entity)",
        "category":    "Financial",
        "tier_label":  dscr_e_tier or "Not provided",
        "points":      dscr_e_pts,
        "max":         100,
        "weight":      "High",
        "note":        "Business-level Debt Service Coverage Ratio. Net Operating Income ÷ Total Debt Service. SBA minimum: 1.10x. PLP lenders target 1.25x+.",
    })

    # ── Financial: Global Cash Flow DSCR ─────────────────────────────────
    dscr_g_tier = inputs.get("dscr_global_tier", "")
    dscr_g_pts = DSCR_GLOBAL_SCORES.get(dscr_g_tier, 0)
    score += dscr_g_pts
    breakdown.append({
        "factor":      "Global Cash Flow DSCR",
        "category":    "Financial",
        "tier_label":  dscr_g_tier or "Not provided",
        "points":      dscr_g_pts,
        "max":         100,
        "weight":      "High",
        "note":        "Consolidates ALL income and obligations across all entities owned, plus personal income/expenses and personal debt service. Required by SOP 50 10 8. SBA minimum: 1.10x.",
    })

    # ── Financial: Leverage (Debt-to-NW) ─────────────────────────────────
    lev_tier = inputs.get("leverage_tier", "")
    lev_pts = LEVERAGE_SCORES.get(lev_tier, 0)
    score += lev_pts
    if lev_tier:
        breakdown.append({
            "factor":      "Leverage (Debt-to-Net Worth)",
            "category":    "Financial",
            "tier_label":  lev_tier,
            "points":      lev_pts,
            "max":         50,
            "weight":      "Medium",
            "note":        "Total Liabilities ÷ Tangible Net Worth. Above 4:1 is a significant red flag. Required by SOP 50 10 8 credit memo.",
        })
        if lev_tier in ("4-5", "above_5"):
            flags.append(f"High leverage ratio ({lev_tier}x) — lender will require detailed explanation and may require additional collateral or equity injection.")

    # ── Financial: Current Ratio ───────────────────────────────────────────
    cr_tier = inputs.get("current_ratio_tier", "")
    cr_pts = CURRENT_RATIO_SCORES.get(cr_tier, 0)
    score += cr_pts
    if cr_tier:
        breakdown.append({
            "factor":      "Current Ratio (Working Capital)",
            "category":    "Financial",
            "tier_label":  cr_tier,
            "points":      cr_pts,
            "max":         40,
            "weight":      "Medium",
            "note":        "Current Assets ÷ Current Liabilities. Below 1.0 means business cannot cover short-term obligations from short-term assets.",
        })
        if cr_tier == "below_1":
            flags.append("Current ratio below 1.0 — business cannot cover short-term obligations. If ≥50% of loan proceeds are for working capital, SOP 50 10 8 requires lien on all fixed assets.")

    # ── Financial: Revenue Trend ───────────────────────────────────────────
    rev_trend = inputs.get("revenue_trend", "")
    trend_pts = REVENUE_TREND_SCORES.get(rev_trend, 0)
    score += trend_pts
    if rev_trend:
        breakdown.append({
            "factor":      "Revenue Trend",
            "category":    "Financial",
            "tier_label":  rev_trend.replace("_", " ").title(),
            "points":      trend_pts,
            "max":         50,
            "weight":      "Medium",
            "note":        "Year-over-year revenue change across most recent 2–3 tax years. Required trend analysis in credit memo.",
        })
        if rev_trend in ("slight_decline", "significant_decline"):
            flags.append("Declining revenue — even if DSCR is currently adequate, a declining trend is a leading indicator of future cash flow deterioration. Lender will scrutinize.")

    # ── Financial: Revenue Concentration ─────────────────────────────────
    concentration = inputs.get("revenue_concentration", "")
    conc_pts = CONCENTRATION_PENALTIES.get(concentration, 0)
    score += conc_pts
    if concentration and concentration != "none":
        breakdown.append({
            "factor":      "Revenue Concentration Risk",
            "category":    "Financial",
            "tier_label":  concentration.replace("_", " ").title(),
            "points":      conc_pts,
            "max":         0,
            "weight":      "Penalty",
            "note":        "Single customer revenue concentration. >25-30% concentration creates structural fragility even with strong historical DSCR.",
        })
        if concentration in ("significant", "highly_concentrated"):
            flags.append("High customer concentration — lender will likely require a risk narrative explaining customer relationship, contract terms, and contingency plan if customer is lost.")

    # ── Business Age ───────────────────────────────────────────────────────
    age_tier = inputs.get("business_age_tier", "")
    age_pts = AGE_SCORES.get(age_tier, 0)
    score += age_pts
    breakdown.append({
        "factor":      "Business Age",
        "category":    "Business",
        "tier_label":  age_tier.replace("_", " ") if age_tier else "Not provided",
        "points":      age_pts,
        "max":         150,
        "weight":      "High",
        "note":        "Years in operation. Under 2 years = start-up classification requiring projections and equity injection.",
    })

    # ── Business: Start-up flags ───────────────────────────────────────────
    is_startup = inputs.get("is_startup", age_tier in ("under_1", "1-2"))
    if is_startup:
        if not inputs.get("equity_injection_available"):
            score -= 100
            breakdown.append({
                "factor":      "Equity Injection (Start-up)",
                "category":    "Business",
                "tier_label":  "Not Available",
                "points":      -100,
                "max":         0,
                "weight":      "Penalty",
                "note":        "10% equity injection is required for start-ups and business acquisitions. Seller notes may qualify only if on full standby for the full loan term.",
            })
            flags.append("No equity injection available — 10% injection required for start-up and acquisition loans per SOP 50 10 8. Application cannot close without verified injection from eligible source.")
        else:
            flags.append("Start-up business — must provide business plan, financial projections, and verified 10% equity injection source documentation.")

    # ── Business: Franchise check ──────────────────────────────────────────
    if inputs.get("is_franchise"):
        if not inputs.get("franchise_on_sba_directory"):
            score -= 40
            breakdown.append({
                "factor":      "Franchise — SBA Directory",
                "category":    "Business",
                "tier_label":  "Not on SBA Directory",
                "points":      -40,
                "max":         0,
                "weight":      "Penalty",
                "note":        "Franchise must appear on the SBA Franchise Directory. If not listed, requires additional eligibility analysis that delays approval.",
            })
            flags.append("Franchise not on SBA Franchise Directory — requires eligibility analysis before proceeding. Check sba.gov/franchise-directory.")

    # ── Industry ──────────────────────────────────────────────────────────
    industry = inputs.get("industry", "")
    ind_pts = INDUSTRY_SCORES.get(industry, 0)
    score += ind_pts
    breakdown.append({
        "factor":      "Industry",
        "category":    "Business",
        "tier_label":  industry.replace("_", " ").title() if industry else "Not provided",
        "points":      ind_pts,
        "max":         100,
        "weight":      "Medium",
        "note":        "SBA industry risk classification. Restaurants, construction, and retail score lower due to historically higher default rates.",
    })

    # ── Owner Experience ──────────────────────────────────────────────────
    exp_tier = inputs.get("experience_tier", "")
    exp_pts = EXPERIENCE_SCORES.get(exp_tier, 0)
    score += exp_pts
    breakdown.append({
        "factor":      "Owner/Management Experience",
        "category":    "Owner",
        "tier_label":  exp_tier.replace("_", " ") if exp_tier else "Not provided",
        "points":      exp_pts,
        "max":         50,
        "weight":      "Medium",
        "note":        "Direct industry and management experience of primary guarantor. Compensating factor for borderline files.",
    })

    # ── Personal Net Worth & Liquidity ────────────────────────────────────
    nw_tier = inputs.get("net_worth_tier", "")
    nw_pts = NET_WORTH_SCORES.get(nw_tier, 0)
    score += nw_pts
    if nw_tier:
        breakdown.append({
            "factor":      "Personal Net Worth / Liquidity",
            "category":    "Owner",
            "tier_label":  nw_tier.replace("_", " ").title(),
            "points":      nw_pts,
            "max":         50,
            "weight":      "Medium",
            "note":        "Guarantor personal net worth and post-injection liquid assets from SBA Form 413. Negative net worth = worthless personal guarantee.",
        })
        if nw_tier == "negative":
            flags.append("Negative personal net worth — personal guarantee has limited practical value. Lender will look for additional collateral or co-borrower with positive net worth.")

    # ── Collateral ────────────────────────────────────────────────────────
    if inputs.get("collateral_available"):
        collateral_type = inputs.get("collateral_type", "other")
        collateral_pts = {"real_estate": 50, "equipment": 30, "other": 20}.get(collateral_type, 20)
        score += collateral_pts
        breakdown.append({
            "factor":      f"Collateral ({collateral_type.replace('_',' ').title()})",
            "category":    "Collateral",
            "tier_label":  "Available",
            "points":      collateral_pts,
            "max":         50,
            "weight":      "Compensating",
            "note":        "SBA SOP 50 10 8: loans >$50K must be fully collateralized. Real estate discounted at 85% of value; equipment at 50–75%; inventory/AR at 10%.",
        })
        if collateral_type == "real_estate":
            flags.append("Real estate collateral — environmental review required per SOP 50 10 8. Obtain Phase I ESA if any indication of environmental contamination (gas stations, dry cleaners, auto repair, industrial).")
    else:
        loan_amount = inputs.get("loan_amount", 0)
        if loan_amount > 50000:
            flags.append(f"No collateral available — loans over $50K must be collateralized to maximum extent possible per SOP 50 10 8. Lender must document why collateral is unavailable.")

    # ── Key Person Risk ───────────────────────────────────────────────────
    if inputs.get("key_person_risk"):
        score -= 20
        breakdown.append({
            "factor":      "Key Person / Owner Dependency",
            "category":    "Owner",
            "tier_label":  "Single owner, high dependency",
            "points":      -20,
            "max":         0,
            "weight":      "Penalty",
            "note":        "Business depends on one owner's skills/relationships. SOP 50 10 8 may require life insurance on key principal assigned to lender if loan is not fully collateralized.",
        })
        flags.append("Key person risk — if loan is not fully collateralized, lender will likely require life insurance policy on primary owner assigned to lender in amount equal to collateral shortfall.")

    # ── Use of Proceeds ───────────────────────────────────────────────────
    if inputs.get("use_of_proceeds_eligible") is False:
        score -= 75
        breakdown.append({
            "factor":      "Use of Proceeds",
            "category":    "Loan Structure",
            "tier_label":  "Ineligible or unclear",
            "points":      -75,
            "max":         0,
            "weight":      "Penalty",
            "note":        "SBA proceeds cannot be used for: personal expenses, refinancing SBA debt (generally), paying dividends, repaying owner equity, or speculative purposes.",
        })
        flags.append("Use of proceeds may be ineligible — every dollar must map to an eligible SBA purpose. Misalignment can result in guaranty denial on default.")

    # ── Bank Statement Quality ─────────────────────────────────────────────
    if inputs.get("nsf_overdrafts"):
        score -= 25
        breakdown.append({
            "factor":      "Bank Account Management",
            "category":    "Financial",
            "tier_label":  "NSFs / Overdrafts present",
            "points":      -25,
            "max":         0,
            "weight":      "Penalty",
            "note":        "SOP 50 10 8 requires review of 2 months of business bank statements. Frequent NSFs or overdrafts are a character and capacity concern.",
        })
        flags.append("NSF/overdraft history — SOP 50 10 8 requires 2 months bank statements. Frequent overdrafts signal cash management issues and will concern lenders.")

    # Cap and floor
    score = max(0, min(1000, score))

    # ── Determine tier ────────────────────────────────────────────────────
    tier_name, tier_color, tier_desc = "Auto-Decline", "red", ""
    for threshold, name, color, desc in TIERS:
        if score >= threshold:
            tier_name, tier_color, tier_desc = name, color, desc
            break

    # ── Lender routing ────────────────────────────────────────────────────
    sbss_numeric = {"above_220": 220, "200-220": 210, "180-199": 190,
                    "165-179": 170, "below_165": 150}.get(sbss_tier, 0)
    lender_matches = [
        l for l in LENDER_ROUTES
        if score >= l["min_score"] and sbss_numeric >= l["min_sbss"]
    ]

    # ── Life insurance trigger flag ───────────────────────────────────────
    if inputs.get("key_person_risk") and not inputs.get("collateral_available"):
        flags.append("Life insurance required — key person risk + no collateral: lender must require life insurance on primary owner assigned as lender beneficiary.")

    # ── Hazard insurance flag ─────────────────────────────────────────────
    loan_amount = inputs.get("loan_amount", 0)
    if loan_amount > 50000 and inputs.get("collateral_available"):
        flags.append("Hazard insurance required on all collateral at full replacement cost. Flood insurance required if collateral is in a FEMA special flood hazard area.")

    # ── Tax transcript flag ────────────────────────────────────────────────
    flags.append("IRS 4506-C tax transcript verification required — SOP 50 10 8 reinstated this requirement. Discrepancies between submitted returns and IRS records are an immediate credibility issue.")

    # ── Recommendation ────────────────────────────────────────────────────
    if score >= 750:
        rec = "File is strong. Address any advisory flags above, generate the lender package, and route to the best matched lender."
    elif score >= 600:
        rec = "File looks good. Resolve open flags and confirm all Five Cs are documented before submitting for senior LO review."
    elif score >= 500:
        rec = "Borderline file. Identify and document compensating factors (collateral, experience, strong industry ties). Route to credit committee with compensating factor narrative."
    elif score >= 400:
        rec = "File has material weaknesses. Consider SBA Microloan (up to $50K), CDFI financing, or conventional line of credit. If proceeding, credit committee must approve with full compensating factor documentation."
    else:
        rec = "File does not meet minimum standards. Issue a decline with reason codes. Discuss SBA Microloan, CDFI, or alternative financing options with the borrower."

    return {
        "score": score,
        "tier": tier_name,
        "tier_color": tier_color,
        "tier_description": tier_desc,
        "hard_stop": False,
        "hard_stop_reasons": [],
        "hard_stop_reason": None,
        "factor_breakdown": breakdown,
        "flags": flags,
        "lender_matches": lender_matches,
        "recommendation": rec,
    }


def score_from_profile(profile: dict) -> dict:
    """
    Derive basic underwriting inputs from a borrower profile dict
    and run the scoring engine with available data.
    """
    owners = profile.get("owners", [])
    fins = profile.get("personal_financials", [{}])
    biz = profile.get("business", {})
    fin = fins[0] if fins else {}

    inputs = {}

    # Hard stops from profile
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
                inputs["is_startup"] = True
        except Exception:
            pass

    # Citizenship
    for owner in owners:
        if not owner.get("us_citizen"):
            inputs["citizenship_failure"] = True

    # Personal liquidity
    try:
        salary = float(fin.get("annual_salary", 0) or 0)
        inputs["positive_cash_flow"] = salary > 0
    except Exception:
        pass

    return score_application(inputs)
