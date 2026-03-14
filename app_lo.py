"""
Loan Officer / Bundler App — app_lo.py (Demo Mode)
Ramp-inspired UI. No API key required.
Run with: streamlit run app_lo.py
"""

import os, json, io, zipfile
import streamlit as st
from deal_store import (
    create_deal, get_deal, list_deals, update_deal_status, set_urgency,
    add_document, save_document_fields, get_documents, delete_document,
    save_profile, get_profile, save_package, get_packages,
)
from gap_detector import detect_gaps, readiness_score
from underwriting_engine import score_application, score_from_profile, TIERS
from sba_form_filler import (
    download_form, build_1919_fields, build_413_fields, fill_form,
    FORMS_DIR, OUTPUT_DIR,
)

st.set_page_config(
    page_title="SBA Loan Officer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

os.makedirs(FORMS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Ramp-inspired CSS
# ---------------------------------------------------------------------------

RAMP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
}
.stApp {
    background: #F4F5F7;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0F1122 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] [data-testid="stText"],
[data-testid="stSidebar"] [data-testid="stCaption"] {
    color: rgba(255,255,255,0.65) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    width: 100% !important;
    padding: 7px 14px !important;
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    transition: background 0.12s;
}
[data-testid="stSidebar"] .stButton > button > p,
[data-testid="stSidebar"] .stButton > button > div,
[data-testid="stSidebar"] .stButton > button span {
    color: rgba(255,255,255,0.7) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.07) !important;
}
[data-testid="stSidebar"] .stButton > button:hover > p,
[data-testid="stSidebar"] .stButton > button:hover > div,
[data-testid="stSidebar"] .stButton > button:hover span {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button:focus {
    outline: none !important;
    background: rgba(255,255,255,0.07) !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 10px 0 !important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: rgba(255,255,255,0.3) !important;
    font-size: 10px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}

/* ── Top header / toolbar ── */
[data-testid="stHeader"] {
    display: none !important;
}
[data-testid="stToolbar"] {
    display: none !important;
}
[data-testid="stDecoration"] {
    display: none !important;
}

/* ── Main area ── */
.main .block-container {
    padding: 12px 40px 56px 40px !important;
    max-width: 1360px !important;
}
.main .block-container > div:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* ── Page title ── */
h1 {
    font-size: 24px !important;
    font-weight: 700 !important;
    color: #0D1117 !important;
    letter-spacing: -0.5px !important;
    margin-bottom: 4px !important;
}
h2 {
    font-size: 16px !important;
    font-weight: 600 !important;
    color: #0D1117 !important;
    margin-bottom: 2px !important;
}
h3 {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    transition: box-shadow 0.15s !important;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #9CA3AF !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: #0D1117 !important;
    letter-spacing: -0.8px !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 12px !important;
    font-weight: 500 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg {
    display: inline-block !important;
    vertical-align: middle !important;
}

/* ── Primary buttons ── */
.stButton > button[kind="primary"] {
    background: #1A56DB !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 9px 20px !important;
    transition: background 0.15s, box-shadow 0.15s !important;
    box-shadow: 0 1px 3px rgba(26,86,219,0.3) !important;
    letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"] > p,
.stButton > button[kind="primary"] > div,
.stButton > button[kind="primary"] span {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1648C0 !important;
    box-shadow: 0 3px 10px rgba(26,86,219,0.35) !important;
}
.stButton > button[kind="primary"]:focus {
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(26,86,219,0.25) !important;
}

/* ── Secondary buttons ── */
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
    background: #FFFFFF !important;
    border: 1px solid #D1D5DB !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    transition: border-color 0.12s, box-shadow 0.12s, background 0.12s !important;
}
.stButton > button[kind="secondary"] > p,
.stButton > button[kind="secondary"] > div,
.stButton > button[kind="secondary"] span,
.stButton > button:not([kind]) > p,
.stButton > button:not([kind]) > div,
.stButton > button:not([kind]) span {
    color: #374151 !important;
    font-weight: 500 !important;
}
.stButton > button:not([kind]):hover,
.stButton > button[kind="secondary"]:hover {
    background: #F9FAFB !important;
    border-color: #9CA3AF !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
}
.stButton > button:not([kind]):focus,
.stButton > button[kind="secondary"]:focus {
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(26,86,219,0.15) !important;
}

/* ── Containers / Cards ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    padding: 0 !important;
    overflow: hidden;
    transition: box-shadow 0.15s !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.07) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #E5E7EB !important;
    background: transparent !important;
    gap: 0 !important;
}
[data-testid="stTabs"] [role="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    padding: 11px 20px !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    background: transparent !important;
    margin-bottom: -1px !important;
    transition: color 0.12s !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #0D1117 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #1A56DB !important;
    background: transparent !important;
}
[data-testid="stTabs"] [role="tab"]:focus {
    outline: none !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
    box-shadow: none !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    padding: 13px 18px !important;
}
[data-testid="stExpander"] summary:hover {
    background: #F9FAFB !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div > div {
    border: 1px solid #D1D5DB !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    background: #FFFFFF !important;
    color: #111827 !important;
    box-shadow: none !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #1A56DB !important;
    box-shadow: 0 0 0 3px rgba(26,86,219,0.1) !important;
}
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #6B7280 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div > div {
    background: linear-gradient(90deg, #1A56DB, #3B82F6) !important;
    border-radius: 999px !important;
}
[data-testid="stProgressBar"] > div > div {
    background: #E5E7EB !important;
    border-radius: 999px !important;
    height: 6px !important;
}

/* ── Info / success / warning / error boxes ── */
[data-testid="stInfo"] {
    background: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 10px !important;
    color: #1E40AF !important;
    font-size: 13px !important;
}
[data-testid="stSuccess"] {
    background: #F0FDF4 !important;
    border: 1px solid #BBF7D0 !important;
    border-radius: 10px !important;
    color: #15803D !important;
    font-size: 13px !important;
}
[data-testid="stError"] {
    background: #FEF2F2 !important;
    border: 1px solid #FECACA !important;
    border-radius: 10px !important;
    color: #DC2626 !important;
    font-size: 13px !important;
}
[data-testid="stWarning"] {
    background: #FFFBEB !important;
    border: 1px solid #FDE68A !important;
    border-radius: 10px !important;
    color: #92400E !important;
    font-size: 13px !important;
}

/* ── Divider ── */
hr {
    border-color: #E5E7EB !important;
    margin: 20px 0 !important;
}

/* ── Captions / small text ── */
.stCaption, [data-testid="stCaption"] {
    font-size: 12px !important;
    color: #9CA3AF !important;
}

/* ── Dividers ── */
hr {
    border-color: #F3F4F6 !important;
    margin: 16px 0 !important;
}

/* ── Checkboxes ── */
[data-testid="stCheckbox"] label {
    font-size: 13px !important;
    color: #374151 !important;
    text-transform: none !important;
    letter-spacing: normal !important;
    font-weight: 400 !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #D1D5DB !important;
    border-radius: 10px !important;
    background: #FAFAFA !important;
    padding: 20px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #0066FF !important;
    background: #EFF6FF !important;
}

/* ── Toggle ── */
[data-testid="stToggle"] label {
    font-size: 12px !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: #FFFFFF !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
[data-testid="stDownloadButton"] button > p,
[data-testid="stDownloadButton"] button > div,
[data-testid="stDownloadButton"] button span {
    color: #0066FF !important;
    font-weight: 500 !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: #EFF6FF !important;
}
[data-testid="stDownloadButton"] button:focus {
    outline: 2px solid #0066FF !important;
    outline-offset: 2px !important;
}

/* ── Status badge helpers (via markdown) ── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    line-height: 1.6;
}
.badge-green  { background: #DCFCE7; color: #15803D; }
.badge-blue   { background: #DBEAFE; color: #1D4ED8; }
.badge-yellow { background: #FEF9C3; color: #854D0E; }
.badge-red    { background: #FEE2E2; color: #DC2626; }
.badge-gray   { background: #F3F4F6; color: #4B5563; }
.badge-orange { background: #FFEDD5; color: #C2410C; }

/* ── Deal row card ── */
.deal-row {
    display: flex;
    align-items: center;
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 8px;
    transition: box-shadow 0.15s, border-color 0.15s;
    gap: 0;
}
.deal-row:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    border-color: #D1D5DB;
}
.deal-name { font-size: 14px; font-weight: 600; color: #111827; }
.deal-id   { font-size: 11px; color: #9CA3AF; font-family: monospace; margin-top: 2px; }
.deal-amount { font-size: 15px; font-weight: 700; color: #111827; font-variant-numeric: tabular-nums; }
.col-label  { font-size: 11px; font-weight: 500; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.06em; padding-bottom: 8px; }
.section-title { font-size: 13px; font-weight: 600; color: #374151; text-transform: uppercase; letter-spacing: 0.07em; margin: 20px 0 10px 0; }
.field-source { font-size: 11px; color: #9CA3AF; margin-top: 1px; }
</style>
"""

st.markdown(RAMP_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Demo data seed
# ---------------------------------------------------------------------------

DEMO_DEALS = [
    {
        "borrower_name": "Apex Roofing LLC",
        "loan_amount": 350000,
        "status": "Ready",
        "urgency": True,
        "notes": "Referred by First Western Bank. Owner wants to close before end of quarter.",
        "docs": [
            {"filename": "apex_2023_1040.pdf",   "doc_type": "tax_return_personal", "summary": "2023 personal tax return — James Whitfield"},
            {"filename": "apex_2023_1120S.pdf",  "doc_type": "tax_return_business", "summary": "2023 S-Corp return — Apex Roofing LLC"},
            {"filename": "apex_bank_stmts.pdf",  "doc_type": "bank_statement",      "summary": "Chase business checking Jan–Mar 2026"},
            {"filename": "apex_intake_form.pdf", "doc_type": "intake_form",         "summary": "Broker intake sheet"},
        ],
        "profile": {
            "business": {"legal_name":"Apex Roofing LLC","dba":"","ein":"82-4719302","entity_type":"S Corp","date_established":"03/14/2018","state_of_organization":"TX","naics_code":"238160","phone":"512-847-3920","email":"james@apexroofing.com","address_street":"4821 Industrial Blvd","address_city":"Austin","address_state":"TX","address_zip":"78744","num_employees":"12","fiscal_year_end":"12/31","loan_amount_requested":"350000","loan_purpose":"Purchase new equipment and expand crew for commercial contracts"},
            "owners": [{"first_name":"James","last_name":"Whitfield","title":"President & Owner","ownership_pct":"100","ssn":"541-77-2983","dob":"07/22/1979","phone":"512-847-3920","email":"james@apexroofing.com","address_street":"118 Ridgecrest Dr","address_city":"Austin","address_state":"TX","address_zip":"78746","us_citizen":True,"criminal_history":False,"currently_incarcerated":False,"probation_parole":False,"prior_sba_loan":False,"prior_default":False,"delinquent_federal_debt":False}],
            "personal_financials": [{"as_of_date":"03/01/2026","cash_and_savings":"87000","ira_401k":"143000","real_estate_value":"620000","real_estate_mortgage":"388000","auto_value":"42000","auto_loan_balance":"18500","other_assets":"15000","credit_cards_balance":"4200","other_liabilities":"0","annual_salary":"180000","other_income":"0","other_income_source":""}],
        },
        "meta": {
            "business.legal_name":   {"value":"Apex Roofing LLC","confidence":"high","source_text":"Form 1120-S Line 1","doc_type":"tax_return_business","filename":"apex_2023_1120S.pdf","conflicts":[]},
            "business.ein":          {"value":"82-4719302","confidence":"high","source_text":"EIN: 82-4719302","doc_type":"tax_return_business","filename":"apex_2023_1120S.pdf","conflicts":[]},
            "owner0.ssn":            {"value":"541-77-2983","confidence":"high","source_text":"SSN on 1040 line 1","doc_type":"tax_return_personal","filename":"apex_2023_1040.pdf","conflicts":[]},
            "owner0.address_street": {"value":"118 Ridgecrest Dr","confidence":"medium","source_text":"Intake form home address","doc_type":"intake_form","filename":"apex_intake_form.pdf","conflicts":[
                {"value":"122 Ridgecrest Dr","confidence":"low","source_text":"Email from borrower: '...my address is 122 Ridgecrest...'","doc_type":"email_notes","filename":"apex_email_thread.txt"}
            ]},
            "fin0.cash_and_savings": {"value":"87000","confidence":"high","source_text":"Chase stmt ending bal: $87,241","doc_type":"bank_statement","filename":"apex_bank_stmts.pdf","conflicts":[]},
            "fin0.annual_salary":    {"value":"180000","confidence":"high","source_text":"1040 Line 1: Wages $180,000","doc_type":"tax_return_personal","filename":"apex_2023_1040.pdf","conflicts":[]},
        },
    },
    {
        "borrower_name": "Sunrise Wellness Studio",
        "loan_amount": 175000,
        "status": "Gaps",
        "urgency": False,
        "notes": "New business — opened 8 months ago. Will need business plan.",
        "docs": [
            {"filename": "sunrise_owner_1040.pdf", "doc_type": "tax_return_personal", "summary": "2023 personal tax return — Maria Chen"},
            {"filename": "sunrise_bank_3mo.pdf",   "doc_type": "bank_statement",      "summary": "Bank statements Dec 2025–Feb 2026"},
            {"filename": "sunrise_email_notes.txt","doc_type": "email_notes",         "summary": "Email thread with borrower"},
        ],
        "profile": {
            "business": {"legal_name":"Sunrise Wellness Studio LLC","dba":"Sunrise Wellness","ein":"93-0284710","entity_type":"LLC","date_established":"06/01/2025","state_of_organization":"CA","naics_code":"812190","phone":"415-302-8847","email":"","address_street":"2240 Market Street, Suite 4","address_city":"San Francisco","address_state":"CA","address_zip":"94114","num_employees":"3","fiscal_year_end":"12/31","loan_amount_requested":"175000","loan_purpose":"Working capital and buildout of second treatment room"},
            "owners": [{"first_name":"Maria","last_name":"Chen","title":"Managing Member","ownership_pct":"100","ssn":"","dob":"11/03/1987","phone":"415-302-8847","email":"maria@sunrisewellness.com","address_street":"881 Castro St Apt 3C","address_city":"San Francisco","address_state":"CA","address_zip":"94114","us_citizen":True,"criminal_history":False,"currently_incarcerated":False,"probation_parole":False,"prior_sba_loan":False,"prior_default":False,"delinquent_federal_debt":False}],
            "personal_financials": [{"as_of_date":"03/01/2026","cash_and_savings":"22000","ira_401k":"41000","real_estate_value":"0","real_estate_mortgage":"0","auto_value":"15000","auto_loan_balance":"6200","other_assets":"0","credit_cards_balance":"8700","other_liabilities":"0","annual_salary":"0","other_income":"0","other_income_source":""}],
        },
        "meta": {
            "business.ein":       {"value":"93-0284710","confidence":"medium","source_text":"Email: 'EIN is 93-0284710'","doc_type":"email_notes","filename":"sunrise_email_notes.txt","conflicts":[]},
            "owner0.ssn":         {"value":"","confidence":"low","source_text":"Not found in any document","doc_type":"","filename":"","conflicts":[]},
            "fin0.annual_salary": {"value":"0","confidence":"low","source_text":"Business < 1yr, no W-2 on 1040","doc_type":"tax_return_personal","filename":"sunrise_owner_1040.pdf","conflicts":[]},
        },
    },
    {
        "borrower_name": "Gulf Coast Transport Inc",
        "loan_amount": 490000,
        "status": "Review",
        "urgency": False,
        "notes": "Multi-owner. 3 trucks, wants 2 more. Strong revenue $1.8M.",
        "docs": [
            {"filename": "gct_2022_1120.pdf",    "doc_type": "tax_return_business",  "summary": "2022 corporate return — $1.2M revenue"},
            {"filename": "gct_2023_1120.pdf",    "doc_type": "tax_return_business",  "summary": "2023 corporate return — $1.8M revenue"},
            {"filename": "gct_owner1_1040.pdf",  "doc_type": "tax_return_personal",  "summary": "2023 personal return — Carlos Rivera"},
            {"filename": "gct_owner2_1040.pdf",  "doc_type": "tax_return_personal",  "summary": "2023 personal return — Diane Rivera"},
            {"filename": "gct_bank_6mo.pdf",     "doc_type": "bank_statement",       "summary": "6 months business bank statements"},
            {"filename": "gct_pl_2026ytd.pdf",   "doc_type": "financial_statement",  "summary": "YTD P&L through Feb 2026"},
        ],
        "profile": {
            "business": {"legal_name":"Gulf Coast Transport Inc","dba":"GCT Freight","ein":"74-3820194","entity_type":"C Corp","date_established":"01/08/2015","state_of_organization":"TX","naics_code":"484121","phone":"713-558-4401","email":"carlos@gctfreight.com","address_street":"9900 Port Rd","address_city":"Houston","address_state":"TX","address_zip":"77029","num_employees":"8","fiscal_year_end":"12/31","loan_amount_requested":"490000","loan_purpose":"Purchase two additional commercial freight trucks"},
            "owners": [
                {"first_name":"Carlos","last_name":"Rivera","title":"CEO","ownership_pct":"60","ssn":"612-44-8823","dob":"04/15/1974","phone":"713-558-4401","email":"carlos@gctfreight.com","address_street":"3312 Magnolia Ave","address_city":"Houston","address_state":"TX","address_zip":"77006","us_citizen":True,"criminal_history":False,"currently_incarcerated":False,"probation_parole":False,"prior_sba_loan":True,"prior_default":False,"delinquent_federal_debt":False},
                {"first_name":"Diane","last_name":"Rivera","title":"COO","ownership_pct":"40","ssn":"619-88-4471","dob":"09/30/1976","phone":"713-558-4402","email":"diane@gctfreight.com","address_street":"3312 Magnolia Ave","address_city":"Houston","address_state":"TX","address_zip":"77006","us_citizen":True,"criminal_history":False,"currently_incarcerated":False,"probation_parole":False,"prior_sba_loan":True,"prior_default":False,"delinquent_federal_debt":False},
            ],
            "personal_financials": [
                {"as_of_date":"03/01/2026","cash_and_savings":"142000","ira_401k":"310000","real_estate_value":"880000","real_estate_mortgage":"490000","auto_value":"55000","auto_loan_balance":"22000","other_assets":"30000","credit_cards_balance":"5400","other_liabilities":"0","annual_salary":"220000","other_income":"18000","other_income_source":"Rental income"},
                {"as_of_date":"03/01/2026","cash_and_savings":"88000","ira_401k":"195000","real_estate_value":"880000","real_estate_mortgage":"490000","auto_value":"35000","auto_loan_balance":"0","other_assets":"10000","credit_cards_balance":"3100","other_liabilities":"0","annual_salary":"130000","other_income":"0","other_income_source":""},
            ],
        },
        "meta": {
            "business.loan_amount_requested": {"value":"490000","confidence":"medium","source_text":"Email: 'We need around $490K for two trucks'","doc_type":"email_notes","filename":"notes.txt","conflicts":[
                {"value":"500000","confidence":"low","source_text":"Intake form: loan amount $500,000","doc_type":"intake_form","filename":"gct_intake.pdf"}
            ]},
            "owner0.ssn": {"value":"612-44-8823","confidence":"high","source_text":"1040 SSN: 612-44-8823","doc_type":"tax_return_personal","filename":"gct_owner1_1040.pdf","conflicts":[]},
            "owner1.ssn": {"value":"619-88-4471","confidence":"high","source_text":"1040 SSN: 619-88-4471","doc_type":"tax_return_personal","filename":"gct_owner2_1040.pdf","conflicts":[]},
        },
    },
    {
        "borrower_name": "Ironwood Fabrication Co",
        "loan_amount": 225000,
        "status": "Submitted",
        "urgency": False,
        "notes": "Submitted to Harvest Small Business Finance on 3/10. Awaiting decision.",
        "docs": [{"filename": "ironwood_complete_pkg.pdf", "doc_type": "intake_form", "summary": "Complete application package"}],
        "profile": {
            "business": {"legal_name":"Ironwood Fabrication Co LLC","ein":"47-1938204","entity_type":"LLC","date_established":"09/22/2019","state_of_organization":"OH","naics_code":"332999","phone":"614-772-3344","email":"ops@ironwoodfab.com","address_street":"8811 Commerce Dr","address_city":"Columbus","address_state":"OH","address_zip":"43235","num_employees":"6","loan_amount_requested":"225000","loan_purpose":"Working capital and inventory expansion"},
            "owners": [{"first_name":"Derek","last_name":"Osei","title":"Managing Member","ownership_pct":"100","ssn":"287-63-4410","dob":"02/14/1982","phone":"614-772-3344","email":"derek@ironwoodfab.com","address_street":"44 Lakeview Ct","address_city":"Columbus","address_state":"OH","address_zip":"43221","us_citizen":True,"criminal_history":False,"currently_incarcerated":False,"probation_parole":False,"prior_sba_loan":False,"prior_default":False,"delinquent_federal_debt":False}],
            "personal_financials": [{"as_of_date":"02/15/2026","cash_and_savings":"53000","ira_401k":"98000","real_estate_value":"310000","real_estate_mortgage":"198000","auto_value":"28000","auto_loan_balance":"11000","other_assets":"5000","credit_cards_balance":"2800","other_liabilities":"0","annual_salary":"95000","other_income":"0","other_income_source":""}],
        },
        "meta": {},
    },
]


def seed_demo_data():
    if list_deals():
        return
    for d in DEMO_DEALS:
        deal_id = create_deal(d["borrower_name"], d["loan_amount"], d["notes"])
        update_deal_status(deal_id, d["status"])
        if d["urgency"]:
            set_urgency(deal_id, True)
        for doc in d["docs"]:
            doc_id = add_document(deal_id, doc["filename"], doc["doc_type"], doc["summary"])
            save_document_fields(doc_id, doc["doc_type"], doc["summary"], {})
        save_profile(deal_id, d["profile"], d.get("meta", {}))

seed_demo_data()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "view" not in st.session_state:
    st.session_state.view = "pipeline"
if "active_deal" not in st.session_state:
    st.session_state.active_deal = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_BADGE = {
    "Intake":     '<span class="badge badge-gray">Intake</span>',
    "Extracting": '<span class="badge badge-blue">Extracting</span>',
    "Review":     '<span class="badge badge-orange">Review</span>',
    "Gaps":       '<span class="badge badge-red">Gaps</span>',
    "Ready":      '<span class="badge badge-green">Ready</span>',
    "Submitted":  '<span class="badge badge-gray">Submitted</span>',
    "Approved":   '<span class="badge badge-green">✓ Approved</span>',
    "Rejected":   '<span class="badge badge-red">✗ Rejected</span>',
}

CONF_DOT = {"high": "🟢", "medium": "🟡", "low": "🔴"}

DOC_ICON = {
    "tax_return_personal": "🧾", "tax_return_business": "🏢",
    "bank_statement": "🏦",      "financial_statement": "📊",
    "intake_form": "📋",         "email_notes": "✉️",
    "borrower_profile_json": "🗂️","articles_or_license": "📜",
}


def fmt_amount(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return v or "—"


def generate_package(deal_id, profile):
    paths = {fid: download_form(fid) for fid in ["1919", "413"]}
    files = []
    for i, owner in enumerate(profile.get("owners", [])):
        last = owner.get("last_name", f"owner{i}")
        out1 = os.path.join(OUTPUT_DIR, f"{deal_id}_SBA_1919_{last}.pdf")
        fill_form(paths["1919"], out1, build_1919_fields(profile, i))
        files.append(out1)
        out4 = os.path.join(OUTPUT_DIR, f"{deal_id}_SBA_413_{last}.pdf")
        fill_form(paths["413"], out4, build_413_fields(profile, i))
        files.append(out4)
    return files


def build_zip(files, name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            if os.path.exists(path):
                zf.write(path, os.path.basename(path))
    buf.seek(0)
    return buf.read()

# ---------------------------------------------------------------------------
# View: Pipeline
# ---------------------------------------------------------------------------

def view_pipeline():
    # Header row
    col_h, col_btn = st.columns([5, 1])
    with col_h:
        st.title("Deals")
    with col_btn:
        st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
        if st.button("+ New deal", type="primary", use_container_width=True):
            st.session_state.view = "new_deal"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    deals = list_deals()

    # KPI metrics
    total        = len(deals)
    ready        = sum(1 for d in deals if d["status"] == "Ready")
    gaps         = sum(1 for d in deals if d["status"] == "Gaps")
    urgent       = sum(1 for d in deals if d["urgency"])
    submitted    = sum(1 for d in deals if d["status"] == "Submitted")
    approved     = sum(1 for d in deals if d["status"] == "Approved")
    rejected     = sum(1 for d in deals if d["status"] == "Rejected")
    pipeline_val = sum(d["loan_amount"] or 0 for d in deals if d["status"] not in ("Submitted", "Approved", "Rejected"))
    approved_val = sum(d["loan_amount"] or 0 for d in deals if d["status"] == "Approved")

    # Row 1 — Pipeline stats
    st.markdown(
        f'''<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:12px">
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Total deals</div>
            <div style="font-size:28px;font-weight:800;color:#0D1117;letter-spacing:-0.8px">{total}</div>
        </div>
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Ready to package</div>
            <div style="font-size:28px;font-weight:800;color:#15803D;letter-spacing:-0.8px">{ready}</div>
        </div>
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Needs attention</div>
            <div style="font-size:28px;font-weight:800;color:{"#DC2626" if gaps > 0 else "#0D1117"};letter-spacing:-0.8px">{gaps}</div>
        </div>
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Urgent</div>
            <div style="font-size:28px;font-weight:800;color:{"#D97706" if urgent > 0 else "#0D1117"};letter-spacing:-0.8px">{urgent}</div>
        </div>
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
            <div style="font-size:11px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Pipeline value</div>
            <div style="font-size:28px;font-weight:800;color:#0D1117;letter-spacing:-0.8px">{fmt_amount(pipeline_val)}</div>
        </div>
        </div>''',
        unsafe_allow_html=True,
    )

    # Row 2 — Outcomes (visually distinct dark section)
    st.markdown(
        f'''<div style="background:#0F1122;border-radius:14px;padding:18px 20px;margin-bottom:16px">
        <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:14px">Lender Outcomes</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:14px 18px">
            <div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Submitted</div>
            <div style="font-size:26px;font-weight:800;color:#E2E8F0;letter-spacing:-0.6px">{submitted}</div>
        </div>
        <div style="background:rgba(21,128,61,0.2);border:1px solid rgba(34,197,94,0.25);border-radius:10px;padding:14px 18px">
            <div style="font-size:11px;font-weight:600;color:rgba(134,239,172,0.7);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Approved</div>
            <div style="font-size:26px;font-weight:800;color:#86EFAC;letter-spacing:-0.6px">{approved}</div>
        </div>
        <div style="background:rgba(185,28,28,0.2);border:1px solid rgba(239,68,68,0.25);border-radius:10px;padding:14px 18px">
            <div style="font-size:11px;font-weight:600;color:rgba(252,165,165,0.7);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Rejected</div>
            <div style="font-size:26px;font-weight:800;color:#FCA5A5;letter-spacing:-0.6px">{rejected}</div>
        </div>
        <div style="background:rgba(21,128,61,0.12);border:1px solid rgba(34,197,94,0.15);border-radius:10px;padding:14px 18px">
            <div style="font-size:11px;font-weight:600;color:rgba(134,239,172,0.6);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">Approved value</div>
            <div style="font-size:26px;font-weight:800;color:#86EFAC;letter-spacing:-0.6px">{fmt_amount(approved_val)}</div>
        </div>
        </div></div>''',
        unsafe_allow_html=True,
    )

    # Table header
    hcols = st.columns([3, 2, 2, 2, 2, 1])
    labels = ["Borrower", "Status", "Loan amount", "Readiness", "Documents", ""]
    for col, lbl in zip(hcols, labels):
        col.markdown(f'<div class="col-label">{lbl}</div>', unsafe_allow_html=True)

    # Deal rows
    for deal in deals:
        badge = STATUS_BADGE.get(deal["status"], "")
        urgency_icon = "🚨&nbsp;" if deal["urgency"] else ""
        profile, meta = get_profile(deal["deal_id"])
        score = readiness_score(profile, meta or {}) if profile else 0
        score_color = "#16A34A" if score >= 90 else "#D97706" if score >= 60 else "#DC2626"
        docs = get_documents(deal["deal_id"])

        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 1])
            with c1:
                st.markdown(
                    f'<div class="deal-name">{urgency_icon}{deal["borrower_name"]}</div>'
                    f'<div class="deal-id">{deal["deal_id"]}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(badge, unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="deal-amount">{fmt_amount(deal.get("loan_amount"))}</div>', unsafe_allow_html=True)
            with c4:
                if profile:
                    st.markdown(
                        f'<div style="font-size:13px;font-weight:600;color:{score_color}">{score}%</div>',
                        unsafe_allow_html=True,
                    )
                    st.progress(score / 100)
                else:
                    st.markdown('<span style="color:#9CA3AF;font-size:13px">—</span>', unsafe_allow_html=True)
            with c5:
                st.markdown(f'<div style="font-size:13px;color:#374151;font-weight:500">{len(docs)} file{"s" if len(docs)!=1 else ""}</div>', unsafe_allow_html=True)
                types = list({d["doc_type"] for d in docs if d["doc_type"]})[:2]
                st.markdown(f'<div class="field-source">{", ".join(t.replace("_"," ") for t in types)}</div>', unsafe_allow_html=True)
            with c6:
                if st.button("Open →", key=f"open_{deal['deal_id']}", use_container_width=True):
                    st.session_state.active_deal = deal["deal_id"]
                    st.session_state.view = "deal"
                    st.rerun()

# ---------------------------------------------------------------------------
# View: New Deal
# ---------------------------------------------------------------------------

def view_new_deal():
    if st.button("← Back", key="back_new"):
        st.session_state.view = "pipeline"
        st.rerun()

    st.title("New deal")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("<div style='padding:4px'>", unsafe_allow_html=True)
        with st.form("new_deal_form"):
            name = st.text_input("Business / Borrower name")
            col1, col2 = st.columns(2)
            with col1:
                amount = st.text_input("Loan amount ($)")
            with col2:
                urgent = st.checkbox("Mark as urgent")
            notes = st.text_area("Notes (optional)", height=80)
            submitted = st.form_submit_button("Create deal", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not name:
            st.error("Business name is required.")
        else:
            try:
                loan_amt = float(amount.replace(",","").replace("$","")) if amount else None
            except ValueError:
                loan_amt = None
            deal_id = create_deal(name, loan_amt, notes)
            if urgent:
                set_urgency(deal_id, True)
            st.session_state.active_deal = deal_id
            st.session_state.view = "deal"
            st.rerun()

# ---------------------------------------------------------------------------
# View: Deal Detail
# ---------------------------------------------------------------------------

def view_deal():
    deal_id = st.session_state.active_deal
    deal = get_deal(deal_id)
    if not deal:
        st.error("Deal not found.")
        return

    # Breadcrumb
    col_back, col_head, col_toggle = st.columns([1, 6, 1])
    with col_back:
        if st.button("← Deals"):
            st.session_state.view = "pipeline"
            st.rerun()
    with col_head:
        badge = STATUS_BADGE.get(deal["status"], "")
        urgency = "🚨&nbsp;" if deal["urgency"] else ""
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;padding-top:4px">'
            f'<span style="font-size:20px;font-weight:700;color:#111827">{urgency}{deal["borrower_name"]}</span>'
            f'&nbsp;{badge}'
            f'<span style="font-size:12px;color:#9CA3AF;font-family:monospace">{deal["deal_id"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if deal.get("notes"):
            st.markdown(f'<div style="font-size:12px;color:#9CA3AF;margin-top:2px">{deal["notes"]}</div>', unsafe_allow_html=True)
    with col_toggle:
        new_urgent = st.toggle("Urgent", value=bool(deal["urgency"]))
        if new_urgent != bool(deal["urgency"]):
            set_urgency(deal_id, new_urgent)
            st.rerun()

    # ── Application Decision Banner & Controls ────────────────────
    status = deal["status"]
    if status == "Approved":
        st.markdown(
            '<div style="background:#F0FDF4;border:1.5px solid #86EFAC;border-radius:10px;padding:14px 20px;'
            'display:flex;align-items:center;justify-content:space-between;margin-top:8px">'
            '<div style="display:flex;align-items:center;gap:10px">'
            '<span style="font-size:20px">✅</span>'
            '<div><div style="font-size:14px;font-weight:700;color:#15803D">Application Approved</div>'
            '<div style="font-size:12px;color:#16A34A;margin-top:1px">Lender has approved this application</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    elif status == "Rejected":
        st.markdown(
            '<div style="background:#FEF2F2;border:1.5px solid #FCA5A5;border-radius:10px;padding:14px 20px;'
            'display:flex;align-items:center;justify-content:space-between;margin-top:8px">'
            '<div style="display:flex;align-items:center;gap:10px">'
            '<span style="font-size:20px">❌</span>'
            '<div><div style="font-size:14px;font-weight:700;color:#DC2626">Application Rejected</div>'
            '<div style="font-size:12px;color:#EF4444;margin-top:1px">Lender has declined this application</div></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    elif status == "Submitted":
        st.markdown(
            '<div style="background:#F8FAFC;border:1.5px solid #CBD5E1;border-radius:10px;padding:14px 20px;margin-top:8px">'
            '<div style="font-size:13px;font-weight:600;color:#374151;margin-bottom:10px">📬 Application submitted — record lender decision</div>',
            unsafe_allow_html=True,
        )
        dc1, dc2, dc3 = st.columns([2, 2, 6])
        with dc1:
            if st.button("✓ Mark Approved", type="primary", use_container_width=True):
                update_deal_status(deal_id, "Approved")
                st.rerun()
        with dc2:
            if st.button("✗ Mark Rejected", use_container_width=True):
                update_deal_status(deal_id, "Rejected")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    tab_docs, tab_review, tab_gaps, tab_package, tab_uw = st.tabs([
        "Documents", "Review & Edit", "Gaps", "Package", "Underwriting"
    ])

    # ----------------------------------------------------------------
    # Tab 1 — Documents
    # ----------------------------------------------------------------
    with tab_docs:
        docs = get_documents(deal_id)

        # Summary bar
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:24px;padding:16px 0 8px 0">'
            f'<span style="font-size:22px;font-weight:700;color:#111827">{len(docs)}</span>'
            f'<span style="font-size:13px;color:#6B7280">documents on file</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Doc table header
        hc = st.columns([3, 2, 4, 1])
        for col, lbl in zip(hc, ["File", "Type", "Summary", "Status"]):
            col.markdown(f'<div class="col-label">{lbl}</div>', unsafe_allow_html=True)

        for doc in docs:
            icon = DOC_ICON.get(doc["doc_type"], "📄")
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 4, 1])
                with c1:
                    st.markdown(f'<span style="font-size:13px;font-weight:500;color:#111827">{icon} {doc["filename"]}</span>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'<span style="font-size:12px;color:#6B7280">{(doc["doc_type"] or "").replace("_"," ").title()}</span>', unsafe_allow_html=True)
                with c3:
                    st.markdown(f'<span style="font-size:12px;color:#6B7280">{doc["summary"] or ""}</span>', unsafe_allow_html=True)
                with c4:
                    st.markdown('<span class="badge badge-green">Extracted</span>', unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.info("**Demo mode** — In production, drop any PDF, CSV, or text file here and Claude classifies it, extracts all borrower fields with confidence scores, and merges it into the profile below.")

        with st.expander("How AI extraction works"):
            st.markdown("""
**Upload → Claude classifies the document type** (tax return, bank statement, intake form, etc.)

**Claude extracts every matching field** and tags it:
- 🟢 **High** — from official docs (tax returns, government forms)
- 🟡 **Medium** — from structured intake sheets or CRM exports
- 🔴 **Low** — mentioned in email or call notes

**Conflicts are surfaced**, not silently overwritten. When two docs disagree on the same field, you see both values and choose the correct one in Review & Edit.
            """)

    # ----------------------------------------------------------------
    # Tab 2 — Review & Edit
    # ----------------------------------------------------------------
    with tab_review:
        profile, meta = get_profile(deal_id)
        if not profile:
            st.info("Upload and extract documents first.")
            return

        score = readiness_score(profile, meta or {})
        score_color = "#16A34A" if score >= 90 else "#D97706" if score >= 60 else "#DC2626"

        # Readiness bar
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:16px;padding:8px 0 16px 0">'
            f'<span style="font-size:13px;font-weight:500;color:#6B7280">Profile completeness</span>'
            f'<span style="font-size:22px;font-weight:700;color:{score_color}">{score}%</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.progress(score / 100)
        st.markdown(
            '<div style="font-size:11px;color:#9CA3AF;margin-bottom:16px">'
            '🟢 High confidence &nbsp;&nbsp; 🟡 Medium confidence &nbsp;&nbsp; 🔴 Low confidence &nbsp;&nbsp; ⚠ Conflict — click to resolve'
            '</div>',
            unsafe_allow_html=True,
        )

        biz    = dict(profile.get("business", {}))
        owners = [dict(o) for o in profile.get("owners", [{}])]
        fins   = [dict(f) for f in profile.get("personal_financials", [{}])]
        while len(fins) < len(owners):
            fins.append({})

        def flabel(fk, lbl):
            if meta and fk in meta:
                m = meta[fk]
                dot = CONF_DOT.get(m.get("confidence",""), "")
                warn = " ⚠" if m.get("conflicts") else ""
                return f"{dot} {lbl}{warn}"
            return lbl

        def show_conflict(fk):
            if meta and fk in meta and meta[fk].get("conflicts"):
                conflicts = meta[fk]["conflicts"]
                with st.expander(f"⚠ {len(conflicts)} conflicting value(s)"):
                    for c in conflicts:
                        st.markdown(
                            f'<div style="font-size:12px;padding:6px 0;border-bottom:1px solid #F3F4F6">'
                            f'<code style="background:#F3F4F6;padding:2px 6px;border-radius:4px">{c["value"]}</code>'
                            f' &nbsp;<span style="color:#9CA3AF">({c["confidence"]})</span>'
                            f' from <strong>{c["filename"]}</strong>'
                            f'<br><span style="color:#9CA3AF;font-size:11px">"{c["source_text"][:90]}"</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

        # Business section
        st.markdown('<div class="section-title">Business Information</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<div style='padding:4px 4px 0 4px'>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                biz["legal_name"]            = st.text_input(flabel("business.legal_name","Legal name"),    value=biz.get("legal_name",""),   key="b_ln")
                biz["ein"]                   = st.text_input(flabel("business.ein","EIN"),                  value=biz.get("ein",""),          key="b_ein")
                biz["entity_type"]           = st.selectbox("Entity type",["LLC","S Corp","C Corp","Partnership","Sole Proprietor",""],
                                                index=["LLC","S Corp","C Corp","Partnership","Sole Proprietor",""].index(biz.get("entity_type","")) if biz.get("entity_type","") in ["LLC","S Corp","C Corp","Partnership","Sole Proprietor"] else 5, key="b_et")
                biz["date_established"]      = st.text_input("Date established (MM/DD/YYYY)", value=biz.get("date_established",""), key="b_de")
                biz["state_of_organization"] = st.text_input("State of org", value=biz.get("state_of_organization",""), key="b_soo")
                biz["naics_code"]            = st.text_input("NAICS code",   value=biz.get("naics_code",""),            key="b_naics")
            with col2:
                biz["dba"]           = st.text_input("DBA (if any)",  value=biz.get("dba",""),   key="b_dba")
                biz["phone"]         = st.text_input(flabel("business.phone","Phone"), value=biz.get("phone",""), key="b_ph")
                biz["email"]         = st.text_input("Email",         value=biz.get("email",""), key="b_em")
                biz["num_employees"] = st.text_input("Employees",     value=biz.get("num_employees",""), key="b_emp")
                biz["loan_amount_requested"] = st.text_input(
                    flabel("business.loan_amount_requested","Loan amount ($)"),
                    value=biz.get("loan_amount_requested",""), key="b_la")
                show_conflict("business.loan_amount_requested")
                biz["loan_purpose"] = st.text_input(flabel("business.loan_purpose","Loan purpose"), value=biz.get("loan_purpose",""), key="b_lp")
            c1,c2,c3,c4 = st.columns([3,2,1,1])
            with c1: biz["address_street"] = st.text_input(flabel("business.address_street","Street address"), value=biz.get("address_street",""), key="b_str")
            with c2: biz["address_city"]   = st.text_input("City",  value=biz.get("address_city",""),  key="b_cty")
            with c3: biz["address_state"]  = st.text_input("State", value=biz.get("address_state",""), key="b_st")
            with c4: biz["address_zip"]    = st.text_input("ZIP",   value=biz.get("address_zip",""),   key="b_zip")
            st.markdown("</div>", unsafe_allow_html=True)

        # Owners
        for i, owner in enumerate(owners[:2]):
            name = f"{owner.get('first_name','')} {owner.get('last_name','')}".strip() or f"Owner {i+1}"
            st.markdown(f'<div class="section-title">Owner {i+1} — {name}</div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<div style='padding:4px'>", unsafe_allow_html=True)
                c1,c2,c3 = st.columns(3)
                with c1:
                    owner["first_name"]    = st.text_input("First name",    value=owner.get("first_name",""),    key=f"o{i}_fn")
                    owner["last_name"]     = st.text_input("Last name",     value=owner.get("last_name",""),     key=f"o{i}_ln")
                    owner["title"]         = st.text_input("Title",         value=owner.get("title",""),         key=f"o{i}_ti")
                    owner["ownership_pct"] = st.text_input("Ownership %",   value=owner.get("ownership_pct",""), key=f"o{i}_pct")
                with c2:
                    owner["ssn"]  = st.text_input(flabel(f"owner{i}.ssn","SSN"), value=owner.get("ssn",""), key=f"o{i}_ssn")
                    show_conflict(f"owner{i}.ssn")
                    owner["dob"]  = st.text_input("Date of birth",  value=owner.get("dob",""),  key=f"o{i}_dob")
                    owner["phone"]= st.text_input("Phone",          value=owner.get("phone",""),key=f"o{i}_ph")
                    owner["email"]= st.text_input("Email",          value=owner.get("email",""),key=f"o{i}_em")
                with c3:
                    owner["address_street"] = st.text_input(flabel(f"owner{i}.address_street","Street address"), value=owner.get("address_street",""), key=f"o{i}_str")
                    show_conflict(f"owner{i}.address_street")
                    owner["address_city"]   = st.text_input("City",  value=owner.get("address_city",""),  key=f"o{i}_cty")
                    owner["address_state"]  = st.text_input("State", value=owner.get("address_state",""), key=f"o{i}_sta")
                    owner["address_zip"]    = st.text_input("ZIP",   value=owner.get("address_zip",""),   key=f"o{i}_zip")
                st.markdown('<div style="font-size:12px;font-weight:500;color:#6B7280;text-transform:uppercase;letter-spacing:0.06em;margin:12px 0 8px 0">Disclosures</div>', unsafe_allow_html=True)
                dc1,dc2 = st.columns(2)
                with dc1:
                    owner["us_citizen"]           = st.checkbox("U.S. Citizen / Lawful Resident", value=bool(owner.get("us_citizen",True)),  key=f"o{i}_cit")
                    owner["criminal_history"]      = st.checkbox("Criminal history (felony)",      value=bool(owner.get("criminal_history",False)), key=f"o{i}_crim")
                    owner["currently_incarcerated"]= st.checkbox("Currently incarcerated",         value=bool(owner.get("currently_incarcerated",False)), key=f"o{i}_inc")
                with dc2:
                    owner["probation_parole"]       = st.checkbox("Probation or parole",   value=bool(owner.get("probation_parole",False)),  key=f"o{i}_prob")
                    owner["prior_sba_loan"]         = st.checkbox("Prior SBA loan",        value=bool(owner.get("prior_sba_loan",False)),    key=f"o{i}_sba")
                    owner["delinquent_federal_debt"]= st.checkbox("Delinquent federal debt",value=bool(owner.get("delinquent_federal_debt",False)), key=f"o{i}_fed")
                st.markdown("</div>", unsafe_allow_html=True)

        # Financials
        for i, owner in enumerate(owners[:2]):
            fin  = fins[i] if i < len(fins) else {}
            name = f"{owner.get('first_name','')} {owner.get('last_name','')}".strip() or f"Owner {i+1}"
            st.markdown(f'<div class="section-title">Personal Financials — {name}</div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<div style='padding:4px'>", unsafe_allow_html=True)
                fin["as_of_date"] = st.text_input("As of date (MM/DD/YYYY)", value=fin.get("as_of_date",""), key=f"f{i}_aod")
                st.markdown('<div style="font-size:12px;font-weight:500;color:#6B7280;text-transform:uppercase;letter-spacing:0.06em;margin:10px 0 6px 0">Assets</div>', unsafe_allow_html=True)
                c1,c2,c3 = st.columns(3)
                with c1:
                    fin["cash_and_savings"] = st.text_input(flabel(f"fin{i}.cash_and_savings","Cash & savings ($)"), value=fin.get("cash_and_savings","0"), key=f"f{i}_cash")
                    fin["ira_401k"]         = st.text_input("IRA / 401k ($)", value=fin.get("ira_401k","0"), key=f"f{i}_ira")
                with c2:
                    fin["real_estate_value"] = st.text_input("Real estate ($)", value=fin.get("real_estate_value","0"), key=f"f{i}_rev")
                    fin["auto_value"]        = st.text_input("Vehicles ($)",    value=fin.get("auto_value","0"),        key=f"f{i}_av")
                with c3:
                    fin["other_assets"] = st.text_input("Other assets ($)", value=fin.get("other_assets","0"), key=f"f{i}_oa")
                st.markdown('<div style="font-size:12px;font-weight:500;color:#6B7280;text-transform:uppercase;letter-spacing:0.06em;margin:10px 0 6px 0">Liabilities</div>', unsafe_allow_html=True)
                c1,c2,c3 = st.columns(3)
                with c1: fin["real_estate_mortgage"] = st.text_input("Mortgage ($)",    value=fin.get("real_estate_mortgage","0"), key=f"f{i}_mort")
                with c2: fin["auto_loan_balance"]    = st.text_input("Auto loan ($)",   value=fin.get("auto_loan_balance","0"),    key=f"f{i}_auto")
                with c3: fin["credit_cards_balance"] = st.text_input("Credit cards ($)",value=fin.get("credit_cards_balance","0"),key=f"f{i}_cc")
                st.markdown('<div style="font-size:12px;font-weight:500;color:#6B7280;text-transform:uppercase;letter-spacing:0.06em;margin:10px 0 6px 0">Income</div>', unsafe_allow_html=True)
                c1,c2,c3 = st.columns(3)
                with c1: fin["annual_salary"]      = st.text_input(flabel(f"fin{i}.annual_salary","Annual salary ($)"), value=fin.get("annual_salary","0"), key=f"f{i}_sal")
                with c2: fin["other_income"]       = st.text_input("Other income ($)",  value=fin.get("other_income","0"),        key=f"f{i}_oi")
                with c3: fin["other_income_source"]= st.text_input("Income source",     value=fin.get("other_income_source",""),  key=f"f{i}_ois")
                try:
                    assets = sum(float(fin.get(k,"0") or "0") for k in ["cash_and_savings","ira_401k","real_estate_value","auto_value","other_assets"])
                    liabs  = sum(float(fin.get(k,"0") or "0") for k in ["real_estate_mortgage","auto_loan_balance","credit_cards_balance"])
                    nw = assets - liabs
                    nw_color = "#16A34A" if nw > 0 else "#DC2626"
                    st.markdown(
                        f'<div style="background:#F9FAFB;border-radius:7px;padding:10px 14px;margin-top:8px;display:flex;gap:32px">'
                        f'<span style="font-size:12px;color:#6B7280">Net worth: <strong style="color:{nw_color}">${nw:,.0f}</strong></span>'
                        f'<span style="font-size:12px;color:#6B7280">Assets: <strong>${assets:,.0f}</strong></span>'
                        f'<span style="font-size:12px;color:#6B7280">Liabilities: <strong>${liabs:,.0f}</strong></span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                except ValueError:
                    pass
                if i < len(fins):
                    fins[i] = fin
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Save profile", type="primary"):
            profile["business"]            = biz
            profile["owners"]              = [o for o in owners if o]
            profile["personal_financials"] = [f for f in fins if f]
            save_profile(deal_id, profile, meta or {})
            gaps = detect_gaps(profile, meta or {}, run_ai=False)
            blocking = [g for g in gaps if g["severity"] == "blocking"]
            update_deal_status(deal_id, "Gaps" if blocking else "Review")
            st.success("Profile saved.")
            st.rerun()

    # ----------------------------------------------------------------
    # Tab 3 — Gaps
    # ----------------------------------------------------------------
    with tab_gaps:
        profile, meta = get_profile(deal_id)
        if not profile:
            st.info("Build a profile first.")
            return

        gaps  = detect_gaps(profile, meta or {}, run_ai=False)
        score = readiness_score(profile, meta or {})
        score_color = "#16A34A" if score >= 90 else "#D97706" if score >= 60 else "#DC2626"

        # Score header
        col_score, col_bar = st.columns([1, 4])
        with col_score:
            st.markdown(
                f'<div style="font-size:42px;font-weight:700;color:{score_color};line-height:1">{score}%</div>'
                f'<div style="font-size:12px;color:#9CA3AF;margin-top:2px">Readiness</div>',
                unsafe_allow_html=True,
            )
        with col_bar:
            st.markdown("<div style='padding-top:14px'>", unsafe_allow_html=True)
            st.progress(score / 100)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        if not gaps:
            st.success("✅ No gaps detected — this deal is ready to package.")
            update_deal_status(deal_id, "Ready")
        else:
            blocking = [g for g in gaps if g["severity"] == "blocking"]
            warnings = [g for g in gaps if g["severity"] == "warning"]
            infos    = [g for g in gaps if g["severity"] == "info"]

            if blocking:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:600;color:#DC2626;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">'
                    f'🔴 Blocking · {len(blocking)} issue{"s" if len(blocking)!=1 else ""} — must resolve before packaging</div>',
                    unsafe_allow_html=True,
                )
                for g in blocking:
                    with st.container(border=True):
                        st.markdown(f'<div style="font-size:13px;font-weight:500;color:#111827;padding:2px 0">{g["message"]}</div>', unsafe_allow_html=True)
                        if g.get("tip"):
                            st.markdown(f'<div style="font-size:12px;color:#6B7280;margin-top:3px">{g["tip"]}</div>', unsafe_allow_html=True)

            if warnings:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:600;color:#D97706;text-transform:uppercase;letter-spacing:0.08em;margin:16px 0 8px 0">'
                    f'🟡 Warnings · {len(warnings)}</div>',
                    unsafe_allow_html=True,
                )
                for g in warnings:
                    with st.container(border=True):
                        st.markdown(f'<div style="font-size:13px;color:#374151;padding:2px 0">{g["message"]}</div>', unsafe_allow_html=True)
                        if g.get("tip"):
                            st.markdown(f'<div style="font-size:12px;color:#6B7280;margin-top:3px">{g["tip"]}</div>', unsafe_allow_html=True)

            if infos:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:600;color:#1D4ED8;text-transform:uppercase;letter-spacing:0.08em;margin:16px 0 8px 0">'
                    f'🔵 Info · {len(infos)}</div>',
                    unsafe_allow_html=True,
                )
                for g in infos:
                    st.markdown(f'<div style="font-size:13px;color:#374151;padding:4px 0">— {g["message"]}</div>', unsafe_allow_html=True)

        # AI check demo
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        with st.expander("🤖 AI soft-issue check (demo)"):
            st.markdown('<div style="font-size:12px;color:#9CA3AF;margin-bottom:8px">In production, Claude reviews the full profile for logic issues and lender risk flags beyond rule-based checks. Example:</div>', unsafe_allow_html=True)
            if deal["borrower_name"] == "Sunrise Wellness Studio":
                st.markdown("""
<div style='font-size:13px;color:#374151;line-height:1.6'>
<span class='badge badge-yellow'>Warning</span>&nbsp; Business established June 2025 (8 months ago). SBA lenders typically prefer 2+ years. This deal will likely require a strong business plan and personal collateral.<br><br>
<span class='badge badge-blue'>Info</span>&nbsp; Owner annual salary is $0 and business has no profit history. Underwriter will ask how living expenses are covered. Recommend documenting savings runway or spousal income.
</div>
                """, unsafe_allow_html=True)
            elif deal["borrower_name"] == "Gulf Coast Transport Inc":
                st.markdown("""
<div style='font-size:13px;color:#374151;line-height:1.6'>
<span class='badge badge-yellow'>Warning</span>&nbsp; Loan amount $490K is just $10K under the Express cap of $500K. Confirm this is intentional — amounts at or above the cap require standard 7(a) processing.<br><br>
<span class='badge badge-blue'>Info</span>&nbsp; Both owners have a prior SBA loan. Confirm the prior loan is in good standing — lender will pull CAIVRS.
</div>
                """, unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:13px;color:#6B7280">No additional issues found.</div>', unsafe_allow_html=True)

    # ----------------------------------------------------------------
    # Tab 4 — Package
    # ----------------------------------------------------------------
    with tab_package:
        profile, meta = get_profile(deal_id)
        if not profile:
            st.info("Build a profile first.")
            return

        gaps     = detect_gaps(profile, meta or {}, run_ai=False)
        blocking = [g for g in gaps if g["severity"] == "blocking"]
        score    = readiness_score(profile, meta or {})

        # Status banner
        if blocking:
            st.error(f"⛔ {len(blocking)} blocking issue(s) must be resolved before packaging. Go to the Gaps tab.")
        else:
            st.success(f"✅ Profile is {score}% complete — ready to generate the lender package.")

        col1, col2 = st.columns([2, 4])
        with col1:
            gen_btn = st.button("Generate package", type="primary",
                                use_container_width=True, disabled=bool(blocking))

        if gen_btn:
            with st.spinner("Filling SBA forms..."):
                try:
                    files = generate_package(deal_id, profile)
                    profile_path = os.path.join(OUTPUT_DIR, f"{deal_id}_borrower_profile.json")
                    with open(profile_path, "w") as f:
                        json.dump(profile, f, indent=2)
                    files.append(profile_path)
                    save_package(deal_id, files)
                    update_deal_status(deal_id, "Ready")
                    st.success(f"Package generated — {len(files)} files ready to download.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # Past packages
        packages = get_packages(deal_id)
        if packages:
            st.markdown('<div class="section-title" style="margin-top:24px">Generated packages</div>', unsafe_allow_html=True)
            for pkg in packages:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f'<div style="font-size:13px;font-weight:600;color:#111827">{pkg["package_id"]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div style="font-size:12px;color:#9CA3AF">{pkg["generated_at"][:16]}  ·  {len(pkg["files"])} files</div>', unsafe_allow_html=True)
                    with c2:
                        zip_bytes = build_zip(pkg["files"], deal["borrower_name"])
                        st.download_button("⬇ Download ZIP", data=zip_bytes,
                            file_name=f"{deal_id}_lender_package.zip", mime="application/zip",
                            use_container_width=True, key=f"dl_{pkg['package_id']}")
                    with c3:
                        if deal["status"] != "Submitted":
                            if st.button("Mark as submitted", key=f"sub_{pkg['package_id']}", use_container_width=True):
                                update_deal_status(deal_id, "Submitted")
                                st.rerun()

        # Document checklist
        st.markdown('<div class="section-title" style="margin-top:24px">Document checklist</div>', unsafe_allow_html=True)
        docs = get_documents(deal_id)
        doc_types_have = {d["doc_type"] for d in docs if d["doc_type"]}
        checklist = [
            ("tax_return_personal", "Personal tax returns (3 years)", True),
            ("tax_return_business", "Business tax returns (2–3 years)", True),
            ("bank_statement",      "Business bank statements (3–6 months)", True),
            ("financial_statement", "YTD profit & loss + balance sheet", True),
            ("articles_or_license","Articles of organization / business license", False),
            ("intake_form",        "Completed credit application", False),
        ]
        with st.container(border=True):
            for doc_type, label, required in checklist:
                have = doc_type in doc_types_have
                icon = "✅" if have else ("🔴" if required else "⬜")
                note = "&nbsp;&nbsp;<span style='color:#DC2626;font-size:11px'>required</span>" if required and not have else ""
                st.markdown(
                    f'<div style="display:flex;align-items:center;padding:10px 16px;border-bottom:1px solid #F3F4F6;font-size:13px;color:{"#374151" if have else "#111827"}">'
                    f'{icon}&nbsp;&nbsp;{label}{note}</div>',
                    unsafe_allow_html=True,
                )

    # ----------------------------------------------------------------
    # Tab 5 — Underwriting
    # ----------------------------------------------------------------
    with tab_uw:
        profile, meta = get_profile(deal_id)

        st.markdown('<div class="section-title">Underwriting Score</div>', unsafe_allow_html=True)
        st.caption("We are a broker, not a lender. This score pre-qualifies the file and estimates lender approval probability based on SBA SOP 50 10 8 — the banking partner makes the final credit decision.")

        already_scored = st.session_state.get(f"uw_scored_{deal_id}")

        # ── Input form ──────────────────────────────────────────────
        with st.expander("Underwriting Inputs" + (" ✓" if already_scored else " — fill in to generate score"), expanded=not already_scored):
            with st.form(f"uw_form_{deal_id}"):

                # ── SECTION 1: Eligibility Hard Stops ─────────────
                st.markdown("#### Eligibility — Hard Stops")
                st.caption("Any checked item triggers an automatic decline before scoring. Verify these first.")
                hs1, hs2, hs3 = st.columns(3)
                with hs1:
                    delinquent   = st.checkbox("Delinquent federal debt", help="Any current unpaid debt to the federal government (IRS, SBA, student loans, etc.)")
                    federal_debar = st.checkbox("Federal debarment/suspension", help="Principal or business is currently debarred or suspended from federal programs")
                    active_bk    = st.checkbox("Active bankruptcy", help="Open bankruptcy proceeding for the business or any principal")
                with hs2:
                    prior_default   = st.checkbox("Prior SBA default (with loss)", help="Previous SBA loan that resulted in a federal guaranty loss")
                    incarcerated    = st.checkbox("Currently incarcerated / on probation or parole", help="Any principal is currently incarcerated, on probation, or on parole — hard stop per SOP")
                    pending_ind     = st.checkbox("Pending felony indictment", help="Outstanding indictment against any principal, even without conviction")
                with hs3:
                    illegal_biz     = st.checkbox("Illegal business activity", help="Any portion of operations is illegal under federal, state, or local law (includes cannabis)")
                    ineligible_type = st.checkbox("Ineligible business type", help="Nonprofit, passive investment entity, financial business (bank/lender), gambling >1/3 revenue, pyramid scheme, etc.")
                    citizenship_fail = st.checkbox("Citizenship/residency failure", help="<95% ownership by U.S. citizens, nationals, or lawful permanent residents (SOP 50 10 8, effective Jan 1, 2026)")
                    sba_cap         = st.checkbox("SBA Express cap exceeded", help="Outstanding SBA Express balance + this loan > $500K")

                st.divider()

                # ── SECTION 2: Credit Profile ─────────────────────
                st.markdown("#### Credit Profile")
                cc1, cc2, cc3 = st.columns(3)
                with cc1:
                    fico_tier = st.selectbox("Personal FICO (Primary Guarantor)", [
                        "", "760+", "740-759", "720-739", "700-719",
                        "680-699", "660-679", "650-659", "below_650"
                    ], help="Personal credit score of primary guarantor. Single strongest predictor.")
                with cc2:
                    sbss_tier = st.selectbox("FICO SBSS Score", [
                        "", "above_220", "200-220", "180-199", "165-179", "below_165"
                    ], help="SBA Small Business Scoring Service (0–300). SBA minimum: 165. PLP lenders prefer 180+. Combines personal + business credit + financials.")
                with cc3:
                    paydex_tier = st.selectbox("D&B Paydex / Business Credit", [
                        "", "80+", "70-79", "50-69", "below_50"
                    ], help="D&B Paydex business payment score (0–100). 80+ = pays on time.")

                cf1, cf2, cf3, cf4 = st.columns(4)
                with cf1:
                    open_collections = st.checkbox("Open collections on credit report", help="Number, recency, dollar amount matter — lender will require explanation")
                with cf2:
                    tax_liens = st.checkbox("Tax liens (federal or state)", help="Active tax liens. May constitute delinquent federal debt if IRS lien.")
                with cf3:
                    bk_discharged = st.checkbox("Prior bankruptcy (discharged)")
                with cf4:
                    criminal = st.checkbox("Criminal history disclosed", help="Not auto-decline but requires SBA Form 912 and lender evaluation")

                years_since_bk = 0
                if bk_discharged:
                    years_since_bk = st.slider("Years since bankruptcy discharge", 0, 15, 3,
                        help="SBA minimum: 2 years. Most PLP lenders: 3–5 years. Some require 7+.")

                st.divider()

                # ── SECTION 3: Financial Performance ─────────────
                st.markdown("#### Financial Performance")
                fp1, fp2, fp3 = st.columns(3)
                with fp1:
                    dscr_entity = st.selectbox("DSCR — Entity Level", [
                        "", "above_1.5", "1.35-1.5", "1.25-1.35",
                        "1.15-1.25", "1.0-1.15", "below_1.0"
                    ], help="Business-level: Net Operating Income ÷ Total Business Debt Service. SBA min: 1.10x")
                with fp2:
                    dscr_global = st.selectbox("DSCR — Global Cash Flow", [
                        "", "above_1.5", "1.35-1.5", "1.25-1.35",
                        "1.10-1.25", "1.0-1.10", "below_1.0"
                    ], help="Consolidates ALL income (all businesses, W-2, rental) minus ALL obligations (all debt, personal living expenses, taxes). SOP 50 10 8 required. SBA min: 1.10x")
                with fp3:
                    leverage_tier = st.selectbox("Debt-to-Tangible Net Worth", [
                        "", "below_1", "1-2", "2-3", "3-4", "4-5", "above_5"
                    ], help="Total Liabilities ÷ (Equity − Intangibles). Above 4:1 is a significant red flag. Required in credit memo by SOP 50 10 8.")

                fp4, fp5, fp6 = st.columns(3)
                with fp4:
                    current_ratio = st.selectbox("Current Ratio (Working Capital)", [
                        "", "above_2", "1.5-2", "1.25-1.5", "1.0-1.25", "below_1"
                    ], help="Current Assets ÷ Current Liabilities. Below 1.0 = cannot cover short-term obligations.")
                with fp5:
                    rev_trend = st.selectbox("Revenue Trend (2–3 Year)", [
                        "", "strong_growth", "moderate_growth", "flat",
                        "slight_decline", "significant_decline"
                    ], format_func=lambda x: x.replace("_"," ").title() if x else "",
                    help="Year-over-year revenue change across most recent tax years. Required trend analysis in credit memo.")
                with fp6:
                    concentration = st.selectbox("Revenue Concentration Risk", [
                        "", "none", "moderate", "significant", "highly_concentrated"
                    ], format_func=lambda x: x.replace("_"," ").title() if x else "",
                    help="Single customer dependency. >25% concentration is a risk flag most lenders document.")

                fflag1, fflag2 = st.columns(2)
                with fflag1:
                    nsf_overdrafts = st.checkbox("NSF/overdrafts in bank statements", help="SOP 50 10 8 requires 2 months bank statements. Frequent overdrafts signal cash management issues.")
                with fflag2:
                    proceeds_eligible = st.selectbox("Use of Proceeds", [
                        "eligible", "ineligible_or_unclear"
                    ], format_func=lambda x: "Eligible SBA purpose" if x == "eligible" else "Ineligible or unclear",
                    help="All proceeds must map to eligible SBA uses: working capital, equipment, real estate, acquisition, eligible refinancing.")

                st.divider()

                # ── SECTION 4: Business Profile ───────────────────
                st.markdown("#### Business Profile")
                bp1, bp2, bp3 = st.columns(3)
                with bp1:
                    business_age_tier = st.selectbox("Business Age", [
                        "", "10+", "5-10", "3-5", "2-3", "1-2", "under_1"
                    ], help="Years in operation. Under 2 years = start-up, requiring projections + equity injection.")
                with bp2:
                    industry = st.selectbox("Industry", [
                        "", "healthcare", "professional_services", "technology",
                        "manufacturing", "wholesale", "education", "transportation",
                        "retail", "construction", "restaurant_food_service", "other", "gambling_adult"
                    ], format_func=lambda x: x.replace("_"," ").title() if x else "")
                with bp3:
                    loan_purpose = st.selectbox("Loan Purpose", [
                        "", "working_capital", "equipment", "real_estate",
                        "acquisition", "refinance", "other"
                    ], format_func=lambda x: x.replace("_"," ").title() if x else "")

                bflag1, bflag2, bflag3 = st.columns(3)
                with bflag1:
                    is_startup = st.checkbox("Start-up business (<2 years)", help="Requires business plan, financial projections, and 10% equity injection")
                    is_franchise = st.checkbox("Franchise business")
                with bflag2:
                    franchise_listed = False
                    if is_franchise:
                        franchise_listed = st.checkbox("Franchise on SBA Franchise Directory", help="Check sba.gov/franchise-directory. If not listed, requires additional eligibility analysis.")
                with bflag3:
                    existing_sba_bal = st.number_input("Existing SBA guaranteed balance ($)", min_value=0, value=0, step=10000,
                        help="Outstanding SBA balance across all loans from all lenders. Express cap: $500K total.")

                st.divider()

                # ── SECTION 5: Owner & Guarantor ──────────────────
                st.markdown("#### Owner & Guarantor")
                og1, og2, og3 = st.columns(3)
                with og1:
                    exp_tier = st.selectbox("Owner Industry Experience", [
                        "", "10+", "5-10", "3-5", "1-3", "under_1"
                    ], help="Direct management and industry experience of primary guarantor.")
                with og2:
                    net_worth_tier = st.selectbox("Personal Net Worth (Form 413)", [
                        "", "strong_positive", "moderate_positive", "slight_positive",
                        "near_zero", "negative"
                    ], format_func=lambda x: {
                        "strong_positive": "Strong positive (>2x loan amount)",
                        "moderate_positive": "Moderate positive (>loan amount)",
                        "slight_positive": "Slight positive (<loan amount)",
                        "near_zero": "Near zero (<$25K)",
                        "negative": "Negative net worth",
                    }.get(x, x) if x else "",
                    help="From SBA Form 413. Negative net worth = personal guarantee has limited practical value.")
                with og3:
                    citizenship = st.selectbox("Citizenship / Residency Status", [
                        "citizen", "lpr", "other"
                    ], format_func=lambda x: {
                        "citizen": "U.S. Citizen or National",
                        "lpr": "Lawful Permanent Resident (LPR)",
                        "other": "Other (visa holder, etc.)",
                    }.get(x, x),
                    help="As of Jan 1, 2026: ≥95% ownership must be held by U.S. citizens, nationals, or LPRs. Other status = hard stop.")

                of1, of2 = st.columns(2)
                with of1:
                    key_person = st.checkbox("Key person risk (single owner, business depends on them)",
                        help="Triggers life insurance requirement if loan not fully collateralized per SOP 50 10 8.")
                with of2:
                    equity_injection = st.checkbox("10% equity injection available (start-up/acquisition)",
                        help="Required for start-ups and change-of-ownership. Must come from borrower's own funds or eligible seller note on full standby.")

                st.divider()

                # ── SECTION 6: Collateral ─────────────────────────
                st.markdown("#### Collateral")
                st.caption("SOP 50 10 8: loans over $50K must be collateralized to maximum extent possible. SBA discount rates: real estate 85%, new equipment 75%, used equipment 50%, furniture/fixtures 10%, inventory/AR 10%.")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    collateral_avail = st.checkbox("Collateral available", value=False)
                with col_b:
                    collateral_type = st.selectbox("Collateral type", [
                        "none", "real_estate", "equipment", "other"
                    ], format_func=lambda x: x.replace("_"," ").title())
                with col_c:
                    loan_amount_input = st.number_input("Loan amount requested ($)", min_value=0, value=250000, step=10000)

                submitted = st.form_submit_button("Run Underwriting Score", type="primary", use_container_width=True)

            if submitted:
                citizenship_fail_derived = (citizenship == "other")
                sba_cap_exceeded = existing_sba_bal + loan_amount_input > 500000

                inputs = {
                    # Hard stops
                    "delinquent_federal_debt":    delinquent,
                    "federal_debarment":          federal_debar,
                    "active_bankruptcy":          active_bk,
                    "prior_sba_default":          prior_default,
                    "currently_incarcerated":     incarcerated,
                    "pending_indictment":         pending_ind,
                    "illegal_business":           illegal_biz,
                    "ineligible_business_type":   ineligible_type,
                    "citizenship_failure":        citizenship_fail or citizenship_fail_derived,
                    "sba_cap_exceeded":           sba_cap or sba_cap_exceeded,
                    # Credit
                    "fico_tier":                  fico_tier,
                    "sbss_tier":                  sbss_tier,
                    "paydex_tier":                paydex_tier,
                    "open_collections":           open_collections,
                    "tax_liens":                  tax_liens,
                    "bankruptcy_discharged":      bk_discharged,
                    "years_since_bankruptcy":     years_since_bk,
                    "criminal_history":           criminal,
                    # Financial
                    "dscr_entity_tier":           dscr_entity,
                    "dscr_global_tier":           dscr_global,
                    "leverage_tier":              leverage_tier,
                    "current_ratio_tier":         current_ratio,
                    "revenue_trend":              rev_trend,
                    "revenue_concentration":      concentration,
                    "nsf_overdrafts":             nsf_overdrafts,
                    "use_of_proceeds_eligible":   proceeds_eligible == "eligible",
                    # Business
                    "business_age_tier":          business_age_tier,
                    "industry":                   industry,
                    "loan_purpose":               loan_purpose,
                    "is_startup":                 is_startup,
                    "is_franchise":               is_franchise,
                    "franchise_on_sba_directory": franchise_listed,
                    "existing_sba_balance":       existing_sba_bal,
                    # Owner
                    "experience_tier":            exp_tier,
                    "net_worth_tier":             net_worth_tier,
                    "equity_injection_available": equity_injection,
                    "citizenship_status":         citizenship,
                    "key_person_risk":            key_person,
                    # Collateral
                    "collateral_available":       collateral_avail,
                    "collateral_type":            collateral_type,
                    "loan_amount":                loan_amount_input,
                }
                st.session_state[f"uw_result_{deal_id}"] = inputs
                st.session_state[f"uw_scored_{deal_id}"] = True
                st.rerun()

        # ── Results ─────────────────────────────────────────────────
        if st.session_state.get(f"uw_scored_{deal_id}"):
            inputs = st.session_state[f"uw_result_{deal_id}"]
            result = score_application(inputs)

            score     = result["score"]
            tier      = result["tier"]
            color     = result["tier_color"]
            hard_stop = result["hard_stop"]

            COLOR_MAP = {
                "green":  ("#D1FAE5", "#065F46", "#10B981"),
                "blue":   ("#DBEAFE", "#1E40AF", "#3B82F6"),
                "yellow": ("#FEF9C3", "#92400E", "#F59E0B"),
                "orange": ("#FFEDD5", "#9A3412", "#F97316"),
                "red":    ("#FEE2E2", "#991B1B", "#EF4444"),
            }
            bg, text, accent = COLOR_MAP.get(color, COLOR_MAP["red"])

            # Score card
            st.markdown(f"""
            <div style="background:{bg};border:1.5px solid {accent};border-radius:12px;padding:24px 28px;margin-bottom:20px">
                <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px">
                    <div>
                        <div style="font-size:13px;font-weight:600;color:{text};text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">Underwriting Score</div>
                        <div style="font-size:52px;font-weight:800;color:{text};letter-spacing:-2px;line-height:1">{score}</div>
                        <div style="font-size:12px;color:{text};opacity:0.7;margin-top:2px">out of 1,000 · base 500</div>
                    </div>
                    <div style="text-align:right">
                        <div style="background:{accent};color:#fff;font-size:13px;font-weight:700;padding:8px 18px;border-radius:999px;display:inline-block;margin-bottom:8px">{tier}</div>
                        <div style="font-size:12px;color:{text};max-width:300px;line-height:1.5">{result["tier_description"]}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if hard_stop:
                for reason in result["hard_stop_reasons"]:
                    st.error(f"**Hard Stop:** {reason}")
                st.warning("Application cannot proceed. Advise borrower on the specific disqualifying factors above and explore alternative products.")
            else:
                # Recommendation
                st.info(f"**Recommendation:** {result['recommendation']}")

                # Score bar + tier legend
                st.progress(min(score / 1000, 1.0))
                st.markdown(
                    ' &nbsp; '.join([
                        f'<span style="font-size:10px;color:#9CA3AF">{t} ({th}+)</span>'
                        for th, t, _, _ in reversed(TIERS) if th > 0
                    ]),
                    unsafe_allow_html=True
                )

                # Advisory flags
                flags = result.get("flags", [])
                if flags:
                    st.markdown('<div class="section-title" style="margin-top:20px">Advisory Flags</div>', unsafe_allow_html=True)
                    for flag in flags:
                        st.warning(flag)

                # Factor breakdown
                st.markdown('<div class="section-title" style="margin-top:20px">Factor Breakdown</div>', unsafe_allow_html=True)

                # Group by category
                categories = {}
                for f in result["factor_breakdown"]:
                    cat = f.get("category", "Other")
                    categories.setdefault(cat, []).append(f)

                for cat_name, factors in categories.items():
                    cat_total = sum(f["points"] for f in factors)
                    cat_color = "#16A34A" if cat_total > 0 else ("#DC2626" if cat_total < 0 else "#6B7280")
                    cat_str = f"+{cat_total}" if cat_total > 0 else str(cat_total)

                    with st.expander(f"{cat_name}  ·  {cat_str} pts", expanded=True):
                        for f in factors:
                            pts = f["points"]
                            pts_color = "#16A34A" if pts > 0 else ("#DC2626" if pts < 0 else "#6B7280")
                            pts_str = f"+{pts}" if pts > 0 else str(pts)

                            row_cols = st.columns([3, 2, 1, 1])
                            with row_cols[0]:
                                st.markdown(
                                    f'<div style="font-size:13px;font-weight:500;color:#111827;padding:8px 0 2px 0">{f["factor"]}</div>'
                                    f'<div style="font-size:11px;color:#9CA3AF;padding-bottom:8px">{f["note"]}</div>',
                                    unsafe_allow_html=True
                                )
                            row_cols[1].markdown(f'<div style="font-size:13px;color:#374151;padding:8px 0">{f["tier_label"]}</div>', unsafe_allow_html=True)
                            row_cols[2].markdown(f'<div style="font-size:12px;color:#6B7280;padding:8px 0">{f["weight"]}</div>', unsafe_allow_html=True)
                            row_cols[3].markdown(f'<div style="font-size:15px;font-weight:700;color:{pts_color};padding:8px 0;text-align:right">{pts_str}</div>', unsafe_allow_html=True)
                            st.markdown('<hr style="margin:0;border-color:#F3F4F6"/>', unsafe_allow_html=True)

                # Lender routing
                st.markdown('<div class="section-title" style="margin-top:24px">Lender Routing</div>', unsafe_allow_html=True)
                matches = result["lender_matches"]
                if matches:
                    with st.container(border=True):
                        for i, lender in enumerate(matches):
                            cols = st.columns([3, 4, 2])
                            with cols[0]:
                                rank = "⭐ Best Match" if i == 0 else f"Option {i+1}"
                                st.markdown(
                                    f'<div style="font-size:12px;color:#6B7280;padding:10px 0 2px 0">{rank}</div>'
                                    f'<div style="font-size:14px;font-weight:600;color:#111827;padding-bottom:10px">{lender["name"]}</div>',
                                    unsafe_allow_html=True
                                )
                            cols[1].markdown(f'<div style="font-size:12px;color:#6B7280;padding:10px 0">{lender["notes"]}</div>', unsafe_allow_html=True)
                            cols[2].markdown(f'<div style="font-size:12px;color:#374151;padding:10px 0"><strong>Turnaround:</strong><br>{lender["turnaround"]}</div>', unsafe_allow_html=True)
                            if i < len(matches) - 1:
                                st.markdown('<hr style="margin:0;border-color:#F3F4F6"/>', unsafe_allow_html=True)
                else:
                    st.warning("No lender matches at this score. Consider SBA Microloan, CDFI financing, or conventional credit alternatives.")

# ---------------------------------------------------------------------------
# Sidebar + Router
# ---------------------------------------------------------------------------

with st.sidebar:
    # ── Brand header ──────────────────────────────────────────────
    st.markdown(
        '<div style="padding:18px 16px 14px 16px;border-bottom:1px solid rgba(255,255,255,0.07)">'
        '<div style="font-size:22px;font-weight:800;color:#FFFFFF;letter-spacing:-0.6px;line-height:1.1">SBA Loan Officer</div>'
        '<div style="margin-top:5px">'
        '<span style="font-size:10px;font-weight:600;background:rgba(26,86,219,0.35);color:#93C5FD;padding:2px 8px;border-radius:999px;letter-spacing:0.05em;text-transform:uppercase">Demo</span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Prototypes ────────────────────────────────────────────────
    st.markdown(
        '<div style="padding:12px 14px 8px 14px">'
        '<div style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.28);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">Prototypes</div>'
        '<a href="https://anthony-w-hwang.github.io/sba-prequal/chat.html" target="_blank" '
        'style="display:flex;align-items:center;gap:8px;color:rgba(255,255,255,0.65);font-size:13px;font-weight:500;'
        'text-decoration:none;padding:7px 10px;border-radius:7px;transition:background 0.12s;margin-bottom:2px" '
        'onmouseover="this.style.background=\'rgba(255,255,255,0.07)\';this.style.color=\'#fff\'" '
        'onmouseout="this.style.background=\'transparent\';this.style.color=\'rgba(255,255,255,0.65)\'">'
        '💬&nbsp;&nbsp;AI Chat Prequal</a>'
        '<a href="https://anthony-w-hwang.github.io/sba-prequal/prequal.html" target="_blank" '
        'style="display:flex;align-items:center;gap:8px;color:rgba(255,255,255,0.65);font-size:13px;font-weight:500;'
        'text-decoration:none;padding:7px 10px;border-radius:7px;transition:background 0.12s" '
        'onmouseover="this.style.background=\'rgba(255,255,255,0.07)\';this.style.color=\'#fff\'" '
        'onmouseout="this.style.background=\'transparent\';this.style.color=\'rgba(255,255,255,0.65)\'">'
        '📋&nbsp;&nbsp;Prequal Form (v2)</a>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Nav ───────────────────────────────────────────────────────
    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:4px 14px 8px 14px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="padding:0 14px 4px 14px;font-size:10px;font-weight:600;color:rgba(255,255,255,0.28);text-transform:uppercase;letter-spacing:0.1em">Pipeline</div>', unsafe_allow_html=True)

    if st.button("🗂  All deals", use_container_width=True):
        st.session_state.view = "pipeline"
        st.rerun()
    if st.button("＋  New deal", use_container_width=True):
        st.session_state.view = "new_deal"
        st.rerun()

    # ── Recent deals ──────────────────────────────────────────────
    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.07);margin:8px 14px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="padding:0 14px 4px 14px;font-size:10px;font-weight:600;color:rgba(255,255,255,0.28);text-transform:uppercase;letter-spacing:0.1em">Recent deals</div>', unsafe_allow_html=True)

    deals = list_deals()
    for d in deals[:8]:
        dot_color = {"Ready":"#22C55E","Gaps":"#EF4444","Review":"#F59E0B","Submitted":"#6B7280","Intake":"#6B7280","Extracting":"#3B82F6","Approved":"#22C55E","Rejected":"#EF4444"}.get(d["status"],"#6B7280")
        flag = "🚨 " if d["urgency"] else ""
        label = f'{flag}{d["borrower_name"][:22]}'
        if st.button(label, key=f"sb_{d['deal_id']}", use_container_width=True):
            st.session_state.active_deal = d["deal_id"]
            st.session_state.view = "deal"
            st.rerun()


# Router
if st.session_state.view == "pipeline":
    view_pipeline()
elif st.session_state.view == "new_deal":
    view_new_deal()
elif st.session_state.view == "deal":
    view_deal()
