import json
import logging
import re
from groq import Groq
from app.core.config import settings
from app.core.gemini_client import get_gemini_client
from app.quiz.quiz_models import GeneratedQuiz

logger = logging.getLogger(__name__)


class QuizGenerator:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = settings.gemini_model
        self.groq_client = (
            Groq(api_key=settings.groq_api_key)
            if getattr(settings, "groq_api_key", None)
            else None
        )

    def _build_prompt(
        self,
        context: str,
        number_of_questions: int,
        question_type: str,
        difficulty: str,
    ) -> str:
        schema = json.dumps(GeneratedQuiz.model_json_schema())

        return f"""
You are an academic assessment generator for StudyPilot AI.

Generate exactly {number_of_questions} questions.
Use ONLY the supplied study material.

Requested question type: {question_type}
Requested difficulty: {difficulty}

Requirements:
- Every answer and explanation must be supported by the material.
- Do not invent facts or use outside knowledge.
- Every question must have a meaningful topic.
- Avoid duplicate questions.
- For mcq, provide exactly four options and one correct answer.
- For short_answer and numerical, options must be an empty list.
- question_type must be one of: mcq, short_answer, numerical.
- difficulty must be one of: easy, medium, hard.
- Return ONLY a JSON object matching this schema without preamble or markdown fences:
{schema}

Study material:
====================
{context}
====================
"""

    def _clean_json_text(self, raw_text: str) -> str:
        """Strip markdown code fence blocks if the LLM wraps JSON inside them."""
        text = raw_text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    def _validate_quiz(
        self,
        raw_json: str,
        number_of_questions: int,
        question_type: str,
        difficulty: str,
    ) -> GeneratedQuiz:
        cleaned_json = self._clean_json_text(raw_json)
        quiz = GeneratedQuiz.model_validate_json(cleaned_json)

        if len(quiz.questions) != number_of_questions:
            logger.warning(
                f"Question count mismatch: expected {number_of_questions}, got {len(quiz.questions)}. Truncating or accepting available questions."
            )
            # Accept if at least 1 question generated rather than completely failing
            if len(quiz.questions) == 0:
                raise ValueError("No questions were generated.")

        for question in quiz.questions:
            # Normalize casing in case model returns TitleCase
            question.question_type = question.question_type.lower()
            question.difficulty = question.difficulty.lower()

            if question.question_type == "mcq":
                if len(question.options) != 4:
                    raise ValueError("Every MCQ must contain exactly four options.")
                if question.correct_answer not in question.options:
                    # If not exact match, check strip/case match or set closest
                    matched = next(
                        (opt for opt in question.options if opt.strip() == question.correct_answer.strip()),
                        None
                    )
                    if matched:
                        question.correct_answer = matched
                    else:
                        raise ValueError("MCQ correct_answer must match one of its options.")
            elif question.options is None:
                question.options = []

        return quiz

    def _generate_with_gemini(
        self,
        prompt: str,
        number_of_questions: int,
        question_type: str,
        difficulty: str,
    ) -> GeneratedQuiz:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": GeneratedQuiz,
            },
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        return self._validate_quiz(
            response.text,
            number_of_questions,
            question_type,
            difficulty,
        )

    def _generate_with_groq(
        self,
        prompt: str,
        number_of_questions: int,
        question_type: str,
        difficulty: str,
    ) -> GeneratedQuiz:
        if not self.groq_client:
            raise ValueError("GROQ_API_KEY is not configured in settings.")

        groq_model = getattr(settings, "groq_model", "llama-3.3-70b-versatile")

        response = self.groq_client.chat.completions.create(
            model=groq_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an academic exam generator. Return only raw, valid JSON conforming "
                        "strictly to the provided schema. Do not wrap output in backticks or markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned an empty response.")

        return self._validate_quiz(
            content,
            number_of_questions,
            question_type,
            difficulty,
        )

    def generate(
        self,
        context: str,
        number_of_questions: int = 5,
        question_type: str = "mcq",
        difficulty: str = "medium",
    ) -> GeneratedQuiz:
        prompt = self._build_prompt(
            context,
            number_of_questions,
            question_type,
            difficulty,
        )

        # FORCE GROQ DIRECTLY FOR TESTING:
        logger.info("Forcing Groq generation directly...")
        return self._generate_with_groq(
            prompt, number_of_questions, question_type, difficulty
        )