from pathlib import Path


def test_legacy_care_execution_is_absent() -> None:
    files = "\n".join(path.read_text() for path in Path("src/fabricassist").rglob("*.py"))
    assert "def decide_care(" not in files
    assert "class LabelExtractionPayload" not in files
