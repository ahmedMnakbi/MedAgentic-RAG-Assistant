# rapportCheck

## Context

Project reviewed: `MedAgentic RAG Assistant`

Review date: `2026-04-29`

Branch / commit reviewed:

- `main`
- latest reviewed commit at report time: `17de9ca`

## Important Note About Browser Use

I attempted to test the app with the Browser Use plugin as requested.

What happened:

- the plugin runtime failed before browser control started
- `mcp__node_repl__.js` returned: `failed to execute Node: Access is denied. (os error 5)`

Impact:

- I could not complete true in-app browser automation through the plugin in this environment
- I continued with the strongest available fallback:
  - full automated test suite
  - live HTTP smoke tests against the running app on `http://127.0.0.1:8000`
  - code review of the frontend files

This looks like an environment/runtime problem, not a problem in the FastAPI app itself.

## What I Tested

### Automated

- full test suite: `38 passed`

### Live endpoint checks

- `GET /`
- `GET /health`
- `GET /api/documents`
- `POST /api/documents/upload`
- `POST /api/chat/ask` for:
  - unsafe dosage refusal
  - summarize
  - simplify
  - quiz
  - pubmed
  - prompt_enhance
  - rag
- `GET /api/prompts/search`
- `GET /api/prompts/{prompt_id}`
- `POST /api/prompts/improve`

### Test file used

- `C:/Users/ahmed/Downloads/8205Oxford Handbook of Clinical Medicine 10th 2017 Edition_SamanSarKo - Copy.pdf`

## What Is Good

- The API is structurally solid.
  - Core endpoints respond correctly.
  - Swagger and the custom web UI can coexist.

- The project safety boundary is partially working well.
  - Unsafe dosage questions are refused correctly.
  - The refusal message is clear and appropriately educational.

- Upload and indexing work.
  - The sample medical PDF uploaded successfully.
  - The document registry and document listing worked.

- The Prompt Lab is a strong addition for demos.
  - prompt search works
  - prompt detail lookup works
  - prompt improvement now behaves more like real prompt engineering and no longer injects random “exclude diagnosis/treatment/dosage/triage” wording into the user’s prompt

- PubMed mode is noticeably better after the recent cleanup.
  - Natural-language PubMed requests now normalize better.
  - Prompt-template inputs like `${chronic fatigue}` are reduced to their real topic instead of poisoning the search query.
  - The user case around Addison’s disease now returns records instead of an empty result.
  - Broad queries like `PubMed studies on anxiety` now benefit from relevance sorting and a stronger fielded query.

- The codebase remains modular and readable.
  - backend logic is separated into routes, services, clients, schemas, and prompts
  - this is good for a portfolio or classroom explanation

- The UI concept is good for class demos.
  - one page for upload, ask, sources, and prompt lab is a strong presentation choice

## What Is Bad

- Browser Use plugin testing is blocked in this environment.
  - That means I could not certify the UI through real browser automation in this session.
  - This is not necessarily an app bug, but it weakens confidence in true end-to-end UI behavior from the plugin perspective.

- `simplify` mode is too weak when the request is generic.
  - Example tested: `Explain the uploaded document in simpler terms.`
  - Result: `no_source`
  - This makes the feature feel unreliable unless the question contains a topic.

- `quiz` mode is too easy to derail with a generic request.
  - Example tested: `Create quiz questions from the uploaded document.`
  - It generated quiz items from an arbitrary psychiatric assessment chunk on page 3.
  - For a big textbook upload, this is not what a normal user expects.

- PubMed relevance is improved, but still noisy on broad topics.
  - The Addison’s PubMed query returned results, but some were only weakly related to Addison’s disease.
  - One result matched an author named `Addison PK`, which is a classic keyword-search false positive.

- Duplicate uploads are allowed with no warning or deduplication.
  - Uploading the same PDF again created another indexed document entry.
  - That may confuse classroom demos and clutter retrieval.

- PDF extraction quality is still imperfect.
  - Some source excerpts still show artifacts like `suffi cient` or broken spacing.
  - This is common with PDF extraction, but it affects polish.

- The chat-level `prompt_enhance` mode is still a little confusing.
  - The dedicated `/api/prompts/improve` behavior is clearer.
  - But if a user types a meta-request like `make this prompt better for a document summary`, the result can still feel awkward rather than obviously useful.

## What Still Needs Work

### 1. Better whole-document workflows

Right now many modes depend on retrieval from a user query.

That works for targeted questions, but it is weak for:

- simplify the whole upload
- quiz the whole upload
- summarize the whole upload

Recommended improvement:

- add explicit whole-document mode or section mode
- let the user choose:
  - entire document
  - selected document
  - selected pages
  - retrieved passages only

### 2. Better PubMed query engineering

Current PubMed querying is better than before, but it is still not a full literature-search workflow.

Recommended improvement:

- use quoted phrases where appropriate
- support MeSH-aware queries later
- add optional filters:
  - recent years
  - article type
  - review vs trial
- possibly add a small query-builder step specifically for PubMed mode

### 3. Clarify the safety policy at the product level

The current project correctly blocks personalized dosage advice.

But there is still a policy ambiguity between:

- general educational discussion of diagnosis/treatment concepts
- prohibited clinical advice

Recommended improvement:

- define this explicitly in the README and UI copy
- enforce it consistently across:
  - summarize
  - rag
  - simplify
  - quiz
  - pubmed synthesis if added later

### 4. Improve prompt engineering behavior further

The prompt improver is much better now, but it still needs to feel like a proper utility.

Recommended improvement:

- return multiple improved variants
- allow styles such as:
  - concise
  - structured
  - chain-of-thought-hidden but robust
  - JSON-oriented
  - search-oriented
- show why one version is stronger than another

### 5. Deduplicate or warn on re-upload

Recommended improvement:

- hash uploaded files
- detect same-file re-upload
- either:
  - block duplicates
  - warn the user
  - or offer “re-index existing document”

### 6. UI verification and E2E testing

This is the biggest process gap now.

Recommended improvement:

- add true end-to-end UI tests when browser automation is available
- even lightweight Playwright tests would help validate:
  - upload flow
  - prompt lab
  - document picker
  - PubMed result rendering
  - error states

## My Practical Verdict

This is already a good student portfolio project and a good classroom demo project.

Why:

- it has a real backend architecture
- it uses RAG, vector storage, external APIs, safety logic, and prompt tooling
- it now has a user-facing demo interface instead of only Swagger

But it is not fully polished yet.

If I had to summarize the current state in one sentence:

> The project is strong architecturally and demo-worthy now, but it still needs better whole-document UX, better PubMed relevance, and better true end-to-end frontend testing to feel fully mature.

## Best Next Steps

If continuing from here, I would prioritize:

1. Whole-document summarize / simplify / quiz modes
2. Better PubMed query building and filtering
3. Duplicate-upload handling
4. Real browser E2E testing
5. Better prompt improver variants and UX
