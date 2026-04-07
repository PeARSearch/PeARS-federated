# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import pytest

os.environ['_PEARS_CONFIG'] = 'testing'

from app import app as flask_app


@pytest.fixture
def app():
    flask_app.config.update({'TESTING': True})
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
