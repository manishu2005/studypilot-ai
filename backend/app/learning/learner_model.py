from dataclasses import dataclass

@dataclass
class MasteryState:
    topic:str
    mastery: float
    attempts: int
    correct: int
    incorrect: int
    last_score: float
    streak: int
    misconceptions: list[str]

class LearnerModel:
    INITIAL_MASTERY = 0.30
    LEARNING_RATE = 0.18
    FORGETTING_RATE = 0.12

    def update(self, current_mastery: float, correct: bool, score: float = 1.0)->float:
        current_mastery = max(0.0, min(1.0, current_mastery))
        if correct:
            updated = (current_mastery + self.LEARNING_RATE * (1.0 - current_mastery) * score)
        else:
            updated = (current_mastery - self.FORGETTING_RATE * (1.0 - score))

        return max(0.0, min(1.0, updated))

    @staticmethod
    def status(mastery: float)->str:
        if mastery < 0.40:
            return "weak"

        if mastery < 0.70:
            return "developing"

        if mastery < 0.85:
            return "proficient"

        return "strong"

    @staticmethod
    def recommended_difficulty(mastery: float)->str:
        if mastery < 0.40:
            return "easy"

        if mastery < 0.70:
            return "medium"

        if mastery < 0.85:
            return "hard"

        return "hard"

    @staticmethod
    def weakest_topics(topics:list[dict], limit: int = 3)->list[dict]:
        return sorted(
            topics, 
            key=lambda item: item["mastery"],
        )[:limit]