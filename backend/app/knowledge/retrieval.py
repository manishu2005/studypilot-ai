from dataclasses import dataclass
from rank_bm25 import BM25Okapi
from app.knowledge.rag_models import Citation

@dataclass
class RetrievedChunk:
    text:str
    source: str
    source_type: str
    document_id: str
    location_type:str
    location_start: float | int
    location_end: float | int
    chunk_index: int
    vector_distance: float
    keyword_score: float = 0.0
    combined_score: float = 0.0

    def to_citation(self):
        if self.location_type=="page":
            label =  f"{self.source}, page {self.location_start}"
        elif self.location_type == "slide":
            label =  f"{self.source}, slide {self.location_start}"
        elif self.location_type == "timestamp":
            label = (
                f"{self.source}, "
                f"{self.location_start}-{self.location_end}"
            )
        else:
            label = (
                f"{self.source}, "
                f"{self.location_type} {self.location_start}"
            )

        return Citation(
            source=self.source,
            source_type=self.source_type,
            location_type=self.location_type,
            location_start=self.location_start,
            location_end=self.location_end,
            label=label,
            document_id=self.document_id,
            chunk_index=self.chunk_index,
        )


class HybridRetriever:
    def __init__(self, collection, embed_function):
        self.collection=collection
        self.embed_function=embed_function

    def retrieve(self,query: str, top_k:int = 8)->list[RetrievedChunk]:
        query = query.strip()
        if not query:
            raise ValueError("Query cannot be empty.")

        vector_results = self._vector_search(
            query=query, top_k = top_k
        )
        keyword_results = self._keyword_search(
            query=query, top_k = top_k
        )

        return self._merge_results(
            vector_results,
            keyword_results,
            top_k,
        )

    def _vector_search(self, query:str, top_k:int)->list[RetrievedChunk]:
        count = self.collection.count()
        if count == 0:
            return []

        embedding = self.embed_function([query])[0]

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        matches = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for text, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        ):

            location_type, start, end = (
                self._extract_location(metadata)
            )
            
            matches.append(RetrievedChunk(
                text=text,
                source=metadata["source_name"],
                source_type=metadata["source_type"],
                document_id=metadata["document_id"],
                location_type=location_type,
                location_start=start,
                location_end=end,
                chunk_index=int(metadata["chunk_index"]),
                vector_distance=float(distance),
            ))
        return matches

    def _keyword_search(self, query:str, top_k:int)->list[RetrievedChunk]:
        data = self.collection.get(include=["documents", "metadatas"])
        documents=data.get("documents", [])
        metadatas = data.get("metadatas", [])
        if not documents:
            return []

        tokenized_documents=[
            self._tokenize(text)
            for text in documents
        ]

        bm25 = BM25Okapi(tokenized_documents)
        query_tokens = self._tokenize(query)
        scores = bm25.get_scores(query_tokens)
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        results =[]
        for index in ranked_indices:

            score = float(scores[index])

            if score <= 0:
                continue

            metadata = metadatas[index]

            location_type, start, end = (
                self._extract_location(metadata)
            )

            results.append(RetrievedChunk(
                text=documents[index],
                source=metadata["source_name"],
                source_type=metadata["source_type"],
                document_id=metadata["document_id"],
                location_type=location_type,
                location_start=start,
                location_end=end,
                chunk_index=int(metadata["chunk_index"]),
                vector_distance=999.0,
                keyword_score=float(scores[index])
            ))

        return results

    def _merge_results(self, vector_results: list[RetrievedChunk], keyword_results: list[RetrievedChunk], top_k:int)-> list[RetrievedChunk]:
        combined = {}
        for rank, item in enumerate(vector_results):
            key = (item.document_id, item.chunk_index)
            combined[key] = item
            item.combined_score += (1.0 / (rank+1))
        max_keyword = max(
            (
                item.keyword_score
                for item in keyword_results
            ), default=1.0
        )

        for rank, item in enumerate(keyword_results):
            key = (
                item.document_id, item.chunk_index
            )
            if key not in combined:
                combined[key] = item

            combined[key].combined_score += (1.0 / (rank + 1))
            if max_keyword > 0:
                combined[key].keyword_score = (item.keyword_score / max_keyword)

        return sorted(
            combined.values(),
            key=lambda item:item.combined_score,
            reverse=True
        )[:top_k]

    @staticmethod
    def _extract_location(metadata):
        source_type = metadata["source_type"]
        if source_type=="video":
            location_type="timestamp"
            start = float(metadata["start_seconds"])
            end = float(metadata["end_seconds"])
        elif source_type == "pptx":
            location_type="slide"
            start = int(metadata["location_number"])
            end=start
        else:
            location_type="page"
            start = int(metadata.get("page_number", metadata.get("location_number", 1)))
            end = start

        return (location_type, start, end)

    

    
    @staticmethod
    def _tokenize(text:str)->list[str]:
        return [
            token.lower()
            for token in text.split()
            if token.strip()
        ]