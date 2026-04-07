# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from unittest.mock import patch, MagicMock
from werkzeug.utils import secure_filename


class TestDownloadFilePathTraversal:
    """Tests for path traversal in download endpoint — issue #149."""

    def test_unauthenticated_access_rejected(self, client):
        """Download endpoint requires admin auth."""
        resp = client.get('/download?filename=test.txt')
        assert resp.status_code == 404

    def test_secure_filename_strips_traversal_sequences(self):
        """secure_filename removes ../ sequences."""
        assert secure_filename('../../etc/passwd') == 'etc_passwd'
        assert '..' not in secure_filename('../../etc/passwd')

    def test_secure_filename_strips_absolute_paths(self):
        """secure_filename removes leading slashes."""
        assert secure_filename('/etc/passwd') == 'etc_passwd'

    def test_secure_filename_returns_empty_for_dots_only(self):
        """secure_filename returns empty string for pure traversal."""
        assert secure_filename('../../') == ''
        assert secure_filename('..') == ''


class TestThemePathTraversal:
    """Tests for path traversal in theme name — issue #157."""

    def test_secure_filename_strips_traversal(self):
        assert '..' not in secure_filename('../../etc/passwd')
        assert '/' not in secure_filename('../../etc/passwd')

    def test_secure_filename_preserves_valid_name(self):
        assert secure_filename('My_Theme') == 'My_Theme'

    def test_secure_filename_handles_slashes(self):
        result = secure_filename('foo/bar/baz')
        assert '/' not in result
