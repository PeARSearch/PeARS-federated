# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Generic admin blueprint.

Every registered model is served by these view functions. Adding a new model
to the admin is a single register() call — no new routes, templates, or
view classes needed.
"""

import logging
import math

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import gettext
from flask_login import current_user
from sqlalchemy import asc, desc, inspect as sa_inspect, or_

from app.admin_views.forms import (
    apply_form_data,
    get_form_fields,
    get_list_columns,
)
from app.admin_views.registry import get as registry_get, get_registry
from app.extensions import db

logger = logging.getLogger(__name__)

admin_views = Blueprint(
    "admin_views",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
)


def _check_admin():
    """Gate every admin page behind admin auth. 404 for non-admins."""
    if not current_user.is_authenticated:
        abort(404)
    if not getattr(current_user, "is_admin", False):
        abort(404)


def _get_admin_or_404(endpoint):
    admin = registry_get(endpoint)
    if admin is None:
        abort(404)
    return admin


@admin_views.before_request
def require_admin():
    _check_admin()


@admin_views.context_processor
def inject_sidebar_nav():
    """Make the sidebar navigation data available to every admin template."""
    registry = get_registry()
    categories = {}
    for admin in registry.values():
        categories.setdefault(admin.category, []).append(admin)
    ordered = sorted(
        categories.items(),
        key=lambda kv: (0 if kv[0] == "Content" else 1, kv[0]),
    )
    current_model = request.view_args.get("model") if request.view_args else None
    return {
        "sidebar_categories": ordered,
        "current_model_endpoint": current_model,
    }


@admin_views.route("/")
def index():
    """Admin dashboard. Groups registered models by category."""
    registry = get_registry()
    categories = {}
    for admin in registry.values():
        categories.setdefault(admin.category, []).append(admin)
    # Sort categories so Content appears first if present.
    ordered = sorted(
        categories.items(),
        key=lambda kv: (0 if kv[0] == "Content" else 1, kv[0]),
    )
    return render_template("admin_views/index.html", categories=ordered)


@admin_views.route("/<model>/")
def list_view(model):
    admin = _get_admin_or_404(model)

    page = max(int(request.args.get("page", 1)), 1)
    search = request.args.get("q", "").strip()
    sort_col = request.args.get("sort")
    sort_desc = request.args.get("desc") == "1"

    mapper = sa_inspect(admin.model)
    col_map = {c.name: c for c in mapper.columns}

    query = db.session.query(admin.model)

    # Search across column_searchable_list with AND over whitespace-split terms
    if search and admin.column_searchable_list:
        terms = search.split()
        for term in terms:
            like = f"%{term}%"
            clauses = [
                col_map[c].ilike(like)
                for c in admin.column_searchable_list
                if c in col_map
            ]
            if clauses:
                query = query.filter(or_(*clauses))

    # Sort
    if sort_col and sort_col in col_map:
        order_fn = desc if sort_desc else asc
        query = query.order_by(order_fn(col_map[sort_col]))
    else:
        # Stable default: primary key descending (newest first)
        pk_col = list(mapper.primary_key)[0]
        query = query.order_by(desc(pk_col))

    total = query.count()
    pages = max(math.ceil(total / admin.page_size), 1)
    page = min(page, pages)
    rows = (
        query.offset((page - 1) * admin.page_size).limit(admin.page_size).all()
    )

    columns = get_list_columns(admin)
    pk_name = list(mapper.primary_key)[0].name

    return render_template(
        "admin_views/list.html",
        admin=admin,
        columns=columns,
        column_labels=admin.column_labels,
        rows=rows,
        pk_name=pk_name,
        page=page,
        pages=pages,
        total=total,
        search=search,
        sort_col=sort_col,
        sort_desc=sort_desc,
    )


@admin_views.route("/<model>/create", methods=["GET", "POST"])
def create_view(model):
    admin = _get_admin_or_404(model)
    if not admin.can_create:
        abort(404)

    instance = admin.model()

    if request.method == "POST":
        try:
            apply_form_data(admin, instance, request.form)
            if admin.on_model_change:
                admin.on_model_change(instance, is_created=True)
            db.session.add(instance)
            db.session.commit()
            if admin.after_model_change:
                admin.after_model_change(instance, is_created=True)
            flash(gettext("Record created."), "success")
            return redirect(
                url_for("admin_views.list_view", model=model)
            )
        except Exception as ex:
            db.session.rollback()
            logger.exception("Failed to create %s", admin.display_name)
            flash(
                gettext("Failed to create record. %(error)s", error=str(ex)),
                "error",
            )

    fields = get_form_fields(admin, instance=instance)
    return render_template(
        "admin_views/edit.html",
        admin=admin,
        fields=fields,
        is_create=True,
    )


def _get_instance_or_404(admin, pk_value):
    mapper = sa_inspect(admin.model)
    pk_col = list(mapper.primary_key)[0]
    instance = (
        db.session.query(admin.model).filter(pk_col == pk_value).first()
    )
    if instance is None:
        abort(404)
    return instance


@admin_views.route("/<model>/<pk>/edit", methods=["GET", "POST"])
def edit_view(model, pk):
    admin = _get_admin_or_404(model)
    if not admin.can_edit:
        abort(404)

    instance = _get_instance_or_404(admin, pk)

    if request.method == "POST":
        try:
            apply_form_data(admin, instance, request.form)
            if admin.on_model_change:
                admin.on_model_change(instance, is_created=False)
            db.session.commit()
            if admin.after_model_change:
                admin.after_model_change(instance, is_created=False)
            flash(gettext("Record updated."), "success")
            return redirect(
                url_for("admin_views.list_view", model=model)
            )
        except Exception as ex:
            db.session.rollback()
            logger.exception("Failed to update %s", admin.display_name)
            flash(
                gettext("Failed to update record. %(error)s", error=str(ex)),
                "error",
            )

    fields = get_form_fields(admin, instance=instance)
    return render_template(
        "admin_views/edit.html",
        admin=admin,
        fields=fields,
        instance=instance,
        is_create=False,
    )


@admin_views.route("/<model>/<pk>/delete", methods=["GET", "POST"])
def delete_view(model, pk):
    admin = _get_admin_or_404(model)
    if not admin.can_delete:
        abort(404)

    instance = _get_instance_or_404(admin, pk)

    if request.method == "POST":
        try:
            if admin.on_model_delete:
                admin.on_model_delete(instance)
            db.session.delete(instance)
            db.session.commit()
            if admin.after_model_delete:
                admin.after_model_delete(instance)
            flash(gettext("Record deleted."), "success")
            return redirect(
                url_for("admin_views.list_view", model=model)
            )
        except Exception as ex:
            db.session.rollback()
            logger.exception("Failed to delete %s", admin.display_name)
            flash(
                gettext("Failed to delete record. %(error)s", error=str(ex)),
                "error",
            )
            return redirect(
                url_for("admin_views.list_view", model=model)
            )

    mapper = sa_inspect(admin.model)
    pk_name = list(mapper.primary_key)[0].name
    return render_template(
        "admin_views/delete.html",
        admin=admin,
        instance=instance,
        pk_name=pk_name,
    )
