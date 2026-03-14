# SBA 7(a) Express Loan Application Tools

A suite of Python tools for automating SBA loan application intake, document processing, and form filling. Built with Streamlit and the Anthropic Claude API.

---

## What's in This Project

There are **three separate apps** in this folder, each representing a different approach. You probably want **`app_lo.py`** (the loan officer dashboard).

| File | What it is | Run command |
|------|-----------|-------------|
| `app_lo.py` | **Main app.** Loan officer / bundler pipeline dashboard. Demo mode — no API key needed. | `streamlit run app_lo.py` |
| `app_ai.py` | AI-first borrower intake. Claude interviews a borrower via chat and fills forms automatically. Requires API key. | `streamlit run app_ai.py` |
| `app.py` | Original manual form wizard. No AI — user fills fields step by step. No API key needed. | `streamlit run app.py` |

### Supporting modules (not run directly)

| File | Purpose |
|------|---------|
| `sba_form_filler.py` | Core PDF engine. Downloads SBA forms, maps data fields to actual PDF field names, fills and saves output PDFs. |
| `deal_store.py` | SQLite persistence layer. Stores deals, uploaded documents, borrower profiles, and generated packages in `deals.db`. |
| `lo_extractor.py` | Document extraction engine. Uses Claude to read uploaded PDFs/docs and pull structured borrower fields with confidence scores. |
| `gap_detector.py` | Gap analysis engine. Rule-based + AI checks to find missing fields, inconsistencies, and lender risk flags. Returns a prioritized gap list and a 0–100 readiness score. |

### Data files

| File | Purpose |
|------|---------|
| `deals.db` | SQLite database. Auto-created on first run. Contains all deals, documents, and profiles. |
| `borrower_profile.json` | Example/reference JSON schema for a complete borrower profile. |
| `forms/` | Downloaded SBA PDF templates (Form 1919 and Form 413). Auto-downloaded if missing. |
| `output/` | Filled PDF output files land here. |

---

## Quickstart — Reopening This Project

### Step 1: Open Terminal

```bash
cd "/Users/anthonyhwang/Desktop/Claude Outputs/SBA_Form_Filler"
```

### Step 2: Activate your Python environment (if you use one)

If you set up a virtual environment previously:
```bash
source venv/bin/activate        # macOS/Linux
# or
.\venv\Scripts\activate         # Windows
```

If you don't have one and packages are installed globally, skip this step.

### Step 3: Install dependencies (only needed once, or after a fresh clone)

```bash
pip install streamlit anthropic pdfplumber reportlab fillpdf pdfrw requests
```

> **Note:** `fillpdf` requires `pdftk` to be installed at the OS level for PDF form-filling to work. On macOS: `brew install pdftk-java`. If you only need the demo dashboard (`app_lo.py`) and aren't generating real PDFs, you can skip this.

### Step 4: Run the app you want

**Loan officer dashboard (demo mode, no API key needed):**
```bash
streamlit run app_lo.py
```

**AI borrower intake (requires Anthropic API key):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
streamlit run app_ai.py
```

**Manual form wizard (no API key needed):**
```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

---

## The Loan Officer Dashboard (`app_lo.py`) — Feature Overview

This is the primary tool. It simulates a loan officer's pipeline from intake to package submission.

### Demo mode
The app ships with **4 pre-seeded demo deals** covering every pipeline stage:
- **Apex Roofing LLC** — Status: Ready (urgent flag), single owner, all docs complete
- **Sunrise Wellness Studio** — Status: Gaps, missing SSN, new business (<1yr)
- **Gulf Coast Transport Inc** — Status: Review, 2 owners, near the $500K Express cap
- **Ironwood Fabrication** — Status: Submitted, complete historical deal

No API key is required for demo mode. The demo data is seeded into `deals.db` automatically on first run.

### Pipeline views

**Pipeline view** (`/` home): Kanban-style deal list showing all active deals with status badges, loan amounts, urgency flags, and readiness scores. Click any deal to open it.

**Deal detail view**: 4-tab layout per deal:
1. **Profile** — Merged borrower profile with field-level confidence indicators (high/medium/low) and conflict flags where documents disagreed
2. **Gaps** — Prioritized gap list. Blocking gaps (red) prevent form generation. Warnings (yellow) are lender risk flags. Info gaps are notes.
3. **Documents** — List of uploaded source documents with doc type, extraction status, and summary
4. **Package** — Generated SBA form packages available for download

**New deal view**: Create a deal, upload documents, and trigger AI extraction (requires API key for live extraction; demo mode shows the pre-seeded deals instead).

### Status workflow
```
Intake → Extracting → Review → Gaps → Ready → Submitted
```

---

## Deploying to the Cloud (Sharing a Demo Link)

### Streamlit Community Cloud (free, easiest)

1. Push this folder to a GitHub repository (can be private)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo → set main file to `app_lo.py`
4. Click **Deploy** — you'll get a public URL like `your-app.streamlit.app`

> **Important before deploying:** `fillpdf` requires `pdftk` at the OS level which isn't available on Streamlit Cloud. Since the demo mode doesn't generate real PDFs, wrap the `sba_form_filler` import in a try/except to prevent a crash on load. The import is at the top of `app_lo.py`.

### Railway (more control, free tier)

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Add start command: `streamlit run app_lo.py --server.port $PORT --server.address 0.0.0.0`
4. Deploy — Railway gives you a custom domain

> SQLite (`deals.db`) is ephemeral on all cloud platforms — it resets on each deploy. For a persistent demo, either hardcode the seed data (already done in demo mode) or switch to a hosted Postgres database.

---

## Using the AI Features (Live Mode)

Both `app_ai.py` and the extraction/gap-analysis features in `app_lo.py` require an Anthropic API key.

### Get an API key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account → API Keys → Create Key
3. Copy the key (starts with `sk-ant-`)

### Set the key
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

To make it permanent, add that line to your `~/.zshrc` or `~/.bash_profile`.

### What uses the API
- **`app_ai.py`**: Every chat message calls `claude-opus-4-6` with streaming. The full interview + form submission is roughly $0.05–0.15 per borrower depending on conversation length.
- **`lo_extractor.py`**: Each uploaded document triggers one Claude call to classify and extract fields. ~$0.02–0.10 per document depending on length.
- **`gap_detector.py`**: The AI gap pass calls Claude once per deal review. ~$0.01–0.05.

---

## SBA Forms Reference

| Form | Name | What it covers |
|------|------|---------------|
| SBA Form 1919 | Borrower Information Form | Business details, owner disclosures (criminal history, federal debt, prior SBA loans), loan purpose |
| SBA Form 413 | Personal Financial Statement | Owner's assets, liabilities, income — required for every owner with 20%+ ownership |

Both forms are automatically downloaded from SBA.gov the first time `sba_form_filler.py` runs. They're cached in the `forms/` directory.

### Borrower profile schema

All apps use the same internal data structure:

```json
{
  "business": {
    "legal_name": "Acme LLC",
    "ein": "12-3456789",
    "entity_type": "LLC",
    "date_established": "01/15/2020",
    "state_of_organization": "TX",
    "address_street": "123 Main St",
    "address_city": "Austin",
    "address_state": "TX",
    "address_zip": "78701",
    "phone": "512-555-0100",
    "loan_amount_requested": "250000",
    "loan_purpose": "Equipment purchase"
  },
  "owners": [
    {
      "first_name": "Jane",
      "last_name": "Doe",
      "title": "President",
      "ownership_pct": "100",
      "ssn": "123-45-6789",
      "dob": "01/01/1980",
      "phone": "512-555-0101",
      "address_street": "456 Oak Ave",
      "address_city": "Austin",
      "address_state": "TX",
      "address_zip": "78702",
      "us_citizen": true,
      "criminal_history": false,
      "delinquent_federal_debt": false
    }
  ],
  "personal_financials": [
    {
      "as_of_date": "03/01/2026",
      "cash_and_savings": "50000",
      "ira_401k": "120000",
      "real_estate_value": "400000",
      "real_estate_mortgage": "250000",
      "annual_salary": "150000"
    }
  ]
}
```

---

## Troubleshooting

**App won't start — `ModuleNotFoundError`**
```bash
pip install streamlit anthropic pdfplumber reportlab fillpdf pdfrw requests
```

**`fillpdf` crashes with pdftk error**
Install pdftk: `brew install pdftk-java` (macOS). If you don't need PDF generation, this error only affects the package generation step — everything else still works.

**Demo deals don't show up / database looks empty**
Delete `deals.db` and restart the app. It will re-seed the demo data on first run.
```bash
rm deals.db
streamlit run app_lo.py
```

**Port 8501 already in use**
```bash
streamlit run app_lo.py --server.port 8502
```

**SBA form download fails (404 error)**
SBA.gov occasionally moves their PDF URLs. Open `sba_form_filler.py` and search for `FORM_URLS` — update the URLs to the current SBA.gov links for Form 1919 and Form 413.

**`ANTHROPIC_API_KEY` not set warning in `app_lo.py`**
The demo mode doesn't need a key. Dismiss the warning or set a key if you want live AI extraction/gap analysis.

---

## Architecture Overview

```
app_lo.py  ←→  deal_store.py    (SQLite: deals, docs, profiles, packages)
           ←→  lo_extractor.py  (Claude API: doc classification + field extraction)
           ←→  gap_detector.py  (Rule engine + Claude API: gap analysis)
           ←→  sba_form_filler.py (PDF download + form filling)

app_ai.py  ←→  sba_form_filler.py
               Claude API (streaming chat + tool use)

app.py     ←→  sba_form_filler.py (no AI)
```

The three apps are **independent** — they don't share session state. `deal_store.py` and `sba_form_filler.py` are shared utility modules used by all three.

---

## Requirements

- Python 3.9+
- `streamlit` — UI framework
- `anthropic` — Claude API client
- `pdfplumber` — PDF text extraction
- `fillpdf` + `pdfrw` — PDF form filling
- `reportlab` — PDF generation
- `requests` — HTTP (form downloads)
- `pdftk-java` — OS-level PDF tool (required by fillpdf; install via Homebrew)
