"""Resolve shared permissions for Agents, Skills, and knowledge bases."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class ResourcePermission(StrEnum):
    """Resource permission levels; numeric order decides whether permission suffices."""

    NONE = "none"
    READ = "read"
    MANAGE = "manage"


class ResourcePermissionDenied(PermissionError):
    """The current user lacks sufficient resource permission."""


class ShareableResource(Protocol):
    """Resource fields subject to permission resolution via share config."""

    created_by: str | None
    share_config: dict | None


@dataclass(frozen=True)
class ResourcePermissionPolicy:
    """Role ceilings allowed per resource type; excludes scope-matching logic."""

    role_ceiling: dict[str, ResourcePermission]


RESOURCE_PERMISSION_ORDER = {
    ResourcePermission.NONE: 0,
    ResourcePermission.READ: 1,
    ResourcePermission.MANAGE: 2,
}

DEFAULT_SCOPE = {"access_level": "global", "department_ids": [], "user_uids": []}
KNOWLEDGE_BASE_PERMISSION_POLICY = ResourcePermissionPolicy(
    role_ceiling={
        "user": ResourcePermission.READ,
        "admin": ResourcePermission.MANAGE,
        "superadmin": ResourcePermission.MANAGE,
    }
)
AGENT_PERMISSION_POLICY = ResourcePermissionPolicy(
    role_ceiling={
        "user": ResourcePermission.MANAGE,
        "admin": ResourcePermission.MANAGE,
        "superadmin": ResourcePermission.MANAGE,
    }
)
SKILL_PERMISSION_POLICY = AGENT_PERMISSION_POLICY


def _normalize_scope(scope: dict | None) -> dict | None:
    """Normalize a share scope and validate its access level and member lists."""

    if scope is None:
        return None
    if not isinstance(scope, dict):
        raise ValueError("Permission scope must be an object")

    access_level = scope.get("access_level") or "global"
    if access_level not in {"global", "department", "user"}:
        raise ValueError("Invalid resource permission scope")

    if access_level == "global":
        return DEFAULT_SCOPE.copy()
    if access_level == "department":
        department_ids = sorted({int(value) for value in scope.get("department_ids") or []})
        if not department_ids:
            raise ValueError("Department permission requires at least one department")
        return {"access_level": access_level, "department_ids": department_ids, "user_uids": []}

    user_uids = sorted({str(value).strip() for value in scope.get("user_uids") or [] if str(value).strip()})
    if not user_uids:
        raise ValueError("User permission requires at least one user")
    return {"access_level": access_level, "department_ids": [], "user_uids": user_uids}


def _validate_manage_scope(read_scope: dict | None, manage_scope: dict | None) -> None:
    """Ensure the manage scope never exceeds the read scope."""

    if not read_scope or not manage_scope or read_scope["access_level"] == "global":
        return

    read_level = read_scope["access_level"]
    manage_level = manage_scope["access_level"]
    if manage_level != read_level:
        raise ValueError("Manage scope must be contained within read scope")
    if read_level == manage_level == "department":
        if not set(manage_scope["department_ids"]).issubset(read_scope["department_ids"]):
            raise ValueError("Manage scope must be contained within read scope")
    elif read_level == manage_level == "user":
        if not set(manage_scope["user_uids"]).issubset(read_scope["user_uids"]):
            raise ValueError("Manage scope must be contained within read scope")


def normalize_permission_config(
    share_config: dict | None,
    *,
    allowed_access_levels: Collection[str] | None = None,
    unauthorized_access_level_message: str = "Current user may not use this resource share scope",
    strict: bool = False,
) -> dict:
    """Normalize and validate a v2 share config."""

    config = share_config if isinstance(share_config, dict) else {}
    if config.get("version") == 2:
        read_scope = _normalize_scope(config.get("read_scope"))
        manage_scope = _normalize_scope(config.get("manage_scope"))
        try:
            _validate_manage_scope(read_scope, manage_scope)
        except ValueError:
            if strict:
                raise
            # Keep historical values when reading legacy configs; strict
            # validation rejects out-of-range configs on save.
        normalized = {
            "version": 2,
            "read_scope": read_scope,
            "manage_scope": manage_scope,
        }
        if allowed_access_levels is not None:
            for scope in (normalized["read_scope"], normalized["manage_scope"]):
                if scope and scope["access_level"] not in allowed_access_levels:
                    raise ValueError(unauthorized_access_level_message)
        return normalized
    raise ValueError("Share config must use version 2")


def scope_matches(user: Any, scope: dict | None) -> bool:
    """Decide whether a user falls inside a share scope."""

    if not scope:
        return False
    access_level = scope.get("access_level")
    if access_level == "global":
        return True
    if access_level == "department":
        department_id = _value(user, "department_id")
        try:
            return department_id is not None and int(department_id) in scope.get("department_ids", [])
        except (TypeError, ValueError):
            return False
    if access_level == "user":
        return str(_value(user, "uid", "") or "") in scope.get("user_uids", [])
    return False


def _value(source: Any, key: str, default: Any = None) -> Any:
    """Read an attribute from a dict or object; unifies permission-resolution inputs."""

    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _minimum_permission(left: ResourcePermission, right: ResourcePermission) -> ResourcePermission:
    """Return the lower of two permissions by permission-level order."""

    return left if RESOURCE_PERMISSION_ORDER[left] <= RESOURCE_PERMISSION_ORDER[right] else right


def resolve_resource_permission(
    user: Any,
    resource: ShareableResource,
    policy: ResourcePermissionPolicy,
) -> ResourcePermission:
    """Resolve the effective permission from ownership, share scopes, and role ceiling."""

    if _value(user, "role") == "superadmin":
        return ResourcePermission.MANAGE

    raw_share_config = _value(resource, "share_config")
    config = normalize_permission_config(
        raw_share_config,
    )
    if str(_value(resource, "created_by", "") or "") == str(_value(user, "uid", "") or ""):
        return ResourcePermission.MANAGE
    elif scope_matches(user, config["manage_scope"]) and (
        config["read_scope"] is None or scope_matches(user, config["read_scope"])
    ):
        granted = ResourcePermission.MANAGE
    elif scope_matches(user, config["read_scope"]):
        granted = ResourcePermission.READ
    else:
        granted = ResourcePermission.NONE

    ceiling = policy.role_ceiling.get(_value(user, "role"), ResourcePermission.READ)
    return _minimum_permission(granted, ceiling)


def require_resource_permission(
    actual: ResourcePermission,
    required: ResourcePermission,
) -> None:
    """Fail explicitly on insufficient permission."""

    if RESOURCE_PERMISSION_ORDER[actual] < RESOURCE_PERMISSION_ORDER[required]:
        raise ResourcePermissionDenied(f"Requires {required.value} permission, current is {actual.value}")


def resolve_knowledge_base_permission(user: Any, resource: ShareableResource) -> ResourcePermission:
    """Resolve knowledge base permission; regular users get at most read permission."""

    return resolve_resource_permission(
        user,
        resource,
        KNOWLEDGE_BASE_PERMISSION_POLICY,
    )


def require_knowledge_base_permission(
    user: Any,
    resource: ShareableResource,
    required: ResourcePermission,
) -> ResourcePermission:
    """Validate that the user holds the required knowledge base permission; return actual."""

    actual = resolve_knowledge_base_permission(user, resource)
    require_resource_permission(actual, required)
    return actual


def resolve_agent_permission(user: Any, resource: ShareableResource) -> ResourcePermission:
    """Resolve Agent permission."""

    return resolve_resource_permission(
        user,
        resource,
        AGENT_PERMISSION_POLICY,
    )


def resolve_skill_permission(user: Any, resource: ShareableResource) -> ResourcePermission:
    """Resolve Skill permission."""

    return resolve_resource_permission(
        user,
        resource,
        SKILL_PERMISSION_POLICY,
    )
