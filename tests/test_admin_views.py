# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the custom admin UI that replaces Flask-Admin — issue #142."""

import pytest
from flask_login import login_user

from app.admin_views.registry import get_registry
from app.api.models import Personalization, Pods, Suggestions, User
from app.extensions import db


@pytest.fixture(autouse=True)
def clean_db(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(
            email='admin@test.local',
            username='admin',
            password='x',
            is_admin=True,
            is_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def logged_in_client(app, admin_user):
    """Client with an admin user logged in via session."""
    with app.test_request_context():
        pass
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user)
        sess['_fresh'] = True
    return client


class TestRegistryWiring:
    def test_all_six_models_registered(self, app):
        with app.app_context():
            registry = get_registry()
            endpoints = set(registry.keys())
            required = {
                'urls',
                'pods',
                'suggestions',
                'rejectedsuggestions',
                'user',
                'personalization',
            }
            assert required.issubset(endpoints)

    def test_urls_has_custom_hooks(self, app):
        with app.app_context():
            registry = get_registry()
            urls_admin = registry['urls']
            assert urls_admin.on_model_delete is not None
            assert urls_admin.on_model_change is not None

    def test_pods_not_editable(self, app):
        with app.app_context():
            assert get_registry()['pods'].can_edit is False

    def test_pods_has_delete_hook(self, app):
        with app.app_context():
            assert get_registry()['pods'].on_model_delete is not None


class TestAccessControl:
    def test_anonymous_gets_404(self, client):
        resp = client.get('/admin/')
        assert resp.status_code == 404

    def test_anonymous_list_view_404(self, client):
        resp = client.get('/admin/suggestions/')
        assert resp.status_code == 404

    def test_non_admin_gets_404(self, app, client):
        with app.app_context():
            user = User(
                email='user@test.local',
                username='user',
                password='x',
                is_admin=False,
                is_confirmed=True,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True
        resp = client.get('/admin/')
        assert resp.status_code == 404


class TestDashboard:
    def test_index_renders(self, logged_in_client):
        resp = logged_in_client.get('/admin/')
        assert resp.status_code == 200
        assert b'Database Admin' in resp.data

    def test_index_lists_all_models(self, logged_in_client):
        resp = logged_in_client.get('/admin/')
        body = resp.data
        for name in [b'URLs', b'Pods', b'Suggestions', b'Users', b'Personalization']:
            assert name in body


class TestListView:
    def test_suggestions_list_empty(self, logged_in_client):
        resp = logged_in_client.get('/admin/suggestions/')
        assert resp.status_code == 200
        assert b'No records yet' in resp.data

    def test_suggestions_list_with_data(self, app, logged_in_client):
        with app.app_context():
            s = Suggestions(url='https://example.com', pod='test', notes='note', contributor='alice')
            db.session.add(s)
            db.session.commit()
        resp = logged_in_client.get('/admin/suggestions/')
        assert resp.status_code == 200
        assert b'example.com' in resp.data

    def test_unknown_endpoint_404(self, logged_in_client):
        resp = logged_in_client.get('/admin/nonexistent/')
        assert resp.status_code == 404

    def test_search_filters_results(self, app, logged_in_client):
        with app.app_context():
            db.session.add(Suggestions(url='https://foo.com', pod='p1'))
            db.session.add(Suggestions(url='https://bar.com', pod='p2'))
            db.session.commit()
        resp = logged_in_client.get('/admin/suggestions/?q=foo')
        assert resp.status_code == 200
        assert b'foo.com' in resp.data
        assert b'bar.com' not in resp.data

    def test_sort_query_param_accepted(self, app, logged_in_client):
        with app.app_context():
            db.session.add(Suggestions(url='https://a.com', pod='p1'))
            db.session.add(Suggestions(url='https://b.com', pod='p2'))
            db.session.commit()
        resp = logged_in_client.get('/admin/suggestions/?sort=url&desc=0')
        assert resp.status_code == 200


class TestCreateView:
    def test_create_form_renders(self, logged_in_client):
        resp = logged_in_client.get('/admin/suggestions/create')
        assert resp.status_code == 200
        assert b'<form' in resp.data

    def test_create_submits_and_redirects(self, app, logged_in_client):
        resp = logged_in_client.post(
            '/admin/suggestions/create',
            data={'url': 'https://new.com', 'pod': 'p', 'notes': '', 'contributor': 'c'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        with app.app_context():
            count = db.session.query(Suggestions).count()
            assert count == 1

    def test_pods_create_allowed_at_url_level(self, logged_in_client):
        # Pods can_edit is False but can_create is True (default)
        resp = logged_in_client.get('/admin/pods/create')
        assert resp.status_code == 200


class TestEditView:
    def test_edit_form_prefills(self, app, logged_in_client):
        with app.app_context():
            s = Suggestions(url='https://edit.com', pod='p1', notes='hi')
            db.session.add(s)
            db.session.commit()
            sid = s.id
        resp = logged_in_client.get(f'/admin/suggestions/{sid}/edit')
        assert resp.status_code == 200
        assert b'edit.com' in resp.data

    def test_edit_updates_record(self, app, logged_in_client):
        with app.app_context():
            s = Suggestions(url='https://old.com', pod='p1')
            db.session.add(s)
            db.session.commit()
            sid = s.id
        logged_in_client.post(
            f'/admin/suggestions/{sid}/edit',
            data={'url': 'https://updated.com', 'pod': 'p1', 'notes': '', 'contributor': ''},
        )
        with app.app_context():
            s = db.session.query(Suggestions).filter_by(id=sid).first()
            assert s.url == 'https://updated.com'

    def test_edit_pods_returns_404(self, app, logged_in_client):
        with app.app_context():
            p = Pods(name='p', url='u', description='d', language='en', registered=True)
            db.session.add(p)
            db.session.commit()
            pid = p.id
        resp = logged_in_client.get(f'/admin/pods/{pid}/edit')
        assert resp.status_code == 404

    def test_edit_nonexistent_record_404(self, logged_in_client):
        resp = logged_in_client.get('/admin/suggestions/99999/edit')
        assert resp.status_code == 404


class TestDeleteView:
    def test_delete_confirm_page_renders(self, app, logged_in_client):
        with app.app_context():
            s = Suggestions(url='https://del.com', pod='p')
            db.session.add(s)
            db.session.commit()
            sid = s.id
        resp = logged_in_client.get(f'/admin/suggestions/{sid}/delete')
        assert resp.status_code == 200
        assert b'Confirm delete' in resp.data or b'permanently' in resp.data

    def test_delete_post_removes_record(self, app, logged_in_client):
        with app.app_context():
            s = Suggestions(url='https://goodbye.com', pod='p')
            db.session.add(s)
            db.session.commit()
            sid = s.id
        logged_in_client.post(f'/admin/suggestions/{sid}/delete')
        with app.app_context():
            assert db.session.query(Suggestions).filter_by(id=sid).first() is None

    def test_pods_delete_runs_hook(self, app, logged_in_client, monkeypatch):
        calls = []

        def fake_delete(name):
            calls.append(name)

        import app.admin_views.registrations as regs
        monkeypatch.setattr(regs, 'delete_pod_representations', fake_delete)

        # Re-register pods with the patched hook
        from app.admin_views.registry import get_registry
        pods_admin = get_registry()['pods']
        original_hook = pods_admin.on_model_delete
        pods_admin.on_model_delete = lambda inst: fake_delete(inst.name)

        try:
            with app.app_context():
                p = Pods(name='targetpod', url='u', description='d', language='en', registered=True)
                db.session.add(p)
                db.session.commit()
                pid = p.id
            logged_in_client.post(f'/admin/pods/{pid}/delete')
            assert 'targetpod' in calls
        finally:
            pods_admin.on_model_delete = original_hook


class TestDynamicModelRegistration:
    """Proves that adding a brand-new model to the admin is a one-liner.

    This is the key design goal of the registry-based approach: no new
    templates, routes, or view classes should be needed when a new model
    is added to the project.
    """

    def test_new_model_auto_appears_in_admin(self, app, logged_in_client):
        from sqlalchemy import Column, Integer, String

        from app.admin_views.registry import get_registry, register

        # Define a brand-new model class on the fly.
        class AdminTestNote(db.Model):
            __tablename__ = 'admin_test_note'
            id = Column(Integer, primary_key=True)
            title = Column(String(200))
            body = Column(String(2000))

        registry = get_registry()
        original_keys = set(registry.keys())

        try:
            with app.app_context():
                AdminTestNote.__table__.create(db.engine, checkfirst=True)

            # Single line to add it to the admin.
            register(
                AdminTestNote,
                name='Test Notes',
                category='Content',
                description='A runtime-registered model',
                column_list=['title', 'body'],
                column_searchable_list=['title', 'body'],
            )

            # 1. Appears on the dashboard.
            resp = logged_in_client.get('/admin/')
            assert resp.status_code == 200
            assert b'Test Notes' in resp.data
            assert b'runtime-registered' in resp.data

            # 2. List view renders the empty state without any new template.
            resp = logged_in_client.get('/admin/admintestnote/')
            assert resp.status_code == 200
            assert b'No records yet' in resp.data

            # 3. Create form auto-generates from the model columns.
            resp = logged_in_client.get('/admin/admintestnote/create')
            assert resp.status_code == 200
            assert b'name="title"' in resp.data
            assert b'name="body"' in resp.data

            # 4. Submitting the form actually persists a record.
            resp = logged_in_client.post(
                '/admin/admintestnote/create',
                data={'title': 'Hello', 'body': 'World'},
                follow_redirects=False,
            )
            assert resp.status_code == 302
            with app.app_context():
                row = db.session.query(AdminTestNote).first()
                assert row is not None
                assert row.title == 'Hello'

            # 5. The new row shows up in the list view with search working.
            resp = logged_in_client.get('/admin/admintestnote/?q=Hello')
            assert resp.status_code == 200
            assert b'Hello' in resp.data

        finally:
            # Clean up so we don't leak the registration into other tests.
            for k in list(registry.keys()):
                if k not in original_keys:
                    del registry[k]
            with app.app_context():
                AdminTestNote.__table__.drop(db.engine, checkfirst=True)


class TestFormGeneration:
    def test_personalization_form_has_all_fields(self, logged_in_client):
        resp = logged_in_client.get('/admin/personalization/create')
        assert resp.status_code == 200
        body = resp.data
        assert b'name="feature"' in body
        assert b'name="language"' in body
        assert b'name="text"' in body

    def test_readonly_fields_are_disabled(self, app, logged_in_client):
        with app.app_context():
            user = User(
                email='x@test.local',
                username='x',
                password='pw',
                is_admin=False,
                is_confirmed=True,
            )
            db.session.add(user)
            db.session.commit()
            uid = user.id
        resp = logged_in_client.get(f'/admin/user/{uid}/edit')
        assert resp.status_code == 200
        # email is in form_readonly_columns
        assert b'name="email"' in resp.data
        assert b'disabled' in resp.data
