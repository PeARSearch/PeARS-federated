#!/bin/bash
# entrypoint.sh

# Enable debugging
set -x

# Extract the languages from the environment variable
echo "PEARS_LANGS: ${PEARS_LANGS}"
IFS=',' read -ra LANGS <<< "${PEARS_LANGS}"

# Loop through each language and install it unless it's 'eng'
for lang in "${LANGS[@]}"; do
  echo "Processing language: $lang"
  if [ "$lang" != "en" ]; then
    echo "Installing language: $lang"
    python /app/deployment/install-lang.py $lang
    if [ $? -ne 0 ]; then
      echo "Error installing language: $lang"
      exit 1
    fi
  fi
done

flask db migrate

gunicorn -b 0.0.0.0:8000 -w 3 -t 120 app:app