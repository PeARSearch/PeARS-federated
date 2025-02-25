FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt

RUN apt update && apt install -y poppler-utils

# Additionally, install Gunicorn
RUN pip install gunicorn

# Make port 8000 available to the world outside this container
EXPOSE 8000

ENV SQLALCHEMY_DATABASE_URI="sqlite:////var/lib/pears/data/app.db"
ENV LOGO_PATH="/var/lib/pears/data"
ENV PODS_DIR="/var/lib/pears/data/pods"
ENV SUGGESTIONS_DIR="/var/lib/pears/data/userdata"
ENV CAPTCHA_DIR="/var/lib/pears/data/.captchas"
env MAINTENANCE_MODE_FILE="/var/lib/pears/data/.maintenance_mode"

RUN mkdir -p /var/lib/pears/data/pod /var/lib/pears/data/userdata /var/lib/pears/data/.captchas

COPY . /app

RUN chmod +x /app/deployment/entrypoint.sh
RUN chmod +x /app/deployment/install-lang.py

# Set the entrypoint script to be executed
ENTRYPOINT ["/app/deployment/entrypoint.sh"]
