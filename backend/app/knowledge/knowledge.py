import uuid
import sqlite3
from app.ai_analyzer import AIAnalyzer

class KnowledgeBuilder:
    def __init__(self, database_path:str):
        self.database_path = database_path
        self.analyzer = AIAnalyzer()

    def analyzer_text_unit(self, document_id:str, source_type:str, location_number:int, chunk_index:int, text:str)->dict:
        analysis = self.analyzer.analyze_topic(text)
        topic_id=str(uuid.uuid4())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO topics(id, document_id, name, description) VALUES (?,?,?,?)
                """,
                (topic_id, document_id, analysis.topic(
                    "Automatically extracted"
                    f"from {source_type}"
                    f"location {location_number}"
                )),
            )

            content_unit_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO content_units(id, document_id, topic_id, source_type, location_number, chunk_index, text, content_type) VALUES (?,?,?,?,?,?,?,?)
                """,
                (content_unit_id, document_id, topic_id, source_type, location_number, chunk_index, text,"text")
            )

            for concept in analysis.concepts:
                connection.execute(
                    """
                    INSERT INTO concepts(id, topic_id, name, explanation) VALUES (?,?,?,?)
                    """,
                    (str(uuid.uuid4()), topic_id, conecpt.name, concept.explanation)
                )

            for prerequisite in (analysis.prerequisite):
                connection.execute(
                    """
                    INSERT INTO prerequisites(id, topic_id, prerequisite_name) VALUES (?,?,?)
                    """,
                    (str(uuid.uuid4()), topic_id, prerequisite)
                )

        return {
            "content_unit_id": content_unit_id,
            "topic_id": topic_id,
            "topic": analysis.topic,
            "subtopics": analysis.subtopics,
            "concepts": [
                concept.model_dump()
                for concept in analysis.concepts
            ],
            "prerequisites": analysis.prerequisites,
            "keywords": analysis.keywords,
        }

    def analyze_diagram(self, document_id:str, content_unit_id:str, source_type:str, location_number:int, image_index:int, extension:str, image_data:bytes, context_text:str="")->dict:

        analysis = self.analyzer.analyze_image(
        image_bytes=image_data,
        image_extension=extension,
        context_text=context_text,
        )

        diagram_id = str(uuid.uuid4())
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO diagrams(id, document_id, content_unit_id, source_type, location_number, image_index, extension, width, height, diagram_type, title, description, educational_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (diagram_id, document_id, content_unit_id, source_type, location_number, image_index, extension, None, None, analysis.diagram_type, analysis.title, analysis.description, analysis.educational_value)
            )

        return {
            "diagram_id": diagram_id,
        "diagram_type": analysis.diagram_type,
        "title": analysis.title,
        "description": analysis.description,
        "components": analysis.components,
        "relationships": analysis.relationships,
        "concepts": analysis.concepts,
        "educational_value": analysis.educational_value
        }