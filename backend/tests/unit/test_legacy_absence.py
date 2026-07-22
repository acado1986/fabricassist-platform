from pathlib import Path

from fabricassist.api.routes.scans import ResultResponse


def test_legacy_care_execution_is_absent() -> None:
    files = "\n".join(path.read_text() for path in Path("src/fabricassist").rglob("*.py"))
    assert "def decide_care(" not in files
    assert "class LabelExtractionPayload" not in files


def test_legacy_roles_and_narrow_answer_contract_are_absent() -> None:
    files = "\n".join(path.read_text() for path in Path("src/fabricassist").rglob("*.py"))

    assert '"garment", "care_label"' not in files
    assert "fallback renderer" not in files.lower()
    assert "answer" not in ResultResponse.model_fields
    assert "result" in ResultResponse.model_fields
