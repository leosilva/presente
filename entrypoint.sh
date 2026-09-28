#!/bin/bash

# Exit on error
set -e

if [ -n "$DB_HOST" ]; then
	echo "Waiting for PostgreSQL..."
	while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
		sleep 1
	done
	echo "PostgreSQL is ready!"
fi

echo "Running database migrations..."
python manage.py migrate --noinput

# collectstatic roda em build time (ver Dockerfile), não aqui: assim o
# container não refaz esse trabalho a cada wake-up do free tier do Render.

# Render (e outros PaaS) expõem a porta via $PORT e falam direto com o
# container por TCP. Sem $PORT, mantemos o socket Unix (setup com Nginx local).
if [ -n "$PORT" ]; then
	BIND_ADDRESS="0.0.0.0:$PORT"
else
	echo "Setting socket directory permissions..."
	chmod 770 /run/sockets
	BIND_ADDRESS="unix:/run/sockets/presente.sock"
fi

echo "Starting Gunicorn on $BIND_ADDRESS..."
exec gunicorn --bind "$BIND_ADDRESS" \
	--workers 3 \
	--timeout 60 \
	--access-logfile - \
	--error-logfile - \
	config.wsgi:application
