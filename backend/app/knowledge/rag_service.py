from app.knowledge.relevance import RelevanceChecker
from app.knowledge.rag_models import TutorResponse
from app.learning.tutor import GeminiTutor


class RAGService:

    def __init__(self, retriever):
        self.retriever = retriever
        self.tutor = GeminiTutor()
        self.relevance_checker = RelevanceChecker()

    def answer(
        self,
        question: str,
        top_k: int = 8,
    ) -> TutorResponse:

        retrieved = self.retriever.retrieve(
            question,
            top_k=top_k,
        )

        if not retrieved:
            return TutorResponse(
                grounded=False,
                answer=(
                    "The uploaded study material does not "
                    "contain enough information to answer "
                    "this question."
                ),
                citations=[],
                confidence=0.0,
                limitation=(
                    "No relevant study material was retrieved."
                ),
            )

        relevance = self.relevance_checker.check(retrieved)

        if not relevance.grounded:
            return TutorResponse(
                grounded=False,
                answer=(
                    "I could not find sufficient information "
                    "about this topic in the uploaded material."
                ),
                citations=[],
                confidence=0.0,
                limitation=(
                    "The retrieved material was not sufficiently "
                    "relevant to the question."
                ),
            )

        context = "\n\n".join(
            [
                f"[Source {index + 1}]\n{chunk.text}"
                for index, chunk in enumerate(retrieved)
            ]
        )

        model_response = self.tutor.answer(
            question=question,
            context=context,
        )

        citations = []

        if model_response.grounded:
            for chunk in retrieved:
                citations.append(
                    chunk.to_citation()
                )

        return TutorResponse(
            grounded=model_response.grounded,
            answer=model_response.answer,
            citations=citations,
            confidence=model_response.confidence,
            limitation=model_response.limitation,
        )