from app.assessment.assessment_models import QuestionFeedback
from app.core.config import settings
from app.core.gemini_client import get_gemini_client

class FeedbackGenerator:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = settings.gemini_model

    def generate(self, question:str, correct_answer:str, student_answer:str, explanation:str, topic:str, context:str)->QuestionFeedback:
        prompt = f"""
You are StudyPilot AI's educational feedback system.

Evaluate the student's answer using ONLY the supplied
study material.

Question:
{question}

Correct answer:
{correct_answer}

Student answer:
{student_answer}

Expected explanation:
{explanation}

Topic:
{topic}

Study material:
========================
{context}
========================

Instructions:

1. Determine whether the student's answer is correct.
2. Give a score between 0 and 1.
3. Explain the result clearly.
4. If incorrect, explain the correct concept.
5. Identify a likely misconception if one is visible.
6. Do not introduce facts that are absent from the material.
7. Keep feedback educational and concise.
8. source_relevant must be true only when the feedback
   is supported by the supplied material.
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": QuestionFeedback,
            },
        )

        return QuestionFeedback.model_validate_json(
            response.text
        )