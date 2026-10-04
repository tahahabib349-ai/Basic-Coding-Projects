"""The structure the AI must return, and the report objects built from it."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

LABELS = ("FACT", "CALCULATED", "INFERENCE", "MISSING")
RISKS = ("High", "Medium", "Low")


def report_schema(include_issues: bool) -> dict:
    point = {
        "type": "object",
        "properties": {
            "statement": {"type": "string"},
            "label": {"type": "string", "enum": list(LABELS)},
            "source": {"type": "string"},
        },
        "required": ["statement", "label", "source"],
    }
    table = {
        "type": "object",
        "properties": {
            "columns": {"type": "array", "items": {"type": "string"}},
            "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        },
        "required": ["columns", "rows"],
    }
    issue = {
        "type": "object",
        "properties": {
            "issue": {"type": "string"},
            "source": {"type": "string"},
            "why_it_matters": {"type": "string"},
            "risk": {"type": "string", "enum": list(RISKS)},
            "recommended_comment": {"type": "string"},
            "label": {"type": "string", "enum": list(LABELS)},
        },
        "required": ["issue", "source", "why_it_matters", "risk", "recommended_comment", "label"],
    }
    schema = {
        "type": "object",
        "properties": {
            "report_title": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "commentary": {"type": "string"},
                        "points": {"type": "array", "items": point},
                        "table": table,
                    },
                    "required": ["heading", "commentary", "points"],
                },
            },
            "issues": {"type": "array", "items": issue},
        },
        "required": ["report_title", "sections", "issues"] if include_issues else ["report_title", "sections"],
    }
    return schema


@dataclass
class Point:
    statement: str
    label: str
    source: str = ""
    flags: list[str] = field(default_factory=list)  # verification warnings added by the application


@dataclass
class Section:
    heading: str
    commentary: str = ""
    points: list[Point] = field(default_factory=list)
    table: dict | None = None
    flags: list[str] = field(default_factory=list)


@dataclass
class Issue:
    issue: str
    source: str
    why_it_matters: str
    risk: str
    recommended_comment: str
    label: str = "INFERENCE"
    flags: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    mode_key: str
    mode_title: str
    title: str
    sections: list[Section]
    issues: list[Issue]
    issues_title: str
    calculations: object  # CalculationResults
    model_issues: list  # list[ModelIssue] from workbook inspection
    documents: list  # list[SourceDocument]
    provider: str
    model: str
    is_demo: bool
    created_at: datetime = field(default_factory=datetime.now)
    context_notes: list[str] = field(default_factory=list)  # e.g. content omitted due to size
    warnings: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    unverified_figures: list = field(default_factory=list)

    @property
    def flagged_points(self) -> list[tuple[str, Point]]:
        return [(s.heading, p) for s in self.sections for p in s.points if p.flags]

    def label_counts(self) -> dict[str, int]:
        counts = {k: 0 for k in LABELS}
        for s in self.sections:
            for p in s.points:
                counts[p.label] = counts.get(p.label, 0) + 1
        return counts
