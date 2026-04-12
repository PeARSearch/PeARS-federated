FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt gunicorn

EXPOSE 8000

ENV SQLALCHEMY_DATABASE_URI="sqlite:////var/lib/pears/data/app.db"
ENV LOGO_PATH="/var/lib/pears/data"
ENV PODS_DIR="/var/lib/pears/data/pods"
ENV SUGGESTIONS_DIR="/var/lib/pears/data/userdata"
ENV CAPTCHA_DIR="/var/lib/pears/data/.captchas"
ENV MAINTENANCE_MODE_FILE="/var/lib/pears/data/.maintenance_mode"

RUN mkdir -p /var/lib/pears/data/pod /var/lib/pears/data/userdata /var/lib/pears/data/.captchas

COPY . /app

RUN chmod +x /app/deployment/entrypoint.sh
RUN chmod +x /app/deployment/install-lang.py

ENTRYPOINT ["/app/deployment/entrypoint.sh"]
