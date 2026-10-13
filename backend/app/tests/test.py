from app.service import StudyService

def test_duplicate_pdf_is_not_indexed_twice(tmp_path):
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text(
        (72,72), "This is a test PDF for duplicate detection."
    )

    pdf_bytes = pdf.tobytes()
    pdf.close()

    service = StudyService(
        database_path = str(tmp_path / "test.db"),
        chroma_path = str(tmp_path / "chroma"),
    )

    first = service.ingest_document("bfs.pdf", pdf_bytes)

    assert first["status"] == "ready"

    second = service.ingest_document("bfs-copy.pdf", pdf_bytes)

    assert second["status"] == "duplicate"
    assert(second["document_id"] == first["document_id"])