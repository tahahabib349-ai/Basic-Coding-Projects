"""Shared test fixtures: sample documents and a scripted (fake) AI provider."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "sample_data"
SAMPLE_FILES = [
    "Information_Memorandum_Thar_Sun.pdf",
    "Term_Sheet_Thar_Sun.pdf",
    "Facility_Agreement_Extract_Thar_Sun.pdf",
    "Financial_Model_Thar_Sun.xlsx",
]

from ib_analyst.llm.base import LLMProvider, LLMResult  # noqa: E402


@pytest.fixture(scope="session")
def sample_paths():
    if not all((SAMPLES / f).exists() for f in SAMPLE_FILES):
        subprocess.run([sys.executable, str(SAMPLES / "generate_samples.py")], check=True)
    return {f: SAMPLES / f for f in SAMPLE_FILES}


@pytest.fixture(scope="session")
def sample_docs(sample_paths):
    from ib_analyst.ingestion.loader import ingest_files

    res = ingest_files([(name, p.read_bytes()) for name, p in sample_paths.items()])
    assert not res.errors, res.errors
    return res.documents


class ScriptedProvider(LLMProvider):
    """Fake AI that returns pre-written answers, for testing without an API key."""

    name = "scripted"
    model = "scripted-test"

    def __init__(self, report=None, figures=None):
        self.report = report or {"report_title": "Test", "sections": [], "issues": []}
        self.figures = figures or []
        self.prompts = []

    def test_connection(self):
        return "ok"

    def generate_json(self, *, system, prompt, schema, task=None):
        self.prompts.append((task or {}).get("kind"))
        self.last_prompt = prompt
        if (task or {}).get("kind") == "extract_figures":
            return LLMResult(data={"figures": self.figures}, provider=self.name, model=self.model)
        return LLMResult(data=self.report, provider=self.name, model=self.model, input_tokens=100, output_tokens=50)


@pytest.fixture
def scripted():
    return ScriptedProvider
