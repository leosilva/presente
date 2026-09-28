# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    musl-dev \
    libpq-dev \
    pkg-config libcairo2-dev libpango1.0-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements* /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-prod.txt

# Runtime stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    # weasyprint dependencies
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    locales \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && \
  locale-gen pt_BR.UTF-8 && \
  update-locale LANG=pt_BR.UTF-8

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project
COPY . /app/

# Create socket directory
RUN mkdir -p /run/sockets

# Create staticfiles directory for collected static
RUN mkdir -p /app/staticfiles

# Create media directory
RUN mkdir -p /app/media

# Set permissions
RUN chmod -R 755 /app/staticfiles /app/media

# Coleta os estáticos em build time. Antes isso rodava no entrypoint.sh a
# cada início de container — no plano Free do Render, o serviço hiberna após
# 15 min sem tráfego e recria o container do zero a cada acesso, então
# refazer collectstatic (com --clear) toda vez deixava o "acordar" bem mais
# lento. STATIC_ROOT precisa bater com o valor configurado no Render.
RUN SECRET_KEY=build-placeholder BUILD_ENV=production \
	STATIC_ROOT=/app/staticfiles MEDIA_ROOT=/app/media \
	python manage.py collectstatic --noinput

# Copy entrypoint script
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
