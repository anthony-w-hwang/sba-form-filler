"""
SBA 7(a) Express Loan Application — AI-First Intake
Claude interviews the user conversationally, extracts their data,
and auto-fills SBA Form 1919 and Form 413.

Run with: streamlit run app_ai.py
Requires: ANTHROPIC_API_KEY environment variable
"""

import os
import json
import io
import zipfile
import streamlit as st
import anthropic
from sba_form_filler import (
    download_form,
    build_1919_fields,
    build_413_fields,
    fill_form,
    FORMS_DIR,
    OUTPUT_DIR,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SBA Loan Application",
    page_icon="🏦",
    layout="centered",
)

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are a friendly SBA loan specialist helping a business owner apply for an SBA 7(a) Express loan.

Your job is to conduct a natural, conversational intake interview to collect all the information needed to fill out SBA Form 1919 (Borrower Information) and Form 413 (Personal Financial Statement).

## Your approach
- Be warm and conversational — this is stressful for borrowers, not a bureaucratic form
- Ask questions in a natural order: start with the business, then owners, then financials
- Group related questions together (don't ask one thing at a time robotically)
- When the user gives you a messy answer, extract the structured data yourself — don't make them reformat it
- If something is unclear or seems missing, ask a brief follow-up
- You can make reasonable inferences (e.g., if they say "we formed the LLC in January 2023 in California", fill in entity_type=LLC, state_of_organization=CA, date_established accordingly)

## What you need to collect

**Business info:**
- Legal business name, DBA (if any)
- EIN (xx-xxxxxxx format)
- Entity type (LLC, S Corp, C Corp, Partnership, Sole Proprietor)
- Date established and state of organization
- Business address (street, city, state, zip)
- Business phone and email
- NAICS code or industry description
- Number of current employees
- Loan amount requested and purpose

**For each owner with 20%+ ownership:**
- Full name, title, ownership percentage
- SSN, date of birth
- Home address, phone, email
- US citizen or lawful resident? (yes/no)
- Any criminal history (felony conviction)? (yes/no)
- Currently incarcerated? (yes/no)
- On probation or parole? (yes/no)
- Prior SBA loan? (yes/no)
- Prior SBA loan default? (yes/no)
- Delinquent on any federal debt? (yes/no)

**Personal financials (per owner, for Form 413):**
- As of date
- Cash and savings ($)
- IRA/401k value ($)
- Real estate value and mortgage balance ($)
- Vehicle value and loan balance ($)
- Other assets ($)
- Credit card balance ($)
- Other liabilities ($)
- Annual salary ($)
- Other income and source ($)

## Flow
1. Start by greeting the user and asking about their business
2. Work through the sections naturally
3. Once you have everything, briefly summarize what you've collected and ask them to confirm before submitting
4. After confirmation, call the `submit_borrower_profile` tool with all the data

## Important
- Never ask for SSNs or financial data until the user seems comfortable and you've established rapport
- SSNs and DOBs are sensitive — acknowledge that when you ask for them
- If they don't know a NAICS code, just ask what the business does and you'll figure it out
- Keep responses concise — this is a chat, not an essay"""

# ---------------------------------------------------------------------------
# Tool definition — Claude calls this when it has all the data
# ---------------------------------------------------------------------------

SUBMIT_TOOL = {
    "name": "submit_borrower_profile",
    "description": "Submit the complete borrower profile to generate pre-filled SBA loan application forms. Call this only after confirming all information with the user.",
    "input_schema": {
        "type": "object",
        "required": ["business", "owners", "personal_financials"],
        "properties": {
            "business": {
                "type": "object",
                "description": "Business information",
                "required": ["legal_name", "ein", "entity_type", "date_established",
                             "state_of_organization", "address_street", "address_city",
                             "address_state", "address_zip", "phone",
                             "loan_amount_requested", "loan_purpose"],
                "properties": {
                    "legal_name":           {"type": "string"},
                    "dba":                  {"type": "string"},
                    "ein":                  {"type": "string", "description": "xx-xxxxxxx format"},
                    "entity_type":          {"type": "string", "enum": ["LLC", "S Corp", "C Corp", "Partnership", "Sole Proprietor"]},
                    "date_established":     {"type": "string", "description": "MM/DD/YYYY"},
                    "state_of_organization": {"type": "string", "description": "2-letter state code"},
                    "naics_code":           {"type": "string"},
                    "phone":                {"type": "string"},
                    "email":                {"type": "string"},
                    "address_street":       {"type": "string"},
                    "address_city":         {"type": "string"},
                    "address_state":        {"type": "string"},
                    "address_zip":          {"type": "string"},
                    "num_employees":        {"type": "string"},
                    "fiscal_year_end":      {"type": "string"},
                    "loan_amount_requested": {"type": "string", "description": "Dollar amount as string"},
                    "loan_purpose":         {"type": "string"},
                }
            },
            "owners": {
                "type": "array",
                "description": "All owners with 20%+ ownership",
                "items": {
                    "type": "object",
                    "required": ["first_name", "last_name", "title", "ownership_pct",
                                 "ssn", "dob", "phone", "address_street",
                                 "address_city", "address_state", "address_zip"],
                    "properties": {
                        "first_name":               {"type": "string"},
                        "last_name":                {"type": "string"},
                        "title":                    {"type": "string"},
                        "ownership_pct":            {"type": "string"},
                        "ssn":                      {"type": "string", "description": "xxx-xx-xxxx"},
                        "dob":                      {"type": "string", "description": "MM/DD/YYYY"},
                        "phone":                    {"type": "string"},
                        "email":                    {"type": "string"},
                        "address_street":           {"type": "string"},
                        "address_city":             {"type": "string"},
                        "address_state":            {"type": "string"},
                        "address_zip":              {"type": "string"},
                        "us_citizen":               {"type": "boolean"},
                        "criminal_history":         {"type": "boolean"},
                        "currently_incarcerated":   {"type": "boolean"},
                        "probation_parole":         {"type": "boolean"},
                        "prior_sba_loan":           {"type": "boolean"},
                        "prior_default":            {"type": "boolean"},
                        "delinquent_federal_debt":  {"type": "boolean"},
                    }
                }
            },
            "personal_financials": {
                "type": "array",
                "description": "Personal financial statement for each owner (same order as owners array)",
                "items": {
                    "type": "object",
                    "required": ["as_of_date"],
                    "properties": {
                        "as_of_date":           {"type": "string", "description": "MM/DD/YYYY"},
                        "cash_and_savings":     {"type": "string"},
                        "ira_401k":             {"type": "string"},
                        "real_estate_value":    {"type": "string"},
                        "real_estate_mortgage": {"type": "string"},
                        "auto_value":           {"type": "string"},
                        "auto_loan_balance":    {"type": "string"},
                        "other_assets":         {"type": "string"},
                        "credit_cards_balance": {"type": "string"},
                        "other_liabilities":    {"type": "string"},
                        "annual_salary":        {"type": "string"},
                        "other_income":         {"type": "string"},
                        "other_income_source":  {"type": "string"},
                    }
                }
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "profile" not in st.session_state:
        st.session_state.profile = None
    if "output_files" not in st.session_state:
        st.session_state.output_files = []
    if "stage" not in st.session_state:
        st.session_state.stage = "chat"  # "chat" | "done"

init_state()

# ---------------------------------------------------------------------------
# API key check
# ---------------------------------------------------------------------------

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    st.error("**ANTHROPIC_API_KEY not set.** Add it to your environment before running.")
    api_key = st.text_input("Or paste your API key here (not saved):", type="password")
    if not api_key:
        st.stop()

client = anthropic.Anthropic(api_key=api_key)

# ---------------------------------------------------------------------------
# Form generation
# ---------------------------------------------------------------------------

def generate_forms(profile: dict) -> list[str]:
    """Fill SBA forms from profile and return list of output file paths."""
    os.makedirs(FORMS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    paths = {}
    for form_id in ["1919", "413"]:
        paths[form_id] = download_form(form_id)

    output_files = []
    for i, owner in enumerate(profile["owners"]):
        last = owner.get("last_name", f"owner{i}")
        out_1919 = os.path.join(OUTPUT_DIR, f"SBA_1919_filled_{last}.pdf")
        fill_form(paths["1919"], out_1919, build_1919_fields(profile, i))
        output_files.append(out_1919)

        out_413 = os.path.join(OUTPUT_DIR, f"SBA_413_filled_{last}.pdf")
        fill_form(paths["413"], out_413, build_413_fields(profile, i))
        output_files.append(out_413)

    return output_files


def build_zip(output_files: list, business_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in output_files:
            zf.write(path, os.path.basename(path))
    buf.seek(0)
    return buf.read()

# ---------------------------------------------------------------------------
# Chat response (streaming)
# ---------------------------------------------------------------------------

def get_claude_response(messages: list) -> tuple[str, dict | None]:
    """
    Stream Claude's response. Returns (text_response, tool_input_or_None).
    If Claude calls submit_borrower_profile, returns the tool input as dict.
    """
    with client.messages.stream(
        model=MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[SUBMIT_TOOL],
        thinking={"type": "adaptive"},
        max_tokens=4096,
    ) as stream:
        # Stream text tokens to UI in real time
        response_placeholder = st.empty()
        full_text = ""
        with st.chat_message("assistant"):
            text_container = st.empty()
            for text_chunk in stream.text_stream:
                full_text += text_chunk
                text_container.markdown(full_text + "▌")
            text_container.markdown(full_text)

    final = stream.get_final_message()

    # Check if Claude called the tool
    tool_input = None
    for block in final.content:
        if block.type == "tool_use" and block.name == "submit_borrower_profile":
            tool_input = block.input

    return full_text, tool_input

# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

st.title("🏦 SBA 7(a) Express Loan Application")

if st.session_state.stage == "chat":
    st.caption("Answer a few questions and we'll fill out your SBA forms automatically.")

    # Render conversation history
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            with st.chat_message(role):
                st.markdown(content)

    # Initial greeting if no messages yet
    if not st.session_state.messages:
        greeting = (
            "Hi! I'm here to help you complete your SBA 7(a) Express loan application. "
            "I'll ask you a few questions and then generate your pre-filled forms automatically — "
            "no paperwork required from you.\n\n"
            "Let's start with the basics: **What's the legal name of your business, "
            "and what does it do?**"
        )
        with st.chat_message("assistant"):
            st.markdown(greeting)
        st.session_state.messages.append({"role": "assistant", "content": greeting})

    # User input
    user_input = st.chat_input("Type your answer here...")

    if user_input:
        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Get Claude's response
        response_text, tool_input = get_claude_response(st.session_state.messages)

        # Add assistant response to history
        if response_text:
            st.session_state.messages.append({"role": "assistant", "content": response_text})

        # If Claude submitted the profile, generate forms
        if tool_input:
            st.session_state.profile = tool_input
            with st.spinner("Generating your SBA forms..."):
                try:
                    output_files = generate_forms(tool_input)
                    st.session_state.output_files = output_files
                    st.session_state.stage = "done"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating forms: {e}")

# ---------------------------------------------------------------------------
# Done screen
# ---------------------------------------------------------------------------

elif st.session_state.stage == "done":
    st.success("Your SBA application forms are ready!")

    profile = st.session_state.profile
    biz = profile["business"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Business", biz.get("legal_name", "—"))
    col2.metric("Loan Amount", f"${float(biz.get('loan_amount_requested', 0)):,.0f}")
    col3.metric("Owners", len(profile["owners"]))

    # Download button
    zip_bytes = build_zip(
        st.session_state.output_files,
        biz.get("legal_name", "business")
    )
    st.download_button(
        label="⬇ Download Filled Forms (ZIP)",
        data=zip_bytes,
        file_name=f"SBA_Forms_{biz.get('legal_name','').replace(' ','_')}.zip",
        mime="application/zip",
        use_container_width=True,
    )

    # Review checklist
    st.markdown("---")
    st.subheader("Before you sign and submit")
    st.markdown("""
- [ ] Open each PDF and review all fields — verify names, SSN, addresses, EIN
- [ ] Confirm loan amount and purpose match what you discussed with your lender
- [ ] Check all Yes/No disclosure answers on Form 1919
- [ ] Review asset, liability, and income figures on Form 413
- [ ] Sign and date each form where indicated
- [ ] Attach supporting docs: 3 years tax returns, YTD P&L, balance sheet, business plan

**Do not submit unsigned forms.**
    """)

    st.markdown("---")

    # Show what was collected
    with st.expander("Review extracted data"):
        st.json(profile)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start a new application", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    with col2:
        # Save profile JSON alongside the PDFs
        profile_path = os.path.join(OUTPUT_DIR, "borrower_profile_last.json")
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)
        with open(profile_path) as f:
            st.download_button(
                "⬇ Download profile JSON",
                data=f.read(),
                file_name="borrower_profile.json",
                mime="application/json",
                use_container_width=True,
            )
