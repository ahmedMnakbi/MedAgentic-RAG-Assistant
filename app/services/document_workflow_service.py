from __future__ import annotations

from app.schemas.documents import DocumentWorkflowRequest, DocumentWorkflowResponse


class DocumentWorkflowService:
    def __init__(
        self,
        *,
        rag_service,
        safety_service,
        summarization_service,
        simplification_service,
        quiz_service,
        answer_service,
    ) -> None:
        self.rag_service = rag_service
        self.safety_service = safety_service
        self.summarization_service = summarization_service
        self.simplification_service = simplification_service
        self.quiz_service = quiz_service
        self.answer_service = answer_service

    def run(self, request: DocumentWorkflowRequest) -> DocumentWorkflowResponse:
        question = request.question or self._default_question(request.action)
        safety = self.safety_service.assess(question)
        if not safety.allowed:
            return DocumentWorkflowResponse(
                status="refused",
                action=request.action,
                answer=self.safety_service.refusal_message(safety.category),
                warnings=["Whole-document workflows are educational only."],
            )
        chunks = self.rag_service.retrieve_document_chunks(
            document_ids=request.document_ids,
            page_from=request.page_from,
            page_to=request.page_to,
        )
        if not chunks:
            return DocumentWorkflowResponse(
                status="no_source",
                action=request.action,
                answer="No indexed document chunks were available for this whole-document workflow.",
                warnings=["Upload a text-based PDF first, or narrow the requested page range."],
            )
        packed = self.rag_service.pack_context(chunks)
        if not packed.text:
            return DocumentWorkflowResponse(
                status="no_source",
                action=request.action,
                answer="No usable whole-document context remained after safety/context packing.",
                warnings=packed.warnings,
            )
        if request.action in {"summary", "page_range_summary"}:
            answer = self.summarization_service.summarize_context(
                question,
                packed.text,
                context_label="Whole-document context",
            )
        elif request.action == "simplification":
            answer = self.simplification_service.simplify_context(
                question,
                packed.text,
                context_label="Whole-document context",
            )
        elif request.action == "quiz":
            quiz_items = self.quiz_service.generate_context(
                question,
                packed.text,
                context_label="Whole-document context",
            )
            return DocumentWorkflowResponse(
                status="ok",
                action=request.action,
                answer="Generated whole-document study quiz questions.",
                warnings=packed.warnings,
                source_count=len(chunks),
                quiz_items=[item.model_dump() for item in quiz_items],
            )
        else:
            answer = self.answer_service.answer_context(
                question,
                packed.text,
                context_label="Whole-document context",
            )
        return DocumentWorkflowResponse(
            status="ok",
            action=request.action,
            answer=answer,
            warnings=packed.warnings,
            source_count=len(chunks),
        )

    @staticmethod
    def _default_question(action: str) -> str:
        mapping = {
            "summary": "Summarize the entire uploaded document for medical education.",
            "page_range_summary": "Summarize the requested page range for medical education.",
            "simplification": "Simplify the entire uploaded document for study purposes.",
            "quiz": "Create a whole-document quiz for medical students.",
            "key_concepts": "Extract key concepts from the whole document for study review.",
        }
        return mapping.get(action, mapping["summary"])
