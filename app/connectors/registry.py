from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from app.connectors.base import BaseConnector

_REGISTRY: dict[str, Type[BaseConnector]] = {}


def register(cls: Type[BaseConnector]) -> Type[BaseConnector]:
    _REGISTRY[cls.connector_type] = cls
    return cls


def get_connector_class(connector_type: str) -> Type[BaseConnector] | None:
    return _REGISTRY.get(connector_type)


def registered_types() -> list[str]:
    return list(_REGISTRY.keys())
