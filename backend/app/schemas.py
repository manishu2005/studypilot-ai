from pydantic import BaseModel, Field

class Concept(BaseModel):
    name:str=Field(description="Name of the concept")
    explanation:str=Field(description="Short explanation of the concept")

class TopicAnalysis(BaseModel):
    topic: str = Field(description="Major topic")
    subtopics: list[str] = Field(
        default_factory=list,
        description="Important subtopics"
    )

    concepts: list[Concept] = Field(
        default_factory=list,
        description="Important concepts"   
    )

    prerequisites: list[str] = Field(
        default_factory=list,
        description=("Concepts or topics a student should know before learning this material")
    )

    keywords: list[str] = Field(
        default_factory=list,
        description="Important keywords"
    )

class DiagramAnalysis(BaseModel):
    diagram_type: str = Field(
        description=(
            "Type of visual such as flowchart, "
            "architecture diagram, graph, table, "
            "chart, illustration, or figure."
        )
    )

    title: str = Field(
        default="",
        description="Title or inferred title."
    )

    description: str = Field(
        description="What the visual represents."
    )

    components: list[str] = Field(
        default_factory=list,
        description="Important visual components."
    )

    relationships: list[str] = Field(
        default_factory=list,
        description=(
            "Important relationships, flows, "
            "connections, arrows, or dependencies."
        )
    )

    concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Learning concepts represented by "
            "the visual."
        )
    )

    educational_value: str = Field(
        description=(
            "What a student should learn from "
            "this visual."
        )
    )