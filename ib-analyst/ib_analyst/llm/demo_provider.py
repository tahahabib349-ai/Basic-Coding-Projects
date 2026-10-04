"""Offline demo provider: lets the whole app run without an API key.

It does NOT analyse anything. It returns a structurally valid but empty report
so the user can see the pipeline working: document ingestion, Excel
inspection and the deterministic calculations are all real; only the AI
commentary is replaced by clearly-marked placeholders.
"""

from __future__ import annotations

from .base import LLMProvider, LLMResult

DEMO_NOTE = "[DEMO MODE] No AI was used. Add a Gemini API key for real analysis."


class DemoProvider(LLMProvider):
    name = "demo"
    model = "offline-demo"
    is_demo = True

    def generate_json(self, *, system: str, prompt: str, schema: dict, task: dict | None = None) -> LLMResult:
        task = task or {}
        if task.get("kind") == "extract_figures":
            return LLMResult(data={"figures": []}, provider=self.name, model=self.model,
                             notes=["Demo mode: no figures extracted from PDFs."])
        sections = [
            {
                "heading": heading,
                "commentary": "",
                "points": [
                    {"statement": DEMO_NOTE, "label": "MISSING", "source": ""}
                ],
                "table": None,
            }
            for heading in task.get("sections", [])
        ]
        data = {
            "report_title": task.get("title", "Analysis (demo)"),
            "sections": sections,
            "issues": [],
        }
        return LLMResult(data=data, provider=self.name, model=self.model)

    def test_connection(self) -> str:
        return "Demo mode is active: no connection to any AI service is made."
