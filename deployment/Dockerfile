FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt

# Additionally, install Gunicorn
RUN pip install gunicorn

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable (example placeholder values, replace them as needed in the .env file)
ENV PEARS_LANGS=en
ENV TRANSLATION_DIR=/app/translations

ENV MAIL_DEFAULT_SENDER=your-email@example.com
ENV EMAIL_USER=your-email@example.com
ENV MAIL_SERVER=smtp.example.com
ENV MAIL_PORT=587
ENV EMAIL_PASSWORD=your-email-password

ENV SECRET_KEY=your-secret-key
ENV SECURITY_PASSWORD_SALT=your-security-password-salt

ENV SITENAME="Cool PeARS pod"
ENV SITE_TOPIC="Cool topic of my cool PeARS pod"
ENV SEARCH_PLACEHOLDER="Search example: Books, Articles"
ENV SQLALCHEMY_DATABASE_URI="sqlite:////var/lib/pears/data/app.db"
ENV LOGO_PATH="/var/lib/pears/data"
ENV PODS_DIR="/var/lib/pears/data/pods"
ENV SUGGESTIONS_DIR="/var/lib/pears/data/userdata"

RUN mkdir -p /var/lib/pears/data/pod /var/lib/pears/data/userdata

COPY . /app

RUN chmod +x /app/deployment/entrypoint.sh

# Set the entrypoint script to be executed
ENTRYPOINT ["/app/deployment/entrypoint.sh"]