"""QStash signed HTTP delivery verification at the inbound adapter boundary."""

from __future__ import annotations

import base64
import hashlib
from typing import cast

import jwt
from pydantic import TypeAdapter, ValidationError

from fabricassist.application.job_execution import PermanentJobMessageError
from fabricassist.application.jobs import JobMessage
from fabricassist.infrastructure.jobs.config import QStashVerifierConfig


class DeliveryVerificationError(Exception):
    """A request which must not be allowed to enter the job executor."""


class QStashDeliveryVerifier:
    """Verify rotating signing keys, body digest, and the exact destination."""

    def __init__(self, config: QStashVerifierConfig) -> None:
        self._config = config

    def verify(self, *, raw_body: bytes, signature: str | None) -> None:
        if not signature:
            raise DeliveryVerificationError("missing signature")
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw_body).digest()).decode().rstrip("=")
        keys = (
            self._config.current_signing_key,
            self._config.next_signing_key,
        )
        for key in keys:
            if not key:
                continue
            try:
                claims = jwt.decode(
                    signature,
                    key,
                    algorithms=["HS256"],
                    issuer="Upstash",
                    options={"require": ["iss", "sub", "exp", "nbf", "body"]},
                )
            except jwt.PyJWTError:
                continue
            body_claim = str(claims.get("body", "")).rstrip("=")
            if claims.get("sub") == self._config.destination_url and body_claim == digest:
                return
        raise DeliveryVerificationError("invalid signature")

    @staticmethod
    def parse(raw_body: bytes) -> JobMessage:
        try:
            return cast(JobMessage, TypeAdapter(JobMessage).validate_json(raw_body))
        except ValidationError as error:
            raise PermanentJobMessageError("permanently invalid job message") from error


def create_qstash_delivery_verifier(
    current_signing_key: str,
    next_signing_key: str,
    destination_url: str,
) -> QStashDeliveryVerifier:
    """Build the inbound verifier from its adapter-specific configuration."""
    return QStashDeliveryVerifier(
        QStashVerifierConfig(
            current_signing_key=current_signing_key,
            next_signing_key=next_signing_key,
            destination_url=destination_url,
        )
    )
