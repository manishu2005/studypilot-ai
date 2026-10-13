from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import date
import json
import logging
import re
from typing import Any, Literal

from groq import Groq
from app.core.config import settings
from app.core.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)

SourceType = Literal["pdf", "pptx", "video"]


@dataclass(frozen=True)
class SourceReference:
    """A reference to the original learning material."""

    source_id: str
    source_type: SourceType
    page_number: int | None = None
    slide_number: int | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    quote: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.source_id.strip():
            errors.append("Source reference requires a non-empty source_id.")

        if self.source_type == "pdf":
            if self.page_number is None or self.page_number < 1:
                errors.append("PDF references require page_number >= 1.")

        elif self.source_type == "pptx":
            if self.slide_number is None or self.slide_number < 1:
                errors.append("PPTX references require slide_number >= 1.")

        elif self.source_type == "video":
            if self.start_seconds is None or self.start_seconds < 0:
                errors.append("Video references require start_seconds >= 0.")

            if (
                self.end_seconds is not None
                and self.start_seconds is not None
                and self.end_seconds < self.start_seconds
            ):
                errors.append("Video end_seconds must be >= start_seconds.")

        return errors


@dataclass
class ConceptNode:
    """A topic, subtopic, or concept in the course graph."""

    id: str
    title: str
    level: Literal["topic", "subtopic", "concept"]
    mastery: float = 0.0
    prerequisites: list[str] = field(default_factory=list)
    source_refs: list[SourceReference] = field(default_factory=list)
    due_date: str | None = None
    estimated_minutes: int = 20

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.id.strip():
            errors.append("Node id cannot be empty.")

        if not self.title.strip():
            errors.append(f"Node {self.id!r} requires a title.")

        if not 0.0 <= self.mastery <= 1.0:
            errors.append(f"Node {self.id!r}: mastery must be between 0 and 1.")

        if self.estimated_minutes < 1:
            errors.append(f"Node {self.id!r}: estimated_minutes must be >= 1.")

        if self.id in self.prerequisites:
            errors.append(f"Node {self.id!r} cannot depend on itself.")

        if len(self.prerequisites) != len(set(self.prerequisites)):
            errors.append(f"Node {self.id!r} contains duplicate prerequisites.")

        for source_ref in self.source_refs:
            errors.extend(source_ref.validate())

        if self.due_date:
            try:
                date.fromisoformat(self.due_date)
            except ValueError:
                errors.append(f"Node {self.id!r}: due_date must use YYYY-MM-DD.")

        return errors


@dataclass
class GraphValidation:
    valid: bool
    errors: list[str]
    topological_order: list[str]


@dataclass
class PlannedTask:
    node_id: str
    title: str
    level: str
    priority: float
    mastery: float
    estimated_minutes: int
    reason: str
    prerequisites: list[str]
    source_refs: list[dict[str, Any]]


class CourseGraph:
    """
    A directed graph where A in B.prerequisites means A must be
    learned before B.
    """

    def __init__(self, nodes: list[ConceptNode] | None = None):
        self.nodes: dict[str, ConceptNode] = {}

        for node in nodes or []:
            if node.id in self.nodes:
                raise ValueError(f"Duplicate node id: {node.id}")
            self.nodes[node.id] = node

    # =========================================================================
    # AI GRAPH GENERATION (Gemini -> Groq Fallback)
    # =========================================================================
    @classmethod
    def from_material(cls, material_context: str) -> CourseGraph:
        """Extracts concept nodes and prerequisite edges directly from text."""
        if not material_context or not material_context.strip():
            raise ValueError("No study material was supplied for graph extraction.")

        prompt = f"""
You are an expert curriculum architect.
Extract an academic prerequisite knowledge graph from the study material below.

Return a JSON object with this exact structure:
{{
  "nodes": [
    {{
      "id": "unique_lowercase_snake_case_id",
      "title": "Clear Concept Title",
      "level": "topic" | "subtopic" | "concept",
      "prerequisites": ["other_node_id"],
      "estimated_minutes": 20,
      "source_refs": [
        {{
          "source_id": "document_id_or_source_name",
          "source_type": "pdf" | "pptx" | "video",
          "page_number": 1,
          "slide_number": null,
          "start_seconds": null,
          "end_seconds": null,
          "quote": "Key sentence from text"
        }}
      ]
    }}
  ]
}}

Rules:
1. Every node id must be unique lowercase snake_case (e.g. 'vectors', 'eigenvalues').
2. Node A must be in Node B's prerequisites IF AND ONLY IF A must be learned before B.
3. No self-dependencies.
4. Only reference prerequisites that are present in the 'nodes' list.
5. Return ONLY raw JSON without markdown formatting or code blocks.

Study Material:
====================
{material_context}
====================
"""
        raw_json = None

        # 1. Primary: Gemini
        try:
            client = get_gemini_client()
            gemini_model = getattr(settings, "gemini_model", "gemini-1.5-flash")
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            if response.text:
                raw_json = response.text
                logger.info("Course graph extracted via Gemini.")
        except Exception as exc:
            logger.warning("Gemini failed during graph extraction: %s. Falling back to Groq...", exc)

        # 2. Fallback: Groq
        if not raw_json:
            if not getattr(settings, "groq_api_key", None):
                raise RuntimeError("Gemini failed and GROQ_API_KEY is not configured.")

            groq_client = Groq(api_key=settings.groq_api_key)
            groq_model = getattr(settings, "groq_model", "llama-3.3-70b-versatile")
            response = groq_client.chat.completions.create(
                model=groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a curriculum parser. Output only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_json = response.choices[0].message.content
            logger.info("Course graph extracted via Groq fallback.")

        # Clean JSON fences if present
        text = raw_json.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)

        data = json.loads(text)
        nodes_raw = data.get("nodes", [])
        if not nodes_raw:
            raise ValueError("No concept nodes were extracted from the material.")

        valid_ids = {n["id"] for n in nodes_raw if "id" in n}

        concept_nodes: list[ConceptNode] = []
        for item in nodes_raw:
            # Clean and validate prerequisites
            prereqs = [
                p for p in item.get("prerequisites", [])
                if p in valid_ids and p != item["id"]
            ]
            seen_prereqs = []
            for p in prereqs:
                if p not in seen_prereqs:
                    seen_prereqs.append(p)

            refs = []
            for ref_data in item.get("source_refs", []):
                refs.append(
                    SourceReference(
                        source_id=ref_data.get("source_id", "doc"),
                        source_type=ref_data.get("source_type", "pdf"),
                        page_number=ref_data.get("page_number"),
                        slide_number=ref_data.get("slide_number"),
                        start_seconds=ref_data.get("start_seconds"),
                        end_seconds=ref_data.get("end_seconds"),
                        quote=ref_data.get("quote"),
                    )
                )

            concept_nodes.append(
                ConceptNode(
                    id=item["id"],
                    title=item["title"],
                    level=item.get("level", "concept"),
                    mastery=float(item.get("mastery", 0.0)),
                    prerequisites=seen_prereqs,
                    source_refs=refs,
                    due_date=item.get("due_date"),
                    estimated_minutes=max(5, int(item.get("estimated_minutes", 20))),
                )
            )

        return cls(concept_nodes)

    def validate(self) -> GraphValidation:
        errors: list[str] = []

        for node in self.nodes.values():
            errors.extend(node.validate())

            for prerequisite_id in node.prerequisites:
                if prerequisite_id not in self.nodes:
                    errors.append(
                        f"Node {node.id!r} references missing prerequisite {prerequisite_id!r}."
                    )

        if errors:
            return GraphValidation(
                valid=False,
                errors=errors,
                topological_order=[],
            )

        indegree = {node_id: 0 for node_id in self.nodes}
        dependents: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}

        for node in self.nodes.values():
            for prerequisite_id in node.prerequisites:
                indegree[node.id] += 1
                dependents[prerequisite_id].append(node.id)

        ready = sorted(
            node_id for node_id, degree in indegree.items() if degree == 0
        )
        order: list[str] = []

        while ready:
            current = ready.pop(0)
            order.append(current)

            for dependent_id in sorted(dependents[current]):
                indegree[dependent_id] -= 1

                if indegree[dependent_id] == 0:
                    ready.append(dependent_id)
                    ready.sort()

        if len(order) != len(self.nodes):
            cyclic_nodes = sorted(
                node_id for node_id, degree in indegree.items() if degree > 0
            )
            errors.append(
                "Prerequisite cycle detected involving: "
                + ", ".join(cyclic_nodes)
            )

        return GraphValidation(
            valid=not errors,
            errors=errors,
            topological_order=order if not errors else [],
        )

    def _prerequisite_closure(self, node_id: str) -> set[str]:
        """Return every direct and indirect prerequisite of a node."""
        found: set[str] = set()
        stack = list(self.nodes[node_id].prerequisites)

        while stack:
            prerequisite_id = stack.pop()
            if prerequisite_id in found:
                continue

            found.add(prerequisite_id)
            stack.extend(self.nodes[prerequisite_id].prerequisites)

        return found

    def build_study_plan(
        self,
        *,
        today: date | None = None,
        limit: int = 10,
        max_minutes: int | None = None,
        mastery_threshold: float = 0.85,
    ) -> list[PlannedTask]:
        if limit < 1:
            raise ValueError("limit must be >= 1.")

        if max_minutes is not None and max_minutes < 1:
            raise ValueError("max_minutes must be >= 1.")

        if not 0.0 <= mastery_threshold <= 1.0:
            raise ValueError("mastery_threshold must be between 0 and 1.")

        validation = self.validate()
        if not validation.valid:
            raise ValueError(
                "Cannot plan from an invalid graph: "
                + "; ".join(validation.errors)
            )

        today = today or date.today()
        planned: list[PlannedTask] = []
        completed: set[str] = set()
        total_minutes = 0

        remaining = {
            node_id
            for node_id, node in self.nodes.items()
            if node.mastery < mastery_threshold
        }

        while remaining and len(planned) < limit:
            eligible: list[ConceptNode] = []

            for node_id in remaining:
                node = self.nodes[node_id]
                prerequisites_ready = all(
                    self.nodes[p].mastery >= mastery_threshold
                    or p in completed
                    for p in node.prerequisites
                )
                if prerequisites_ready:
                    eligible.append(node)

            if not eligible:
                break

            def priority(node: ConceptNode) -> tuple[float, str]:
                score = (1.0 - node.mastery) * 100.0

                if node.due_date:
                    due = date.fromisoformat(node.due_date)
                    days_until_due = (due - today).days

                    if days_until_due < 0:
                        score += 30.0
                    elif days_until_due == 0:
                        score += 20.0
                    elif days_until_due <= 3:
                        score += 10.0

                unmastered_children = sum(
                    1
                    for other in self.nodes.values()
                    if node.id in other.prerequisites
                    and other.mastery < mastery_threshold
                )
                score += min(unmastered_children * 5.0, 20.0)

                return score, node.id

            eligible.sort(
                key=lambda node: (
                    -priority(node)[0],
                    priority(node)[1],
                )
            )

            selected = eligible[0]

            if (
                max_minutes is not None
                and total_minutes + selected.estimated_minutes > max_minutes
            ):
                fitting = [
                    node
                    for node in eligible
                    if total_minutes + node.estimated_minutes <= max_minutes
                ]
                if not fitting:
                    break
                selected = fitting[0]

            missing_prerequisites = [
                prerequisite_id
                for prerequisite_id in selected.prerequisites
                if self.nodes[prerequisite_id].mastery < mastery_threshold
            ]

            reasons = []

            if selected.mastery < 0.40:
                reasons.append("low mastery")
            elif selected.mastery < mastery_threshold:
                reasons.append("mastery needs reinforcement")

            if selected.due_date:
                due = date.fromisoformat(selected.due_date)
                if due < today:
                    reasons.append("overdue review")
                elif due == today:
                    reasons.append("review due today")

            if missing_prerequisites:
                reasons.append(
                    "prerequisite gap: " + ", ".join(missing_prerequisites)
                )

            if not reasons:
                reasons.append("scheduled for reinforcement")

            planned.append(
                PlannedTask(
                    node_id=selected.id,
                    title=selected.title,
                    level=selected.level,
                    priority=round(priority(selected)[0], 2),
                    mastery=selected.mastery,
                    estimated_minutes=selected.estimated_minutes,
                    reason="; ".join(reasons),
                    prerequisites=list(selected.prerequisites),
                    source_refs=[
                        asdict(ref) for ref in selected.source_refs
                    ],
                )
            )

            total_minutes += selected.estimated_minutes
            completed.add(selected.id)
            remaining.remove(selected.id)

        return planned