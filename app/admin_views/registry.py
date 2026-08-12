# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Registry-based admin configuration.

Each SQLAlchemy model is registered once with a ModelAdmin config object that
declares how it should appear in the admin UI. The generic admin controller
then handles all list/create/edit/delete logic by reading the registry, which
means adding a new model only requires a single register() call.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Type


@dataclass
class ModelAdmin:
    """Configuration for a single model's admin interface."""

    model: Type
    name: Optional[str] = None
    category: str = "Content"
    description: str = ""

    # List view
    column_list: Optional[List[str]] = None
    column_exclude_list: List[str] = field(default_factory=list)
    column_searchable_list: List[str] = field(default_factory=list)
    column_labels: Dict[str, str] = field(default_factory=dict)
    page_size: int = 50

    # Permissions
    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True

    # Form
    form_columns: Optional[List[str]] = None
    form_excluded_columns: List[str] = field(default_factory=list)
    form_readonly_columns: List[str] = field(default_factory=list)

    # Hooks (all optional)
    on_model_change: Optional[Callable] = None
    after_model_change: Optional[Callable] = None
    on_model_delete: Optional[Callable] = None
    after_model_delete: Optional[Callable] = None

    @property
    def display_name(self) -> str:
        return self.name or self.model.__name__

    @property
    def endpoint(self) -> str:
        """URL-safe identifier for this model."""
        return self.model.__name__.lower()


# Module-level registry keyed by endpoint name.
_registry: Dict[str, ModelAdmin] = {}


def register(model: Type, **kwargs) -> ModelAdmin:
    """Register a model with the admin UI.

    Example:
        register(User, category='Users', column_list=['email', 'username'])
    """
    admin = ModelAdmin(model=model, **kwargs)
    _registry[admin.endpoint] = admin
    return admin


def get_registry() -> Dict[str, ModelAdmin]:
    """Return the current registry dict."""
    return _registry


def get(endpoint: str) -> Optional[ModelAdmin]:
    """Look up a registered ModelAdmin by endpoint name."""
    return _registry.get(endpoint)
