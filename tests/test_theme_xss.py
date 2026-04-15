# SPDX-FileCopyrightText: 2026 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression guard for issue #163 — innerHTML XSS in theme dropdowns.

The bug: theme names were concatenated into an HTML string and assigned to
`innerHTML`, so a theme name containing quotes or angle brackets could break
the page or execute script.

The fix switches to DOM-API construction (`document.createElement('option')`
+ `option.value = theme`) which the browser escapes automatically.

This test greps the affected templates to catch any future regression where
someone re-introduces string-concat + innerHTML for theme lists.
"""

import os
import re

import pytest

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app",
    "templates",
    "indexer",
)

# Templates that render the theme datalist.
THEME_TEMPLATES = [
    "index.html",
    "suggest.html",
    "write_and_index.html",
    "web_commentary.html",
]


class TestThemeDropdownXss:
    @pytest.mark.parametrize("template", THEME_TEMPLATES)
    def test_no_innerhtml_option_concat(self, template):
        """Fail if the template builds <option> tags via string concat."""
        path = os.path.join(TEMPLATE_DIR, template)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        # The classic vulnerable pattern: building an HTML string with + and
        # assigning it to innerHTML.
        bad_patterns = [
            r"\+\s*['\"]<option",           # "...  + '<option"
            r"\.innerHTML\s*=\s*str\b",     # .innerHTML = str
        ]
        for pattern in bad_patterns:
            assert not re.search(pattern, source), (
                f"{template} contains the vulnerable pattern {pattern!r}. "
                "Use document.createElement('option') + option.value = theme "
                "instead of string concatenation with innerHTML."
            )

    @pytest.mark.parametrize("template", THEME_TEMPLATES)
    def test_uses_createelement(self, template):
        """Positive check: the template builds options via the DOM API."""
        path = os.path.join(TEMPLATE_DIR, template)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        assert 'createElement("option")' in source or \
            "createElement('option')" in source, (
                f"{template} should build theme options via "
                "document.createElement('option')."
            )
