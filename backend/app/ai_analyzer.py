import base64
from openai import OpenAI
from app.core.config import settings
from app.knowledge.schemas import DiagramAnalysis, TopicAnalysis

class AIAnalyzer:
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        self.client = OpenAI(ap_key=settings.openai_api_key)

    def analyze_topic(self, text:str)->TopicAnalysis:
        text = text.strip()
        if not text:
            raise ValueError("Text cannot be empty.")

        response = self.client.responses.parse(
            model=settings.topic_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an educational "
                        "knowledge extraction system. "
                        "Analyze the supplied course material. "
                        "Identify the major topic, subtopics, "
                        "concepts, prerequisites and keywords. "
                        "Do not invent concepts that are not "
                        "supported by the supplied material."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this educational material:\n\n"
                        f"{text}"
                    ),
                },
            ],
            text_format=TopicAnalysis,
        )

        result = response.output_parsed

        if result is None:
            raise ValueError("The model did not return structured topic data.")

        return result

    def analyze_image(self, image_bytes:bytes, image_extension:str, context_text:str="")->DiagramAnalysis:
        if not image_bytes:
            raise ValueError("Image data cannot be empty.")
        
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = self._get_mime_type(image_extension)
        prompt = (
            "Analyze this educational image or diagram. "
            "Identify what it represents, its components, "
            "relationships between components, concepts "
            "being taught, and its educational value. "
            "Do not invent information that cannot be "
            "reasonably inferred from the visual."
        )

        if context_text.strip():
            prompt += (
                "\n\nNearby source text for context:\n"
                f"{context_text[:5000]}"
            )

        response = self.client.responses.parse(
            model=settings.vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{mime_type};"
                                f"base64,{encoded}"
                            ),
                            "detail": "auto",
                        },
                    ],
                }
            ],
            text_format=DiagramAnalysis,
        )

        result = response.output_parsed
        if result is None:
            raise ValueError("The model did not return structured diagram analysis of these images.")

        return result

    @staticmethod
    def _get_mime_type(extension:str)->str:
        extension = extension.lower().lstrip(".")
        mapping = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
        }

        if extension not in mapping:
            raise ValueError(f"Unsupported image extension: {extension}")
        return mapping[extension]