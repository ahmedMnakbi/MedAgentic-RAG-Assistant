# MedAgentic RAG Assistant

MedAgentic RAG Assistant is a FastAPI backend for **medical education and document understanding only**. It uses uploaded medical PDFs, retrieval, and tool-style routes to support source-grounded Q&A, summarization, simplification, quiz generation, prompt enhancement, and PubMed metadata lookup.

## Safety Boundary

- This project is **not** a diagnosis, triage, or treatment tool.
- It must refuse:
  - diagnosis requests
  - medication dosage requests
  - emergency triage requests
  - personalized treatment recommendations
- It is intended for study demos, portfolio use, and educational document analysis.

## v1 Features

- FastAPI backend with Swagger docs
- `GET /health`
- `GET /api/documents`
- `POST /api/documents/upload`
- `POST /api/chat/ask`
- PDF validation, parsing, chunking, embeddings, and Chroma persistence
- Rule-based router for `rag`, `summarize`, `simplify`, `quiz`, `pubmed`, and `prompt_enhance`
- Safety-first refusal logic
- PubMed metadata search via NCBI E-utilities

## Excluded From v1

- frontend
- authentication
- deployment
- LangGraph orchestration
- OCR for scanned PDFs
- multi-user features
- prompts.chat or MCP live integration

## Project Structure

```text
app/
  api/routes/
  clients/
  core/
  prompts/
  schemas/
  services/
  storage/
  utils/
tests/
```

## Environment

Create a `.env` file from `.env.example` and set:

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `NCBI_EMAIL`
- optionally `NCBI_API_KEY`

Recommended: Python 3.12 for the smoothest local experience with the RAG stack.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Open Swagger at `http://127.0.0.1:8000/docs`.

## API Notes

### `POST /api/documents/upload`

- accepts PDF files only
- validates extension, content type when present, size, and PDF signature
- rejects corrupted PDFs and PDFs without extractable text

### `GET /api/documents`

- lists uploaded document metadata

### `POST /api/chat/ask`

Request example:

```json
{
  "question": "Summarize the key points about heart failure from the uploaded document.",
  "mode": "auto",
  "document_ids": null,
  "enhance_prompt": false,
  "top_k": 4
}
```

Possible response statuses:

- `ok`
- `refused`
- `no_source`

No-source behavior:

- if retrieval does not find a useful match, the assistant says the answer was not found in the uploaded documents

## Testing

```bash
pytest
```

## PubMed v1 Scope

PubMed integration is metadata-only in v1:

- PMID
- title
- authors
- journal
- publication date
- PubMed URL

Abstract snippets and synthesis are intentionally deferred to v1.1.
