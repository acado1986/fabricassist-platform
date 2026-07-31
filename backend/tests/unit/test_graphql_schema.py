from __future__ import annotations

from fabricassist.api.graphql_schema import create_schema
from fabricassist.settings import Settings


def test_schema_exposes_canonical_queries_and_mutations() -> None:
    schema = create_schema(Settings(environment="test"))
    sdl = schema.as_str()

    for field in (
        "currentUser",
        "scans",
        "scan(",
        "garments",
        "messages",
        "analysisRevision",
        "usage",
        "createScan",
        "renameGarment",
        "submitFeedback",
    ):
        assert field in sdl


def test_schema_has_query_resource_limits() -> None:
    schema = create_schema(Settings(environment="test", graphql_max_depth=3))

    extension_names = {type(extension).__name__ for extension in schema.extensions}
    assert extension_names >= {"QueryDepthLimiter", "MaxTokensLimiter", "MaxAliasesLimiter"}
