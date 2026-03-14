"""
Loan Officer Extractor — lo_extractor.py
Extracts borrower profile fields from uploaded documents using Claude.
Each extracted field carries a confidence score and source text snippet.
"""

import os
import json
import pdfplumber
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ---------------------------------------------------------------------------
# Document types
# ---------------------------------------------------------------------------

DOC_TYPES = [
    "tax_return_personal",       # 1040, Schedule C/E
    "tax_return_business",       # 1120, 1120-S, 1065
    "bank_statement",            # personal or business
    "financial_statement",       # P&L, balance sheet
    "intake_form",               # broker intake sheet, credit app
    "email_notes",               # email thread or call notes
    "borrower_profile_json",     # existing borrower_profile.json
    "articles_or_license",       # articles of incorporation, business license
    "unknown",
]

# ---------------------------------------------------------------------------
# Extraction tool schema
# ---------------------------------------------------------------------------

# Each extractable field from borrower_profile.json is represented here.
# Claude fills in value + confidence + source_text for each it can find.

FIELD_SCHEMA = {
    "type": "object",
    "description": "All fields extracted from the document. Only include fields actually found — omit fields not present in the document.",
    "properties": {
        # Business fields
        "business.legal_name":           {"$ref": "#/$defs/field"},
        "business.dba":                  {"$ref": "#/$defs/field"},
        "business.ein":                  {"$ref": "#/$defs/field"},
        "business.entity_type":          {"$ref": "#/$defs/field"},
        "business.date_established":     {"$ref": "#/$defs/field"},
        "business.state_of_organization":{"$ref": "#/$defs/field"},
        "business.naics_code":           {"$ref": "#/$defs/field"},
        "business.phone":                {"$ref": "#/$defs/field"},
        "business.email":                {"$ref": "#/$defs/field"},
        "business.address_street":       {"$ref": "#/$defs/field"},
        "business.address_city":         {"$ref": "#/$defs/field"},
        "business.address_state":        {"$ref": "#/$defs/field"},
        "business.address_zip":          {"$ref": "#/$defs/field"},
        "business.num_employees":        {"$ref": "#/$defs/field"},
        "business.fiscal_year_end":      {"$ref": "#/$defs/field"},
        "business.loan_amount_requested":{"$ref": "#/$defs/field"},
        "business.loan_purpose":         {"$ref": "#/$defs/field"},
        # Owner fields (first owner — index 0)
        "owner0.first_name":             {"$ref": "#/$defs/field"},
        "owner0.last_name":              {"$ref": "#/$defs/field"},
        "owner0.title":                  {"$ref": "#/$defs/field"},
        "owner0.ownership_pct":          {"$ref": "#/$defs/field"},
        "owner0.ssn":                    {"$ref": "#/$defs/field"},
        "owner0.dob":                    {"$ref": "#/$defs/field"},
        "owner0.phone":                  {"$ref": "#/$defs/field"},
        "owner0.email":                  {"$ref": "#/$defs/field"},
        "owner0.address_street":         {"$ref": "#/$defs/field"},
        "owner0.address_city":           {"$ref": "#/$defs/field"},
        "owner0.address_state":          {"$ref": "#/$defs/field"},
        "owner0.address_zip":            {"$ref": "#/$defs/field"},
        "owner0.us_citizen":             {"$ref": "#/$defs/field"},
        "owner0.criminal_history":       {"$ref": "#/$defs/field"},
        "owner0.delinquent_federal_debt":{"$ref": "#/$defs/field"},
        # Owner 1 (second owner)
        "owner1.first_name":             {"$ref": "#/$defs/field"},
        "owner1.last_name":              {"$ref": "#/$defs/field"},
        "owner1.ownership_pct":          {"$ref": "#/$defs/field"},
        "owner1.ssn":                    {"$ref": "#/$defs/field"},
        "owner1.dob":                    {"$ref": "#/$defs/field"},
        "owner1.phone":                  {"$ref": "#/$defs/field"},
        "owner1.address_street":         {"$ref": "#/$defs/field"},
        "owner1.address_city":           {"$ref": "#/$defs/field"},
        "owner1.address_state":          {"$ref": "#/$defs/field"},
        "owner1.address_zip":            {"$ref": "#/$defs/field"},
        # Personal financials (owner 0)
        "fin0.as_of_date":               {"$ref": "#/$defs/field"},
        "fin0.cash_and_savings":         {"$ref": "#/$defs/field"},
        "fin0.ira_401k":                 {"$ref": "#/$defs/field"},
        "fin0.real_estate_value":        {"$ref": "#/$defs/field"},
        "fin0.real_estate_mortgage":     {"$ref": "#/$defs/field"},
        "fin0.auto_value":               {"$ref": "#/$defs/field"},
        "fin0.auto_loan_balance":        {"$ref": "#/$defs/field"},
        "fin0.other_assets":             {"$ref": "#/$defs/field"},
        "fin0.credit_cards_balance":     {"$ref": "#/$defs/field"},
        "fin0.other_liabilities":        {"$ref": "#/$defs/field"},
        "fin0.annual_salary":            {"$ref": "#/$defs/field"},
        "fin0.other_income":             {"$ref": "#/$defs/field"},
        "fin0.other_income_source":      {"$ref": "#/$defs/field"},
        # Personal financials (owner 1)
        "fin1.as_of_date":               {"$ref": "#/$defs/field"},
        "fin1.cash_and_savings":         {"$ref": "#/$defs/field"},
        "fin1.annual_salary":            {"$ref": "#/$defs/field"},
        "fin1.real_estate_value":        {"$ref": "#/$defs/field"},
        "fin1.real_estate_mortgage":     {"$ref": "#/$defs/field"},
    },
    "$defs": {
        "field": {
            "type": "object",
            "required": ["value", "confidence", "source_text"],
            "properties": {
                "value":       {"type": "string", "description": "The extracted value, normalized (e.g. dates as MM/DD/YYYY, dollar amounts as digits only)"},
                "confidence":  {"type": "string", "enum": ["high", "medium", "low"], "description": "high=from official doc, medium=structured form, low=inferred from narrative"},
                "source_text": {"type": "string", "description": "The exact snippet of text from the document this was extracted from (max 100 chars)"},
            },
            "additionalProperties": False,
        }
    },
    "additionalProperties": False,
}

EXTRACT_TOOL = {
    "name": "extract_borrower_fields",
    "description": "Extract all borrower profile fields found in the document. Only include fields that are explicitly present — do not guess or invent values.",
    "input_schema": FIELD_SCHEMA,
}

CLASSIFY_TOOL = {
    "name": "classify_document",
    "description": "Identify the type of financial/loan document.",
    "input_schema": {
        "type": "object",
        "required": ["doc_type", "summary"],
        "properties": {
            "doc_type": {"type": "string", "enum": DOC_TYPES},
            "summary":  {"type": "string", "description": "1-2 sentence description of what this document is"},
        },
        "additionalProperties": False,
    }
}

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(path: str) -> str:
    """Extract raw text from a PDF file."""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def load_document_text(path: str) -> str:
    """Load document text from a file path. Handles PDF, JSON, and plain text."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext == ".json":
        with open(path) as f:
            data = json.load(f)
        return json.dumps(data, indent=2)
    else:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

# ---------------------------------------------------------------------------
# Classify document
# ---------------------------------------------------------------------------

def classify_document(text: str):
    """
    Returns (doc_type, summary).
    Uses the first 2000 chars — enough to identify the doc type.
    """
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_document"},
        messages=[{
            "role": "user",
            "content": f"Identify this document type:\n\n{text[:2000]}"
        }]
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "classify_document":
            return block.input["doc_type"], block.input["summary"]
    return "unknown", "Could not classify"

# ---------------------------------------------------------------------------
# Extract fields from document
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM = """You are a meticulous SBA loan analyst. Your job is to extract borrower data from financial documents.

Rules:
- Only extract values that are explicitly stated in the document. Never invent or infer values not present.
- Normalize all values: dates as MM/DD/YYYY, dollar amounts as digits only (no $ or commas), SSNs as xxx-xx-xxxx, phone as xxx-xxx-xxxx.
- Confidence levels:
  - high: value comes from an official document (tax return, government form, bank statement header)
  - medium: value comes from a structured form or intake sheet
  - low: value mentioned casually in email, notes, or inferred from context
- source_text: copy the exact phrase from the document (up to 100 chars) that contains this value
- For SSNs: only extract from official documents (tax returns, credit apps). Do NOT extract from email or notes — set confidence=low and source_text to indicate it came from an unofficial source.
- For financial figures: use the most recent year's data if multiple years are present. Note the year in source_text.
- If you find a second owner, use the owner1.* and fin1.* fields."""


def extract_fields(text: str, doc_type: str, filename: str = "") -> dict:
    """
    Extract borrower fields from document text.
    Returns a dict of field_key -> {value, confidence, source_text, doc_type, filename}.
    """
    context = f"Document type: {doc_type}\nFilename: {filename}\n\nDocument content:\n{text[:8000]}"

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=EXTRACTION_SYSTEM,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_borrower_fields"},
        messages=[{"role": "user", "content": context}]
    )

    extracted = {}
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_borrower_fields":
            for field_key, field_data in block.input.items():
                if isinstance(field_data, dict) and "value" in field_data:
                    extracted[field_key] = {
                        **field_data,
                        "doc_type": doc_type,
                        "filename": filename,
                    }
    return extracted

# ---------------------------------------------------------------------------
# Merge extractions from multiple documents
# ---------------------------------------------------------------------------

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

def merge_extractions(extractions: list) -> dict:
    """
    Merge field extractions from multiple documents into a single profile.
    - Higher-confidence sources win.
    - Conflicts (same field, different values) are flagged.
    Returns: {field_key: {value, confidence, source_text, doc_type, filename, conflicts: []}}
    """
    merged = {}

    for doc_fields in extractions:
        for field_key, field_data in doc_fields.items():
            if field_key not in merged:
                merged[field_key] = {**field_data, "conflicts": []}
            else:
                existing = merged[field_key]
                new_rank = CONFIDENCE_RANK.get(field_data["confidence"], 0)
                exist_rank = CONFIDENCE_RANK.get(existing["confidence"], 0)

                # Track conflict if values differ meaningfully
                if field_data["value"].strip().lower() != existing["value"].strip().lower():
                    conflict = {
                        "value":       field_data["value"],
                        "confidence":  field_data["confidence"],
                        "source_text": field_data["source_text"],
                        "doc_type":    field_data["doc_type"],
                        "filename":    field_data["filename"],
                    }
                    existing["conflicts"].append(conflict)

                # Higher confidence wins
                if new_rank > exist_rank:
                    old = {k: existing[k] for k in ["value", "confidence", "source_text", "doc_type", "filename"]}
                    existing["conflicts"].append(old)
                    existing.update({
                        "value":       field_data["value"],
                        "confidence":  field_data["confidence"],
                        "source_text": field_data["source_text"],
                        "doc_type":    field_data["doc_type"],
                        "filename":    field_data["filename"],
                    })

    return merged

# ---------------------------------------------------------------------------
# Convert merged fields → borrower_profile.json structure
# ---------------------------------------------------------------------------

def fields_to_profile(merged: dict) -> dict:
    """
    Convert flat merged field dict to nested borrower_profile.json structure.
    Returns the profile dict with a parallel _meta dict for confidence/source info.
    """
    profile = {"business": {}, "owners": [{}, {}], "personal_financials": [{}, {}]}
    meta = {}

    for field_key, field_data in merged.items():
        parts = field_key.split(".", 1)
        if len(parts) != 2:
            continue
        section, key = parts

        if section == "business":
            profile["business"][key] = field_data["value"]
            meta[field_key] = field_data
        elif section in ("owner0", "owner1"):
            idx = int(section[-1])
            profile["owners"][idx][key] = field_data["value"]
            meta[field_key] = field_data
        elif section in ("fin0", "fin1"):
            idx = int(section[-1])
            profile["personal_financials"][idx][key] = field_data["value"]
            meta[field_key] = field_data

    # Trim empty owners/financials
    profile["owners"] = [o for o in profile["owners"] if o]
    profile["personal_financials"] = [f for f in profile["personal_financials"] if f]

    return profile, meta

# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------

def process_document(path: str, doc_type: str = None) -> dict:
    """
    Full pipeline for a single document:
    1. Load text
    2. Classify (if type not provided)
    3. Extract fields
    Returns: {"doc_type": str, "summary": str, "fields": dict}
    """
    text = load_document_text(path)
    filename = os.path.basename(path)

    if doc_type is None:
        doc_type, summary = classify_document(text)
    else:
        summary = f"Manually specified as {doc_type}"

    # If it's a borrower_profile JSON, parse directly with high confidence
    if doc_type == "borrower_profile_json":
        fields = _extract_from_profile_json(text, filename)
        return {"doc_type": doc_type, "summary": summary, "fields": fields}

    fields = extract_fields(text, doc_type, filename)
    return {"doc_type": doc_type, "summary": summary, "fields": fields}


def _extract_from_profile_json(json_text: str, filename: str) -> dict:
    """Convert a borrower_profile.json directly to annotated fields (all high confidence)."""
    data = json.loads(json_text)
    fields = {}

    biz = data.get("business", {})
    for k, v in biz.items():
        if v:
            fields[f"business.{k}"] = {"value": str(v), "confidence": "high",
                                        "source_text": f"borrower_profile.json business.{k}",
                                        "doc_type": "borrower_profile_json", "filename": filename, "conflicts": []}

    for i, owner in enumerate(data.get("owners", [])[:2]):
        for k, v in owner.items():
            if v is not None and v != "":
                fields[f"owner{i}.{k}"] = {"value": str(v), "confidence": "high",
                                            "source_text": f"borrower_profile.json owners[{i}].{k}",
                                            "doc_type": "borrower_profile_json", "filename": filename, "conflicts": []}

    for i, fin in enumerate(data.get("personal_financials", [])[:2]):
        for k, v in fin.items():
            if v is not None and v != "":
                fields[f"fin{i}.{k}"] = {"value": str(v), "confidence": "high",
                                          "source_text": f"borrower_profile.json personal_financials[{i}].{k}",
                                          "doc_type": "borrower_profile_json", "filename": filename, "conflicts": []}

    return fields


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 lo_extractor.py <path_to_document>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"\nProcessing: {path}")
    result = process_document(path)
    print(f"Doc type:   {result['doc_type']}")
    print(f"Summary:    {result['summary']}")
    print(f"Fields extracted: {len(result['fields'])}\n")
    for key, data in result["fields"].items():
        conflicts = f" ⚠ {len(data['conflicts'])} conflict(s)" if data.get("conflicts") else ""
        print(f"  [{data['confidence'].upper():6}] {key}: {data['value']!r}{conflicts}")
