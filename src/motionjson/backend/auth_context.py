from __future__ import annotations

import sqlite3
from typing import Any, Callable, Mapping, Protocol

from .deployment import HOSTED_DEPLOYMENT_MODES
from .models import UnauthorizedError


LocalUserFactory = Callable[[sqlite3.Connection], dict[str, Any]]


class AuthContext(Protocol):
    mode: str

    def require_user(
        self,
        conn: sqlite3.Connection,
        *,
        headers: Mapping[str, str] | None = None,
        local_user_factory: LocalUserFactory,
    ) -> dict[str, Any]:
        ...


class LocalSingleUserAuthContext:
    mode = "local_single_user"

    def require_user(
        self,
        conn: sqlite3.Connection,
        *,
        headers: Mapping[str, str] | None = None,
        local_user_factory: LocalUserFactory,
    ) -> dict[str, Any]:
        del headers
        return local_user_factory(conn)


class FailClosedHostedAuthContext:
    def __init__(self, *, mode: str):
        self.mode = mode

    def require_user(
        self,
        conn: sqlite3.Connection,
        *,
        headers: Mapping[str, str] | None = None,
        local_user_factory: LocalUserFactory,
    ) -> dict[str, Any]:
        del conn, headers, local_user_factory
        raise UnauthorizedError(
            "hosted deployment mode requires a configured auth provider; Local UI single-user fallback is disabled"
        )


def auth_context_for_deployment(deployment: Mapping[str, Any]) -> AuthContext:
    mode = str(deployment.get("mode") or "local_single_user")
    if mode in HOSTED_DEPLOYMENT_MODES:
        return FailClosedHostedAuthContext(mode=mode)
    return LocalSingleUserAuthContext()
