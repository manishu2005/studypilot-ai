
from unittest.mock import MagicMock, patch

from app.rag_models import TutorModelResponse
from app.tutor import GeminiTutor


def test_groq_fallback_when_gemini_fails():
    tutor = GeminiTutor.__new__(GeminiTutor)
    tutor.client = MagicMock()
    tutor.model = "test-gemini-model"
    tutor.groq_client = MagicMock()

    tutor.client.models.generate_content.side_effect = RuntimeError(
        "Simulated Gemini failure"
    )

    tutor.groq_client.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    '{"grounded": true, '
                    '"answer": "Photosynthesis is how plants make food.", '
                    '"confidence": 0.95, '
                    '"limitation": ""}'
                )
            )
        )
    ]

    with patch(
        "app.tutor.build_tutor_prompt",
        return_value="Answer using the supplied study context.",
    ):
        result = tutor.answer(
            question="What is photosynthesis?",
            context="Plants use sunlight to make food.",
        )

    assert isinstance(result, TutorModelResponse)
    assert result.answer == "Photosynthesis is how plants make food."
    tutor.groq_client.chat.completions.create.assert_called_once()
