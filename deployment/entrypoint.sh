#!/bin/bash
# entrypoint.sh

# Extract the languages from the environment variable
IFS=',' read -ra LANGS <<< "${PEARS_LANGS}"

# Loop through each language and install it unless it's 'eng'
for lang in "${LANGS[@]}"; do
  if [ "$lang" != "en" ]; then
    flask pears install-language "$lang"
  fi
done

flask db migrate

gunicorn -b 0.0.0.0:8000 -w 3 -t 120 app:app