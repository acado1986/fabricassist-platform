from fabricassist.application.auth import (
    decode_access_token,
    hash_password,
    issue_access_token,
    verify_password,
)
from fabricassist.infrastructure.persistence.models import User
from fabricassist.settings import Settings


def test_argon2id_password_hashes_do_not_echo_password() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "correct-horse-battery-staple")
    assert not verify_password(password_hash, "wrong-password-value")


def test_access_token_carries_tenant_scoped_identity() -> None:
    user = User(
        email="person@example.test",
        password_hash="x",
        tenant_id="00000000-0000-0000-0000-000000000001",
        role="customer",
    )
    claims = decode_access_token(issue_access_token(user, Settings()), Settings())
    assert claims["sub"] == str(user.id)
    assert claims["tenant_id"] == "00000000-0000-0000-0000-000000000001"
    assert claims["role"] == "customer"
