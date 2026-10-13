
import json

from openai import OpenAI

from app.core.config import settings
from app.core.gemini_client import get_gemini_client
from app.knowledge.rag_models import TutorModelResponse
from app.learning.learning_tools import build_tutor_prompt

class GeminiTutor:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = settings.gemini_model

        self.groq_client = None
        if settings.groq_api_key:
            self.groq_client = OpenAI(
                api_key=settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )

    def answer(self,question: str,context: str,language: str = "hinglish") -> TutorModelResponse:
        prompt = build_tutor_prompt(
            question=question,
            retrieved_context=context,
            language=language,
        )

        # Try Gemini first.
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": TutorModelResponse,
                },
            )

            if not response.text:
                raise RuntimeError("Gemini returned an empty tutor response.")

            return TutorModelResponse.model_validate_json(response.text)

        
        except Exception as gemini_error:
            if self.groq_client is None:
                raise RuntimeError(
                    "Gemini failed and Groq fallback is not configured."
                ) from gemini_error

            try:
                response = self.groq_client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Answer using only the supplied study context. "
                                "If the context does not support an answer, set grounded to false "
                                "and explain the limitation. Return valid JSON with exactly these "
                                "fields: grounded (boolean), answer (string), confidence (number "
                                "from 0 to 1), limitation (string). "
                                "Do not invent facts or sources."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                if not content:
                    raise RuntimeError("Groq returned an empty tutor response.")

                return TutorModelResponse.model_validate_json(content)

            except Exception as groq_error:
                raise RuntimeError(
                    "Both Gemini and Groq tutor requests failed. "
                    f"Gemini error: {gemini_error}; Groq error: {groq_error}"
                ) from groq_error
