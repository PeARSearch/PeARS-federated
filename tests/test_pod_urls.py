# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import tempfile
from unittest.mock import patch

import joblib
import numpy as np
import pytest
from scipy.sparse import csr_matrix, save_npz

from app.api.models import Pods
from app.extensions import db
from app.utils_db import create_pod_in_db, mv_pod


@pytest.fixture(autouse=True)
def clean_db(app):
    """Ensure a fresh database for every test."""
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


class TestCreatePodInDb:
    """Tests for pod URL construction in create_pod_in_db — issue #156."""

    def test_url_uses_sitename_not_localhost(self, app):
        """Pod URL must use SITENAME config, not hardcoded localhost."""
        with app.app_context():
            create_pod_in_db('alice', 'cooking', 'en')
            pod = Pods.query.first()
            assert 'localhost:8080' not in pod.url
            assert pod.url.startswith(app.config['SITENAME'])

    def test_url_contains_contributor_lang_theme(self, app):
        """Pod URL must include contributor, language, and theme segments."""
        with app.app_context():
            create_pod_in_db('alice', 'cooking', 'en')
            pod = Pods.query.first()
            assert '/api/pods/' in pod.url
            assert '/alice/' in pod.url
            assert '/en/' in pod.url
            assert 'cooking' in pod.url

    def test_url_encodes_spaces_in_theme(self, app):
        """Spaces in theme name should be replaced with +."""
        with app.app_context():
            create_pod_in_db('alice', 'home cooking', 'en')
            pod = Pods.query.first()
            assert 'home+cooking' in pod.url

    def test_no_duplicate_pod_created(self, app):
        """Calling create_pod_in_db twice with same args should not duplicate."""
        with app.app_context():
            create_pod_in_db('alice', 'cooking', 'en')
            create_pod_in_db('alice', 'cooking', 'en')
            pods = Pods.query.all()
            assert len(pods) == 1

    def test_url_with_custom_sitename(self, app):
        """Pod URL should reflect a non-default SITENAME."""
        with app.app_context():
            original = app.config['SITENAME']
            app.config['SITENAME'] = 'https://example.com'
            try:
                create_pod_in_db('bob', 'gardening', 'fr')
                pod = Pods.query.first()
                assert pod.url.startswith('https://example.com')
            finally:
                app.config['SITENAME'] = original


class TestMvPodUrl:
    """Tests for pod URL reconstruction in mv_pod — issue #156."""

    def _create_pod_files(self, pod_dir, contributor, lang, name):
        """Helper to create the npz and pos files mv_pod expects."""
        path = os.path.join(pod_dir, contributor, lang)
        os.makedirs(path, exist_ok=True)
        full_name = name + '.u.' + contributor
        mat = csr_matrix(np.zeros((1, 10)))
        save_npz(os.path.join(path, full_name + '.npz'), mat)
        joblib.dump([{}], os.path.join(path, full_name + '.pos'))
        return path

    def test_renamed_pod_url_uses_sitename(self, app):
        """After rename, pod URL must use SITENAME, not hardcoded localhost."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                self._create_pod_files(tmpdir, 'alice', 'en', 'cooking')
                with patch('app.utils_db.pod_dir', tmpdir):
                    create_pod_in_db('alice', 'cooking', 'en')
                    result = mv_pod('cooking', 'baking', contributor='alice')
                    assert 'Moved pod' in result
                    pod = Pods.query.filter_by(
                        name='baking.u.alice').first()
                    assert 'localhost:8080' not in pod.url
                    assert pod.url.startswith(app.config['SITENAME'])

    def test_renamed_pod_url_has_all_segments(self, app):
        """After rename, pod URL must include contributor, lang, and new name."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                self._create_pod_files(tmpdir, 'alice', 'en', 'cooking')
                with patch('app.utils_db.pod_dir', tmpdir):
                    create_pod_in_db('alice', 'cooking', 'en')
                    mv_pod('cooking', 'baking', contributor='alice')
                    pod = Pods.query.filter_by(
                        name='baking.u.alice').first()
                    assert '/alice/' in pod.url
                    assert '/en/' in pod.url
                    assert 'baking' in pod.url

    def test_renamed_pod_url_matches_create_format(self, app):
        """URL format after rename must match the format used at creation."""
        with app.app_context():
            with tempfile.TemporaryDirectory() as tmpdir:
                self._create_pod_files(tmpdir, 'alice', 'en', 'cooking')
                self._create_pod_files(tmpdir, 'alice', 'en', 'baking')
                with patch('app.utils_db.pod_dir', tmpdir):
                    create_pod_in_db('alice', 'cooking', 'en')
                    create_pod_in_db('alice', 'baking', 'en')
                    fresh = Pods.query.filter_by(
                        name='baking.u.alice').first()
                    fresh_url = fresh.url
                    db.session.delete(fresh)
                    db.session.commit()
                    mv_pod('cooking', 'baking', contributor='alice')
                    renamed = Pods.query.filter_by(
                        name='baking.u.alice').first()
                    assert renamed.url == fresh_url
