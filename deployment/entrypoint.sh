#!/bin/bash
# entrypoint.sh

flask db migrate

gunicorn -b 0.0.0.0:8000 -w 3 -t 120 app:app