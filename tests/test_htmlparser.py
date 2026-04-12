# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from unittest.mock import patch, MagicMock
from app.indexer.htmlparser import BS_parse, extract_html


class TestBSParse:
    """Tests for BS_parse() — issue #151."""

    def test_returns_none_when_head_request_fails(self, app):
        """When requests.head() raises an exception, BS_parse should
        return (None, None) without crashing on NoneType access."""
        with app.app_context():
            with patch('app.indexer.htmlparser.requests.head', side_effect=ConnectionError("refused")):
                bs_obj, req = BS_parse('http://nonexistent.invalid')
                assert bs_obj is None
                assert req is None

    def test_returns_none_for_non_html_content(self, app):
        """When content-type is not text/html, should return (None, req)."""
        with app.app_context():
            mock_resp = MagicMock()
            mock_resp.headers = {'content-type': 'application/pdf'}
            with patch('app.indexer.htmlparser.requests.head', return_value=mock_resp):
                bs_obj, req = BS_parse('http://example.com/file.pdf')
                assert bs_obj is None
                assert req is mock_resp

    def test_returns_none_when_content_type_missing(self, app):
        """When content-type header is missing entirely, should not crash."""
        with app.app_context():
            mock_resp = MagicMock()
            mock_resp.headers = {}
            with patch('app.indexer.htmlparser.requests.head', return_value=mock_resp):
                bs_obj, req = BS_parse('http://example.com/no-content-type')
                assert bs_obj is None
                assert req is mock_resp


class TestExtractHtml:
    """Tests for extract_html() — issue #150."""

    def test_returns_six_values_on_language_detection_failure(self, app):
        """All return paths should return exactly 6 values:
        (title, body_str, language, snippet, cc, error)."""
        with app.app_context():
            with patch('app.indexer.htmlparser.BS_parse') as mock_bs:
                # Simulate a page where BS_parse succeeds but language
                # detection fails on the body text
                mock_bs_obj = MagicMock()
                mock_bs_obj.title.string = 'Test'
                mock_bs_obj.find.return_value = None
                mock_bs_obj.findAll.return_value = []
                mock_req = MagicMock()

                mock_bs.return_value = (mock_bs_obj, mock_req)

                with patch('app.indexer.htmlparser.detect', side_effect=Exception("No features")):
                    result = extract_html('http://example.com')
                    assert len(result) == 6, f"Expected 6 return values, got {len(result)}"

    def test_returns_six_values_on_bs_parse_failure(self, app):
        """When BS_parse returns None, should still return 6 values."""
        with app.app_context():
            with patch('app.indexer.htmlparser.BS_parse', return_value=(None, None)):
                result = extract_html('http://example.com')
                assert len(result) == 6
                assert result[-1] is not None  # error should be set
