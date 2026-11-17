#!/bin/sh
set -e

# Aplica migrations pendentes (não destrutivo; não cria o banco — use scripts.setup_db para isso)
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python -m scripts.init_db
fi

exec gunicorn "run:app" \
    --bind "0.0.0.0:${PORT:-5001}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --worker-class gthread \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
