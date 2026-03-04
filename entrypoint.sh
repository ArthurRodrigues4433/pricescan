#!/bin/bash
set -e

echo "Aguardando banco de dados..."
while ! python -c "
import os, psycopg2
conn = psycopg2.connect(
    dbname=os.environ.get('POSTGRES_DB', 'pricescan'),
    user=os.environ.get('POSTGRES_USER', 'pricescan'),
    password=os.environ.get('POSTGRES_PASSWORD', ''),
    host=os.environ.get('POSTGRES_HOST', 'db'),
    port=os.environ.get('POSTGRES_PORT', '5432'),
)
conn.close()
" 2>/dev/null; do
    echo "Banco indisponível — tentando novamente em 2s..."
    sleep 2
done

echo "Aplicando migrações..."
python manage.py migrate --noinput

echo "Coletando static files..."
python manage.py collectstatic --noinput

echo "Iniciando Gunicorn..."
exec gunicorn pricescan.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 120
