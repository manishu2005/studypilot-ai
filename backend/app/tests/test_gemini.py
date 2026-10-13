from app.config import settings
from app.gemini_client import get_gemini_client
import os
import pytest

def test_gemini_configuration():
    assert settings.gemini_api_key
    assert settings.gemini_model
    assert get_gemini_client() is not None

@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_GEMINI_INTEGRATION") != "1",
    reason="Set RUN_GEMINI_INTEGRATION=1 to test the live Gemini API.",
)


def test_gemini_connection():

    client = get_gemini_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents="Reply with exactly: GEMINI_OK",
    )

    assert response.text
    assert "GEMINI_OK" in response.text