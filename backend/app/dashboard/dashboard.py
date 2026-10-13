
from app.learning.learner_model import LearnerModel


class DashboardService:
    def __init__(self):
        self.model = LearnerModel()

    def build(self, topics: list[dict]) -> dict:
        # Handle the case where no topic data exists.
        if not topics:
            return {
                "has_data": False,
                "overall_mastery": 0.0,
                "status": "new",
                "topics": [],
                "weak_topics": [],
                "strong_topics": [],
                "misconceptions": [],
                "recommendation": {
                    "action": "diagnostic",
                    "message": (
                        "Take a diagnostic assessment "
                        "to establish your learning profile."
                    ),
                },
            }

        # Normalize topic data.
        normalized_topics = []

        for topic in topics:
            item = dict(topic)

            mastery = float(item.get("mastery", 0.0))
            item["mastery"] = max(0.0, min(1.0, mastery))

            item.setdefault("topic", "unknown")
            item.setdefault("misconceptions", [])
            item.setdefault("last_score", 0.0)
            item.setdefault("attempts", 0)
            item.setdefault("correct", 0)
            item.setdefault("incorrect", 0)

            item["status"] = self.model.status(item["mastery"])
            item["recommended_difficulty"] = (
                self.model.recommended_difficulty(item["mastery"])
            )

            normalized_topics.append(item)

        # Calculate overall mastery.
        overall = sum(
            item["mastery"] for item in normalized_topics
        ) / len(normalized_topics)

        # Identify weak and strong topics.
        weak_topics = [
            item
            for item in normalized_topics
            if item["mastery"] < 0.70
        ]

        strong_topics = [
            item
            for item in normalized_topics
            if item["mastery"] >= 0.85
        ]

        # Collect misconceptions.
        misconceptions = []

        for item in normalized_topics:
            for misconception in item["misconceptions"]:
                misconceptions.append({
                    "topic": item.get("topic", "unknown"),
                    "description": misconception,
                })

        # Prioritize topics requiring additional attention.
        def priority(item: dict) -> float:
            mastery_gap = 1.0 - item["mastery"]

            misconception_bonus = (
                min(len(item["misconceptions"]), 3) * 0.10
            )

            recent_failure_bonus = (
                0.15
                if float(item["last_score"]) < 0.5
                and int(item["attempts"]) > 0
                else 0.0
            )

            return (
                mastery_gap
                + misconception_bonus
                + recent_failure_bonus
            )

        recommended = max(normalized_topics, key=priority)

        # Generate a personalized recommendation.
        if recommended["mastery"] < 0.40:
            recommendation = {
                "action": "revision",
                "topic": recommended["topic"],
                "difficulty": "easy",
                "message": (
                    f"Review {recommended['topic']} using your "
                    "course materials, then try an easy quiz."
                ),
            }
        else:
            recommendation = {
                "action": "adaptive_quiz",
                "topic": recommended["topic"],
                "difficulty": recommended["recommended_difficulty"],
                "message": (
                    f"Practice {recommended['topic']} to improve "
                    "your estimated mastery."
                ),
            }

        # Return the dashboard response.
        return {
            "has_data": True,
            "overall_mastery": round(overall, 3),
            "status": self.model.status(overall),
            "topics": normalized_topics,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "misconceptions": misconceptions,
            "recommendation": recommendation,
        }
