"""Helpers compartidos por los modelos."""

from datetime import UTC, datetime
from uuid import uuid4


def new_uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)
