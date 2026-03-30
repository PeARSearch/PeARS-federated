# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Flask extensions instantiated outside the app module to avoid circular imports.

Every module that needs db, migrate, mail, or login_manager should import from
here instead of from app.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()

class _PeARSLoginManager(LoginManager):
    """Return 404 instead of 401 for unauthorized access."""
    def unauthorized(self):
        from flask import abort
        return abort(404)

login_manager = _PeARSLoginManager()
login_manager.login_view = 'auth.login'
