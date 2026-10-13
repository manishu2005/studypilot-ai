from dataclasses import dataclass

@dataclass
class DiagnosticTopicResult:
    topic: str
    total: int
    correct: int
    score: float
    initial_mastery: float

class DiagnosticEngine:
    def calculate_topic_result(self, topic:str, correct:int, total:int)->DiagnosticTopicResult:
        if total <= 0:
            raise ValueError(
                "Total questions must be greater than zero."
            )

        if correct < 0 or correct > total:
            raise ValueError(
                "Correct answers must be within the total."
            )

        score = correct / total
        initial_mastery = round(0.20 + (0.70 * score),2)

        return DiagnosticTopicResult(
            topic=topic,
            total=total,
            correct=correct,
            score=score,
            initial_mastery=initial_mastery,
        )