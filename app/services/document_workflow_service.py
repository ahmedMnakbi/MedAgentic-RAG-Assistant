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
        document_service=None,
    ) -> None:
        self.rag_service = rag_service
        self.safety_service = safety_service
        self.summarization_service = summarization_service
        self.simplification_service = simplification_service
        self.quiz_service = quiz_service
        self.answer_service = answer_service
        self.document_service = document_service

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
        eligible_ids, scope_warnings, blocked = self._eligible_document_ids(request.document_ids)
        if blocked:
            answer = (
                "This document appears to be outside MARA's medical education scope. "
                "MARA is designed for medical and health-learning content, so I can't summarize "
                "or generate quizzes from this source."
            )
            if not any("out-of-scope" in warning for warning in scope_warnings):
                answer = (
                    "This document has not been verified as medical or health-learning content, "
                    "so MARA will not use it for medical workflows by default."
                )
            return DocumentWorkflowResponse(
                status="refused",
                action=request.action,
                answer=answer,
                warnings=scope_warnings,
            )
        if eligible_ids is not None and not eligible_ids:
            return DocumentWorkflowResponse(
                status="no_source",
                action=request.action,
                answer="No eligible medical documents are available for this whole-document workflow.",
                warnings=scope_warnings,
            )

        chunks = self.rag_service.retrieve_document_chunks(
            document_ids=eligible_ids,
            page_from=request.page_from,
            page_to=request.page_to,
        )
        if not chunks:
            return DocumentWorkflowResponse(
                status="no_source",
                action=request.action,
                answer="No indexed document chunks were available for this whole-document workflow.",
                warnings=scope_warnings + ["Upload a text-based PDF first, or narrow the requested page range."],
            )
        packed = self.rag_service.pack_context(chunks)
        if not packed.text:
            return DocumentWorkflowResponse(
                status="no_source",
                action=request.action,
                answer="No usable whole-document context remained after safety/context packing.",
                warnings=scope_warnings + packed.warnings,
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
                warnings=scope_warnings + packed.warnings,
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
            warnings=scope_warnings + packed.warnings,
            source_count=len(chunks),
        )

    def _eligible_document_ids(self, document_ids: list[str] | None) -> tuple[list[str] | None, list[str], bool]:
        if not self.document_service:
            return document_ids, [], False
        records = self.document_service.list_documents()
        selected_ids = set(document_ids or [])
        scoped = [record for record in records if not selected_ids or record.document_id in selected_ids]
        eligible = [record for record in scoped if record.eligible_for_medical_workflows]
        ineligible = [record for record in scoped if not record.eligible_for_medical_workflows]
        non_medical = [record for record in ineligible if record.scope_category == "non_medical"]
        warnings = []
        if ineligible:
            count = len(ineligible)
            if non_medical:
                warnings.append(f"Skipped {count} out-of-scope document{'s' if count != 1 else ''}.")
            else:
                warnings.append(f"Skipped {count} document{'s' if count != 1 else ''} because they are not verified as medical-scope sources.")
        unknown = [record for record in eligible if record.scope_category == "unknown"]
        if unknown:
            count = len(unknown)
            warnings.append(f"{count} document{'s have' if count != 1 else ' has'} unknown scope and will be used with caution.")
        blocked = bool(document_ids and ineligible and not eligible)
        if document_ids is None:
            return [record.document_id for record in eligible], warnings, False
        return [record.document_id for record in eligible], warnings, blocked

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
