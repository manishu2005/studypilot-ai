from dataclasses import dataclass
from app.knowledge.retrieval import RetrievedChunk

@dataclass
class RelevanceResult:
    grounded:bool
    chunks: list[RetrievedChunk]
    score:float

class RelevanceChecker:
    def __init__(self, minimum_score: float = 0.12):
        self.minimum_score = minimum_score

    def check(self, chunks:list[RetrievedChunk])->RelevanceResult:
        if not chunks:
            return RelevanceResult(
                grounded=False,
                chunks=[],
                score=0.0,
            )

        top_score = chunks[0].combined_score

        grounded = (
            top_score >= self.minimum_score
        )

        return RelevanceResult(
            grounded=grounded,
            chunks=chunks if grounded else [],
            score=float(top_score),
        )