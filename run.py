# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Run a test server.

from app import app
from decouple import config

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config("APP_PORT", default=8080), debug=True)
