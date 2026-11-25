# Claims Pre-analysis Agent

A set of document-AI modules that prepare life-insurance claims for the analyst: translating foreign documents, extracting medical records and employment termination terms, cross-checking the claim documents, and checking employer social-security filings (GFIP).

**Stack:** Python · LangGraph · Azure OpenAI (GPT-4.1-mini) · Azure Document Intelligence · Pydantic · pandas · Streamlit
**Role:** Lead developer: design and implementation

> Built at a large Brazilian insurer. The company is replaced by the fictional **Acme Seguros**, and every name, document and data point here is fictional. Code, prompts and UI are in Portuguese, written for Brazilian business teams.

## Problem

Before deciding a claim, analysts read and cross-checked a pile of documents: death certificate, heirs' declaration, IDs, proofs of address, medical records, termination terms and, for group policies, the employer's payroll filings. Some arrived in foreign languages.

## What I built

| Module | What it does |
|---|---|
| Document translation | Translates a foreign-language PDF into Brazilian Portuguese and rebuilds it as a formatted PDF |
| Medical record | Extracts a structured record (Pydantic) from a scanned medical file |
| Termination term | Extracts the employment termination data relevant to the claim |
| Pre-analysis | Runs one extraction agent per document (death certificate, heirs' declaration, ID, proof of address), then checks in code that the fields they share agree, and exports a consolidated spreadsheet |
| GFIP check | Extracts the employee list from the employer's social-security filing (GFIP): general classification, lookup by tax ID or by name, duplicate detection, and a comparison with a sick-leave document |

- **One LangGraph workflow per module** (translation, extraction, comparison, duplicate and formatting nodes).
- **One Pydantic model per document type**, so every extraction has a fixed, checkable shape.
- **OCR page by page** with Document Intelligence, and a time counter per step to track latency.
- The analyst gets a pre-analysis to confirm, not an automatic decision.

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                               # Azure OpenAI + Document Intelligence
streamlit run streamlit_app.py
```

Use fictional sample documents.

---
Part of my [AI engineering portfolio](https://github.com/lucasboliveirasipp).
