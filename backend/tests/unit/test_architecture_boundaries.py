from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SOURCE = BACKEND / "src/fabricassist"
REPOSITORY = BACKEND.parent


def python_sources(path: Path) -> list[Path]:
    return sorted(path.rglob("*.py"))


def imports(path: Path) -> set[str]:
    modules: set[str] = set()
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_application_and_domain_do_not_import_infrastructure_sdks() -> None:
    forbidden = (
        "boto3",
        "botocore",
        "celery",
        "redis",
        "upstash",
        "google.genai",
    )
    violations: list[str] = []
    for path in python_sources(SOURCE / "application") + python_sources(SOURCE / "domain"):
        for module in imports(path):
            if module in forbidden or module.startswith(tuple(f"{name}." for name in forbidden)):
                violations.append(f"{path.relative_to(BACKEND)} imports {module}")
    assert violations == []


def test_application_capabilities_do_not_read_global_settings() -> None:
    capability_services = (
        "analysis.py",
        "conversations.py",
        "job_execution.py",
        "product_information.py",
    )
    for name in capability_services:
        path = SOURCE / "application" / name
        assert "fabricassist.settings" not in imports(path), name
        assert "Settings" not in path.read_text(), name


def test_routes_do_not_select_outbound_adapter_technologies() -> None:
    route_source = "\n".join(path.read_text() for path in python_sources(SOURCE / "api/routes"))
    for forbidden in (
        "create_evidence_provider(",
        "create_care_planning_provider(",
        "create_conversation_provider(",
        "create_object_storage(",
        "create_product_information_provider(",
        "JobDispatcherType.",
        "ModelCapabilityProvider.",
        "ObjectStorageBackend.",
        "ProductInformationProviderType.",
    ):
        assert forbidden not in route_source


def test_garment_history_application_contract_is_transport_neutral() -> None:
    path = SOURCE / "application" / "garment_history.py"
    forbidden = {"sqlalchemy", "fabricassist.application.object_storage"}
    assert imports(path).isdisjoint(forbidden)
    assert "fabricassist.infrastructure.persistence" not in path.read_text()


def test_valkey_capability_adapters_do_not_import_sibling_capabilities() -> None:
    capabilities = ("cache", "concurrency", "rate_limits")
    for capability in capabilities:
        for path in python_sources(SOURCE / "infrastructure" / capability):
            modules = imports(path)
            for sibling in capabilities:
                if sibling != capability:
                    assert not any(
                        module.startswith(f"fabricassist.infrastructure.{sibling}")
                        for module in modules
                    ), f"{path.name} imports sibling {sibling}"


def test_frontend_screens_use_generated_transport_not_direct_fetch() -> None:
    app_root = REPOSITORY / "frontend/apps/client/src"
    violations = [
        str(path.relative_to(REPOSITORY))
        for path in sorted(app_root.rglob("*.ts*"))
        if "/platform/" not in path.as_posix() and "fetch(" in path.read_text()
    ]
    assert violations == []
