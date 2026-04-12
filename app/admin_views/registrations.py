# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Register PeARS models with the admin UI.

This module wires all PeARS-specific models into the generic admin registry.
Adding a new model to the admin is a one-liner here — no templates or routes
required.
"""

import logging

from app.admin_views.registry import register
from app.api.models import (
    Personalization,
    Pods,
    RejectedSuggestions,
    Suggestions,
    Urls,
    User,
)
from app.extensions import db
from app.utils_db import (
    add_to_npz,
    create_pod_in_db,
    create_pod_npz_pos,
    delete_pod_representations,
    delete_url_representations,
    rm_doc_from_pos,
    rm_from_npz,
    update_db_idvs_after_npz_delete,
)

logger = logging.getLogger(__name__)


# -- Custom hooks for Urls --------------------------------------------------

def _urls_before_save(instance, is_created):
    """Handle pod-move logic when a URL's pod is changed on edit.

    Mirrors the legacy Flask-Admin UrlsModelView.update_model flow: if the
    pod value has changed, move the vector between NPZ files and clean up
    the old pod if it becomes empty.
    """
    if is_created:
        return

    # The instance's attribute already reflects the submitted value at this
    # point, so we compare against the database-persisted original.
    state = db.session.query(Urls).filter(Urls.id == instance.id).one()
    old_pod = state.pod
    new_pod = instance.pod

    if not old_pod or old_pod == new_pod:
        return

    if ".u." not in old_pod:
        return

    _, contributor = old_pod.split(".u.", 1)
    if ".u." not in new_pod:
        new_pod = new_pod + ".u." + contributor
        instance.pod = new_pod

    new_theme = new_pod.split(".u.")[0]
    p = db.session.query(Pods).filter_by(name=old_pod).first()
    if p is None:
        return
    lang = p.language

    logger.info("Pod name has changed from %s to %s", old_pod, new_pod)
    pod_path = create_pod_npz_pos(contributor, new_theme, lang)
    create_pod_in_db(contributor, new_theme, lang)
    idv, v = rm_from_npz(instance.vector, old_pod)
    update_db_idvs_after_npz_delete(idv, old_pod)
    add_to_npz(v, pod_path + ".npz")
    rm_doc_from_pos(instance.id, old_pod)

    # After the main commit, check if old pod is now empty
    instance._old_pod_to_cleanup = old_pod  # type: ignore[attr-defined]


def _urls_after_save(instance, is_created):
    """Clean up the old pod if the URL move left it empty."""
    old_pod = getattr(instance, "_old_pod_to_cleanup", None)
    if not old_pod:
        return
    remaining = db.session.query(Urls).filter_by(pod=old_pod).count()
    if remaining == 0:
        delete_pod_representations(old_pod)


def _urls_before_delete(instance):
    logger.info("Deleting %s", instance.url)
    delete_url_representations(instance.url)


# -- Custom hooks for Pods --------------------------------------------------

def _pods_before_delete(instance):
    logger.info("Deleting %s", instance.name)
    delete_pod_representations(instance.name)


# -- Register all models ----------------------------------------------------

def register_all():
    register(
        Urls,
        name="URLs",
        category="Content",
        description="Browse, search, edit, or delete indexed pages",
        column_list=["doctype", "url", "title", "pod", "notes"],
        column_labels={"doctype": "Type"},
        column_searchable_list=["url", "title", "pod", "notes", "doctype"],
        page_size=100,
        form_readonly_columns=["vector", "url", "date_created", "date_modified"],
        on_model_change=_urls_before_save,
        after_model_change=_urls_after_save,
        on_model_delete=_urls_before_delete,
    )

    register(
        Pods,
        name="Pods",
        category="Content",
        description="View and manage topic categories",
        column_list=["name", "url", "language", "registered"],
        column_searchable_list=["url", "name", "description", "language"],
        page_size=50,
        can_edit=False,
        form_readonly_columns=["date_created", "date_modified"],
        on_model_delete=_pods_before_delete,
    )

    register(
        Suggestions,
        name="Suggestions",
        category="Content",
        description="Pending URL suggestions from users",
        column_list=["url", "pod", "contributor", "notes"],
        column_searchable_list=["url", "pod"],
        page_size=50,
    )

    register(
        RejectedSuggestions,
        name="Rejected Suggestions",
        category="Content",
        description="Previously rejected submissions",
        column_list=["url", "pod", "contributor", "rejection_reason"],
        column_searchable_list=["url", "pod", "rejection_reason"],
        page_size=50,
    )

    register(
        User,
        name="Users",
        category="Users & Settings",
        description="Manage user accounts and permissions",
        column_list=["email", "username", "is_admin", "is_confirmed"],
        column_exclude_list=["password"],
        column_searchable_list=["email", "username"],
        page_size=50,
        form_readonly_columns=[
            "email",
            "password",
            "username",
            "is_confirmed",
            "confirmed_on",
        ],
    )

    register(
        Personalization,
        name="Personalization",
        category="Users & Settings",
        description="Customize tips, messages, and instance info",
        column_list=["feature", "language", "text"],
        column_searchable_list=["feature", "language"],
        page_size=50,
    )
