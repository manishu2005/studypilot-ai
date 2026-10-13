import json
import logging

from groq import Groq

from app.core.config import settings
from app.core.gemini_client import get_gemini_client
from app.assessment.assessment_models import VerificationResult

logger = logging.getLogger(__name__)


class QuizVerifier:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = settings.gemini_model
        self.groq_client = (
            Groq(api_key=settings.groq_api_key)
            if settings.groq_api_key
            else None
        )

    def verify(
        self,
        question: str,
        options: list[str],
        correct_answer: str,
        explanation: str,
        context: str,
    ) -> VerificationResult:
        prompt = f"""
You are the assessment quality verifier for StudyPilot AI.

Use ONLY the supplied study material.
Do not use outside knowledge.

Question:
{question}

Options:
{json.dumps(options)}

Claimed correct answer:
{correct_answer}

Explanation:
{explanation}

Study material:
========================
{context}
========================

Check:
1. Is the question supported by the material?
2. Is the answer supported by the material?
3. Is the question unambiguous?
4. Is the explanation supported by the material?
5. For MCQs, is exactly one option correct?
6. Does the question test the supplied material?
7. Is there hallucinated information?

Set valid=true only when all important checks pass.
If invalid, explain why.

Return JSON matching this schema:
{json.dumps(VerificationResult.model_json_schema())}
"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": VerificationResult,
                },
            )

            if not response.text:
                raise ValueError("Gemini returned an empty verification response.")

            result = VerificationResult.model_validate_json(response.text)
            logger.info("Question verified using Gemini.")
            return result

        except Exception:
            logger.exception(
                "Gemini verification failed; attempting Groq fallback."
            )

        try:
            if not self.groq_client:
                raise ValueError("GROQ_API_KEY is missing.")

            response = self.groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Verify academic questions strictly against "
                            "the supplied study material. Return only valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            content = response.choices[0].message.content

            if not content:
                raise ValueError("Groq returned an empty verification response.")

            result = VerificationResult.model_validate_json(content)
            logger.info("Question verified using Groq fallback.")
            return result

        except Exception as groq_error:
            logger.exception("Both Gemini and Groq verification failed.")
            raise RuntimeError(
                "Question verification failed with both Gemini and Groq. "
                f"Groq error: {groq_error}"
            ) from groq_error
