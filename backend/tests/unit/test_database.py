from __future__ import annotations

from fabricassist.infrastructure.database import normalise_database_url


def test_postgresql_url_uses_psycopg_dialect() -> None:
    assert normalise_database_url("postgresql://localhost/fabricassist") == (
        "postgresql+psycopg://localhost/fabricassist"
    )
