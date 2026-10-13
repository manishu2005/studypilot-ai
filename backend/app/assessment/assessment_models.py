from typing import Literal
from pydantic import BaseModel, Field

class VerificationResult(BaseModel):
    valid:bool
    answer_supported:bool
    question_supported: bool
    unambiguous: bool
    explanation_supported: bool
    reason: str

class QuestionFeedback(BaseModel):
    correct:bool
    score: float=Field(ge=0.0, le=1.0)
    feedback:str
    explanation: str
    misconception: str= ""
    topic:str
    source_relevant: bool

class QuizAttemptResult(BaseModel):
    total_questions: int
    correct_answers: int
    score: float
    feedback: list[QuestionFeedback]