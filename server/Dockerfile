FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies (all pure-Python or prebuilt wheels –
# no compiler toolchain needed in the image)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite + unprivileged runtime user
# (container hardening: limits the blast radius if the app is ever
# compromised). /app stays writable because SQLite creates and updates
# its DB file there at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
