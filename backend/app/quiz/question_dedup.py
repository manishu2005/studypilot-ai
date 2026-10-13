from sentence_transformers import SentenceTransformer

class QuestionDeduplicator:
    def __init__(self, model_name: str = ("sentence-transformers/all-MiniLM-L6-v2"), threshold: float = 0.88):
        self.model = SentenceTransformer(model_name)
        self.threshold= threshold

    def is_duplicate(self, question:str, existing_questions:list[str])->bool:
        if not existing_questions:
            return False

        embeddings = self.model.encode(
            [question] + existing_questions, normalize_embeddings=True
        )

        new_embedding = embeddings[0]
        similarities = embeddings[1:] @ new_embedding
        return bool(similarities.max() => self.threshold)