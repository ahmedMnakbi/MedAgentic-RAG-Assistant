# MARA

MARA, short for **Medical Agent RAG Assistant**, is a FastAPI project for **medical education and document understanding only**. It lets you upload medical PDFs, retrieve grounded answers from them, summarize or simplify the material, generate study quizzes, search PubMed, compare selected studies, and refine prompts through a simpler Prompt Studio.

`v1.3` adds multi-study PubMed comparison and synthesis, a lighter Prompt Studio, a more interactive web UI, and MARA branding while keeping Swagger at `/docs` for developer testing.

## Safety Boundary

- This project is **not** a diagnosis, dosage, triage, or treatment system.
- It must refuse:
  - diagnosis requests
  - medication dosage requests
  - emergency triage requests
  - personalized treatment recommendations
- It is built for learning, demonstrations, and portfolio use.

## What v1.3 Includes

- FastAPI backend with Swagger docs
- interactive web UI at `/`
- `GET /health`
- `GET /api/documents`
- `POST /api/documents/upload`
- `POST /api/chat/ask`
- `GET /api/prompts/search`
- `GET /api/prompts/{prompt_id}`
- `POST /api/prompts/improve`
- `POST /api/pubmed/transform`
- `POST /api/pubmed/import-url`
- PDF validation, parsing, chunking, embeddings, and Chroma persistence
- rule-based routing for `rag`, `summarize`, `simplify`, `quiz`, `pubmed`, and `prompt_enhance`
- safety-first refusal logic
- PubMed metadata search through NCBI E-utilities
- selected PubMed article summarize / simplify / quiz workflows
- multi-study PubMed comparison and merged synthesis
- PMC full-text fallback when a selected PubMed result has a PMCID
- experimental import of readable open-access article URLs
- internal prompt library and a lighter Prompt Studio inspired by Prompt Finder & Enhancer / prompts.chat

## What v1.3 Still Does Not Include

- authentication
- deployment
- OCR for scanned PDFs
- LangGraph orchestration
- multi-user accounts
- live prompts.chat or MCP dependency
- guaranteed full text for every PubMed article
- publisher-site scraping as a primary workflow

## Interface Map

- Web app: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## High-Level Architecture

```mermaid
flowchart TD
    A["User Web UI / Swagger"] --> B["FastAPI Routes"]
    B --> C["Safety Guardrail"]
    C --> D["Rule-Based Router"]
    D --> E["Document RAG Path"]
    D --> F["PubMed Search + Article Actions"]
    D --> G["Prompt Studio Path"]
    E --> H["PDF Parsing + Chunking"]
    H --> I["Embeddings"]
    I --> J["ChromaDB"]
    J --> K["Retrieved Chunks"]
    K --> L["Groq LLM Response"]
    F --> M["NCBI E-utilities + PMC Full Text"]
    G --> N["Prompt Library + Prompt Improver"]
```

## External Services You Need

- Groq: [https://console.groq.com/](https://console.groq.com/)
  - required for RAG answers, summaries, simplification, quizzes, and live prompt improvement
- PubMed: [https://pubmed.ncbi.nlm.nih.gov/](https://pubmed.ncbi.nlm.nih.gov/)
  - required for literature metadata search
- NCBI E-utilities docs: [https://www.ncbi.nlm.nih.gov/books/NBK25497/](https://www.ncbi.nlm.nih.gov/books/NBK25497/)

## Environment Setup

1. Clone the repository:

```bash
git clone https://github.com/ahmedMnakbi/MedAgentic-RAG-Assistant.git
cd MedAgentic-RAG-Assistant
```

2. Create a virtual environment:

```bash
python -m venv .venv
```

3. Activate it on Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Create a local env file:

```bash
Copy-Item .env.example .env
```

6. Open `.env` and set:

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `NCBI_EMAIL`
- optionally `NCBI_API_KEY`

Recommended runtime: Python `3.12`.

## Run The App

```bash
uvicorn app.main:app --reload
```

Then open:

- web app: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

The first PDF upload on a fresh machine can still take longer because the embedding model may download once.

## Main Endpoints

### `GET /health`

- simple server status check

### `GET /api/documents`

- lists uploaded document metadata
- returns:
  - `document_id`
  - `filename`
  - `page_count`
  - `chunk_count`
  - `uploaded_at`

### `POST /api/documents/upload`

- uploads and indexes a PDF
- validates:
  - `.pdf` extension
  - content type when present
  - max file size
  - PDF signature
  - corrupted PDF handling
  - empty-text PDF handling

### `POST /api/chat/ask`

Request example:

```json
{
  "question": "Summarize what the uploaded document says about Addison's disease.",
  "mode": "auto",
  "document_ids": null,
  "enhance_prompt": false,
  "top_k": 4
}
```

Possible statuses:

- `ok`
- `refused`
- `no_source`

Rules:

- unsafe medical requests are refused before any retrieval or generation
- if retrieval does not find useful chunks, the assistant says the answer was not found in the uploaded documents

### `GET /api/prompts/search`

- searches the internal prompt library
- supports:
  - `query`
  - `limit`
  - `type`
  - `category`
  - `tag`

### `GET /api/prompts/{prompt_id}`

- returns one prompt template plus its variables

### `POST /api/prompts/improve`

- improves a rough prompt while preserving meaning
- adds structure and output expectations without changing the task
- does not add new medical facts

Example:

```json
{
  "prompt": "summarize a medical topic for students",
  "outputType": "text",
  "outputFormat": "structured_json"
}
```

### `POST /api/pubmed/transform`

- takes one or more selected PubMed PMIDs
- tries PMC full text first when available
- falls back to PubMed abstract text
- supports:
  - `summarize`
  - `compare`
  - `simplify`
  - `quiz`

Example:

```json
{
  "pmids": ["39738916"],
  "action": "summarize",
  "question": "Summarize the selected article for medical students.",
  "enhance_prompt": false,
  "prefer_full_text": true
}
```

### `POST /api/pubmed/import-url`

- experimental workflow for importing readable text from a public open-access article URL
- supports the same actions as selected PubMed articles
- blocks localhost/private-network URLs
- may fail on sites that require login, heavy JavaScript, or anti-bot protection

## Web UI Overview

The class-demo interface at `/` has three areas:

- `Document Dock`
  - upload PDFs
  - view indexed documents
- `Assistant Lab`
  - ask questions
  - switch between modes
  - compare `top_k`
  - toggle prompt enhancement
  - select PubMed results for summary, comparison, simplification, or quizzes
  - try experimental open-access URL import
- `Prompt Studio`
  - search built-in prompt recipes
  - inspect variables without reading a wall of template text
  - improve prompts with a lighter flow

Swagger remains available for low-level API testing.

## Prompt Studio Design

The prompt features are inspired by Prompt Finder & Enhancer / prompts.chat, but implemented locally for this project.

Current support:

- prompt search
- prompt detail lookup
- prompt improvement

Current limitation:

- no live prompts.chat dependency
- no remote prompt marketplace sync

## Suggested Demo Flow

1. Open the web app at `/`.
2. Show the health pill and the Swagger link.
3. Upload a text-based medical PDF.
4. Ask an unsafe dosage question and show refusal.
5. Ask a grounded study question and show sources.
6. Switch to `summarize`, `simplify`, and `quiz`.
7. Use a PubMed question to show literature metadata.
8. Select multiple PubMed studies and run `compare` or `summarize`.
9. Optionally demonstrate the open-access article URL import.
10. Open `Prompt Studio` and improve a rough prompt live.

## Project Structure

```text
app/
  api/routes/              # FastAPI endpoints
  clients/                 # Groq, Chroma, PDF loader, NCBI wrappers
  core/                    # config, constants, exceptions
  prompts/                 # prompt templates for generation
  schemas/                 # request/response models
  services/                # business logic
  web/                     # class-demo web interface
  storage/                 # local runtime storage
  utils/                   # helper utilities
tests/                     # automated tests
```

## Testing

Run the automated suite:

```bash
pytest
```

Current local baseline for `v1.3`:

- `51` tests passing

## Current Limitations

- educational use only
- no diagnosis or treatment
- no OCR for scanned PDFs
- PubMed article actions are still limited by abstract availability or PMC full text
- open-access URL import is experimental and site-dependent
- no authentication or multi-user support
- no deployment pipeline yet

## Good Next Steps After v1.3

- add true side-by-side comparison tables and evidence-agreement views for selected studies
- add post-generation safety checking
- add richer source citation formatting in the UI
- add Docker for easier classroom demos
- add conversation history or session memory
- add exportable study notes and quiz sets
