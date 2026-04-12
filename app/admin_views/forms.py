# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Introspect SQLAlchemy models and describe their columns for form rendering.

The admin controller uses these descriptors to render create/edit forms
without needing a separate form class per model.
"""

from dataclasses import dataclass
from typing import Any, List, Optional

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.types import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
)


@dataclass
class FieldDescriptor:
    name: str
    label: str
    input_type: str  # 'text', 'textarea', 'number', 'checkbox', 'datetime', 'date', 'select'
    required: bool = False
    readonly: bool = False
    value: Any = None
    choices: Optional[list] = None
    max_length: Optional[int] = None


def _column_to_input_type(column) -> str:
    col_type = column.type
    if isinstance(col_type, Boolean):
        return "checkbox"
    if isinstance(col_type, DateTime):
        return "datetime"
    if isinstance(col_type, Date):
        return "date"
    if isinstance(col_type, (Integer, Float, Numeric)):
        return "number"
    if isinstance(col_type, Text):
        return "textarea"
    if isinstance(col_type, String):
        # Long strings become textareas
        length = getattr(col_type, "length", None) or 0
        if length >= 1000:
            return "textarea"
        return "text"
    return "text"


def _prettify(name: str) -> str:
    return name.replace("_", " ").title()


def get_form_fields(admin, instance=None) -> List[FieldDescriptor]:
    """Build a list of FieldDescriptor objects for a model's create/edit form.

    Args:
        admin: A ModelAdmin config instance.
        instance: Optional model instance to pre-populate field values.
    """
    mapper = sa_inspect(admin.model)
    all_columns = [c for c in mapper.columns if not c.primary_key]

    if admin.form_columns is not None:
        columns = [c for c in all_columns if c.name in admin.form_columns]
        # Preserve the order requested in form_columns
        columns.sort(key=lambda c: admin.form_columns.index(c.name))
    else:
        columns = [
            c for c in all_columns if c.name not in admin.form_excluded_columns
        ]

    fields = []
    for col in columns:
        name = col.name
        value = getattr(instance, name, None) if instance is not None else None
        max_length = getattr(col.type, "length", None)
        fields.append(
            FieldDescriptor(
                name=name,
                label=admin.column_labels.get(name, _prettify(name)),
                input_type=_column_to_input_type(col),
                required=not col.nullable and col.default is None,
                readonly=name in admin.form_readonly_columns,
                value=value,
                max_length=max_length,
            )
        )
    return fields


def apply_form_data(admin, instance, form_data) -> None:
    """Apply submitted form data to a model instance.

    Skips readonly fields and coerces values to appropriate types based on
    the column type.
    """
    mapper = sa_inspect(admin.model)
    col_map = {c.name: c for c in mapper.columns}

    fields = get_form_fields(admin, instance=instance)
    for f in fields:
        if f.readonly:
            continue
        col = col_map.get(f.name)
        if col is None:
            continue

        raw = form_data.get(f.name)

        if f.input_type == "checkbox":
            value = f.name in form_data
        elif raw is None or raw == "":
            value = None
        elif f.input_type == "number":
            if isinstance(col.type, Integer):
                value = int(raw)
            else:
                value = float(raw)
        else:
            value = raw

        setattr(instance, f.name, value)


def get_list_columns(admin) -> List[str]:
    """Return the columns to display in the list view."""
    if admin.column_list is not None:
        return list(admin.column_list)
    mapper = sa_inspect(admin.model)
    all_names = [c.name for c in mapper.columns]
    return [n for n in all_names if n not in admin.column_exclude_list]
