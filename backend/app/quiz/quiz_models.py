from typing import Literal
from pydantic import BaseModel, Field

QuestionType=Literal["mcq","short_answer","numerical"]
Difficulty=Literal["easy","medium","hard"]

class GeneratedQuestion(BaseModel):
    question: str=Field(description="The question presented to the student.")
    question_type:QuestionType

    options:list[str]=Field(
        default_factory=list,
        description=(
            "Exactly four options for MCQ. "
            "Empty for other question types."
        ),
    )

    correct_answer: str=Field(description="correct answer")
    explanation: str= Field(description=("Educational explanation of why the answer is correct"))
    topic:str=Field(description="Topic tested by the question.")
    difficulty:Difficulty

class GeneratedQuiz(BaseModel):
    questions:list[GeneratedQuestion]