from app.evaluation import answer_context_metrics, citation_metrics, evaluate_dataset,  retrieval_metrics, evaluate_recorded_answer, evaluate_live_retrieval_case
def test_retrieval_precision_and_recall():
    result = retrieval_metrics(
        retrieved_ids=["a", "b", "c"],
        relevant_ids=["b", "c", "d"],
    )
    assert result["precision_at_k"] == 0.6667
    assert result["recall_at_k"] == 0.6667


def test_empty_retrieval_does_not_crash():
    result = retrieval_metrics([], ["expected"])
    assert result["precision_at_k"] == 0.0
    assert result["recall_at_k"] == 0.0


def test_answer_context_metrics():
    result = answer_context_metrics(
        answer="BFS uses a queue",
        context="BFS explores vertices using a queue",
        reference_answer="BFS uses a queue",
    )
    assert result["answer_empty"] is False
    assert result["context_empty"] is False
    assert result["answer_context_token_overlap"] > 0
    assert result["reference_token_recall"] == 1.0


def test_pdf_citation_requires_page():
    result = citation_metrics([
        {"source_id": "notes", "source_type": "pdf"}
    ])
    assert result["valid_count"] == 0
    assert result["malformed_indices"] == [0]


def test_pptx_citation_requires_slide():
    result = citation_metrics([
        {"source_id": "slides", "source_type": "pptx", "slide": 4}
    ], known_source_ids={"slides"})
    assert result["valid_count"] == 1


def test_video_citation_requires_timestamp():
    result = citation_metrics([
        {
            "source_id": "lecture",
            "source_type": "video",
            "timestamp": "00:01:20",
        }
    ], known_source_ids={"lecture"})
    assert result["valid_count"] == 1


def test_unknown_citation_source_fails_validation():
    result = citation_metrics(
        [{
            "source_id": "not-real",
            "source_type": "video",
            "timestamp": "00:01:20",
        }],
        known_source_ids={"real"},
    )
    assert result["valid_count"] == 0
    assert result["unknown_source_indices"] == [0]


def test_abstention_is_detected():
    result = evaluate_recorded_answer({
        "case_id": "unknown",
        "answer": "I cannot determine this from the provided material.",
        "context": "Only arrays are discussed.",
        "citations": [],
        "context_required": True,
        "citations_required": False,
        "expect_abstention": True,
    })
    assert result["checks"]["abstention_signaled"] is True
    assert result["passed"] is True


def test_required_invalid_citation_fails_case():
    result = evaluate_recorded_answer({
        "case_id": "invalid",
        "answer": "The instructor discusses recursion.",
        "context": "The lecture discusses recursion.",
        "citations": [
            {"source_id": "lecture", "source_type": "video"}
        ],
        "citations_required": True,
    })
    assert result["checks"]["citations_valid_when_required"] is False
    assert result["passed"] is False


def test_live_retrieval_uses_study_service_search():
    class FakeService:
        def search(self, query, top_k=5):
            assert query == "breadth first search"
            assert top_k == 2
            return [
                {
                    "document_id": "doc-1",
                    "chunk_index": 2,
                    "source": "graph-notes.pdf",
                    "text": "Breadth first search uses a queue.",
                    "distance": 0.1,
                    "page_number": 3,
                },
                {
                    "document_id": "doc-2",
                    "chunk_index": 4,
                    "source": "unrelated.pdf",
                    "text": "Sorting algorithms arrange items.",
                    "distance": 0.4,
                    "page_number": 1,
                },
            ]

    result = evaluate_live_retrieval_case(
        FakeService(),
        {
            "case_id": "retrieval-1",
            "question": "breadth first search",
            "top_k": 2,
            "relevant_source_names": ["graph-notes.pdf"],
            "expected_terms": ["queue"],
            "minimum_precision": 0.5,
            "minimum_term_coverage": 1.0,
        },
    )
    assert result["retrieved_count"] == 2
    assert result["precision_at_k"] == 0.5
    assert result["expected_term_coverage"] == 1.0
    assert result["passed"] is True


def test_answer_dataset_generates_report(tmp_path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(
        """
        [
          {
            "case_id": "ok",
            "answer": "BFS uses a queue.",
            "context": "BFS uses a queue.",
            "citations": [],
            "context_required": true,
            "citations_required": false
          }
        ]
        """,
        encoding="utf-8",
    )

    report = evaluate_dataset(dataset)
    assert report["total_cases"] == 1
    assert report["passed_cases"] == 1
    assert report["pass_rate"] == 1.0
