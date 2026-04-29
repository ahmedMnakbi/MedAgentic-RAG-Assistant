from __future__ import annotations

APP_DESCRIPTION = (
    "MedAgentic RAG Assistant is an educational medical document assistant. "
    "It helps with document understanding, retrieval, summarization, simplification, "
    "study quizzes, and PubMed metadata search. It does not provide diagnosis, "
    "dosage advice, emergency triage, or personalized treatment."
)

DEFAULT_ROUTER_MODE = "rag"
DEFAULT_COLLECTION_NAME = "medical_chunks"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
}

PUBMED_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

ROUTER_KEYWORDS = {
    "pubmed": (
        "pubmed",
        "ncbi",
        "literature",
        "paper",
        "papers",
        "study",
        "studies",
        "article",
        "articles",
        "journal",
    ),
    "quiz": (
        "quiz",
        "mcq",
        "multiple choice",
        "question bank",
        "flashcard",
        "flashcards",
        "test me",
        "practice question",
        "practice questions",
    ),
    "simplify": (
        "simplify",
        "simple terms",
        "plain language",
        "easy terms",
        "easy language",
        "explain simply",
        "easier words",
    ),
    "summarize": (
        "summarize",
        "summary",
        "key points",
        "overview",
        "main points",
        "briefly explain",
    ),
    "prompt_enhance": (
        "improve my prompt",
        "enhance my prompt",
        "rewrite my prompt",
        "better prompt",
        "optimize this prompt",
    ),
}

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "does",
    "from",
    "have",
    "into",
    "medical",
    "more",
    "most",
    "not",
    "only",
    "over",
    "same",
    "should",
    "than",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "this",
    "those",
    "through",
    "under",
    "very",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}
