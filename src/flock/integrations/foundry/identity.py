"""Resolve the trusted principal of a Foundry request."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


HOSTED_ENVIRONMENT_VARIABLE = "FOUNDRY_HOSTING_ENVIRONMENT"


class IdentityRequiredError(PermissionError):
    """The request carries no platform user identity and none may be assumed."""


def running_in_foundry() -> bool:
    """True inside a Foundry hosted-agent container."""
    return bool(os.environ.get(HOSTED_ENVIRONMENT_VARIABLE))


@dataclass(frozen=True)
class IdentityPolicy:
    """Map Foundry's platform identity to a workflow principal.

    In a hosted container the gateway sets ``x-agent-user-id``; the SDK exposes
    it as ``platform_context.user_id_key`` - an opaque per-user partition key
    (not an Entra tenant id). The header is trusted only inside a Foundry
    hosted container (or in explicit local development): anywhere else a
    direct caller could set it. Requests without a trusted identity are
    rejected rather than falling back to one shared principal.

    Attributes:
        required: Reject requests without a trusted user identity (default).
            Set ``False`` only for applications that do not partition anything
            by principal (public outputs, no per-user history or storage): such
            requests then run with ``principal_id=None`` - never as a shared
            named principal.
        local_development: Explicit opt-in for running outside Foundry: requests
            without a user key get ``local_principal``. Refused inside a hosted
            container.
        local_principal: Principal used in local development mode.
        resolve: Optional mapping from the user key to your own principal id
            (for example a tenant lookup). Must not trust request payloads.
    """

    required: bool = True
    local_development: bool = False
    local_principal: str = "local-developer"
    resolve: Callable[[str], str] | None = None

    def __post_init__(self) -> None:
        if self.local_development and running_in_foundry():
            raise ValueError(
                "IdentityPolicy(local_development=True) must not be used in a "
                "Foundry hosted container."
            )

    def principal_for(self, context: Any) -> str | None:
        """Principal of the request behind ``context`` (a ``ResponseContext``)."""
        platform = getattr(context, "platform_context", None)
        user_key = getattr(platform, "user_id_key", None)
        trusted = self.local_development or running_in_foundry()
        if user_key and trusted:
            return self.resolve(user_key) if self.resolve else user_key
        if self.local_development:
            return self.local_principal
        if user_key:
            raise IdentityRequiredError(
                "Platform identity headers are only trusted inside a Foundry hosted "
                "container."
            )
        if not self.required:
            return None
        raise IdentityRequiredError("The request carries no platform user identity.")


__all__ = [
    "HOSTED_ENVIRONMENT_VARIABLE",
    "IdentityPolicy",
    "IdentityRequiredError",
    "running_in_foundry",
]
