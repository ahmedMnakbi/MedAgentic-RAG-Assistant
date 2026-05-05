from __future__ import annotations

from types import SimpleNamespace

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, documents, health, open_article, open_literature, prompts, pubmed, web
from app.clients.embeddings_client import EmbeddingsClient
from app.clients.groq_client import GroqClient
from app.clients.ncbi_client import NCBIClient
from app.clients.pdf_loader import PDFLoaderClient
from app.clients.vectorstore_client import VectorStoreClient
from app.core.config import Settings, get_settings
from app.core.constants import APP_DESCRIPTION
from app.core.exceptions import AppError
from app.schemas.common import ErrorResponse
from app.services.answer_service import AnswerService
from app.services.document_registry_service import DocumentRegistryService
from app.services.document_service import DocumentService
from app.services.document_workflow_service import DocumentWorkflowService
from app.services.general_education_service import GeneralEducationService
from app.services.prompt_enhancer_service import PromptEnhancerService
from app.services.prompt_enhancer_v2_service import PromptEnhancerV2Service
from app.services.prompt_library_service import PromptLibraryService
from app.services.grounding_service import GroundingService
from app.services.langgraph_rag_service import LangGraphRagService
from app.services.open_article_service import OpenArticleService
from app.services.open_literature.adapters.core_adapter import COREAdapter
from app.services.open_literature.adapters.crossref_adapter import CrossrefAdapter
from app.services.open_literature.adapters.cureus_adapter import CureusAdapter
from app.services.open_literature.adapters.doaj_adapter import DOAJAdapter
from app.services.open_literature.adapters.europe_pmc_adapter import EuropePMCAdapter
from app.services.open_literature.adapters.generic_html_adapter import GenericOAHTMLAdapter
from app.services.open_literature.adapters.openalex_adapter import OpenAlexAdapter
from app.services.open_literature.adapters.pubmed_adapter import PMCOAAdapter, PubMedMetadataAdapter
from app.services.open_literature.adapters.semantic_scholar_adapter import SemanticScholarAdapter
from app.services.open_literature.adapters.unpaywall_adapter import UnpaywallAdapter
from app.services.open_literature.search_service import OpenLiteratureSearchService
from app.services.post_safety_service import PostSafetyService
from app.services.pubmed_service import PubMedService
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService
from app.services.router_service import RouterService
from app.services.safety_service import SafetyService
from app.services.simplification_service import SimplificationService
from app.services.summarization_service import SummarizationService


def build_services(settings: Settings) -> SimpleNamespace:
    embeddings_client = EmbeddingsClient(settings)
    vectorstore_client = VectorStoreClient(settings, embeddings_client)
    groq_client = GroqClient(settings)
    document_registry_service = DocumentRegistryService(settings)
    rag_service = RagService(settings, vectorstore_client)
    prompt_library_service = PromptLibraryService(settings=settings, groq_client=groq_client)
    safety_service = SafetyService()
    ncbi_client = NCBIClient(settings)
    open_article_service = OpenArticleService(
        settings=settings,
        ncbi_client=ncbi_client,
    )
    generic_html_adapter = GenericOAHTMLAdapter(open_article_service)
    answer_service = AnswerService(groq_client=groq_client)
    summarization_service = SummarizationService(groq_client=groq_client)
    simplification_service = SimplificationService(groq_client=groq_client)
    quiz_service = QuizService(groq_client=groq_client)
    return SimpleNamespace(
        safety_service=safety_service,
        router_service=RouterService(),
        prompt_enhancer_service=PromptEnhancerService(),
        prompt_enhancer_v2_service=PromptEnhancerV2Service(
            settings=settings,
            safety_service=safety_service,
            groq_client=groq_client,
        ),
        prompt_library_service=prompt_library_service,
        document_service=DocumentService(
            settings=settings,
            pdf_loader=PDFLoaderClient(),
            vectorstore_client=vectorstore_client,
            registry_service=document_registry_service,
        ),
        rag_service=rag_service,
        answer_service=answer_service,
        general_education_service=GeneralEducationService(settings=settings, groq_client=groq_client),
        summarization_service=summarization_service,
        simplification_service=simplification_service,
        quiz_service=quiz_service,
        document_workflow_service=DocumentWorkflowService(
            rag_service=rag_service,
            safety_service=safety_service,
            summarization_service=summarization_service,
            simplification_service=simplification_service,
            quiz_service=quiz_service,
            answer_service=answer_service,
        ),
        pubmed_service=PubMedService(ncbi_client=ncbi_client),
        open_article_service=open_article_service,
        open_literature_service=OpenLiteratureSearchService(
            settings=settings,
            safety_service=safety_service,
            adapters=[
                PMCOAAdapter(ncbi_client),
                PubMedMetadataAdapter(ncbi_client),
                EuropePMCAdapter(),
                OpenAlexAdapter(),
                UnpaywallAdapter(),
                CrossrefAdapter(),
                COREAdapter(),
                SemanticScholarAdapter(),
                DOAJAdapter(),
                CureusAdapter(),
            ],
            generic_adapter=generic_html_adapter if settings.open_literature_enable_generic_html else None,
        ),
        post_safety_service=PostSafetyService(safety_service),
        grounding_service=GroundingService(),
        langgraph_rag_service=LangGraphRagService(settings),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.ensure_storage_paths()
    web_dir = Path(__file__).resolve().parent / "web"

    app = FastAPI(
        title=resolved_settings.app_name,
        description=APP_DESCRIPTION,
        debug=resolved_settings.app_debug,
        version="2.0.0",
    )
    app.state.settings = resolved_settings
    app.state.services = build_services(resolved_settings)

    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    app.include_router(web.router)
    app.include_router(health.router)
    app.include_router(documents.router, prefix=resolved_settings.api_prefix)
    app.include_router(chat.router, prefix=resolved_settings.api_prefix)
    app.include_router(pubmed.router, prefix=resolved_settings.api_prefix)
    app.include_router(open_article.router, prefix=resolved_settings.api_prefix)
    app.include_router(open_literature.router, prefix=resolved_settings.api_prefix)
    app.include_router(prompts.router, prefix=resolved_settings.api_prefix)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(error=exc.message, code=exc.code, details=exc.details)
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        body = ErrorResponse(error="Unexpected internal server error.", code="internal_server_error")
        return JSONResponse(status_code=500, content=body.model_dump())

    return app


app = create_app()
