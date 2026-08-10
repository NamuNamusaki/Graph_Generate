# SmartBioPep frontend (Streamlit) container.
# Build context must be the frontend/ folder itself, e.g.:
#   docker build -t smartbiopep-frontend -f frontend/Dockerfile frontend
# (docker-compose.yml at the repo root already sets this up.)

FROM python:3.11-slim

WORKDIR /app/Demo_webapp/frontend

# Install deps first so this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything in frontend/ into the image (Mock_backend.py, db.py,
# schema.sql, Result_Sequence/, etc. come along too, even though this
# container only runs app.py) -- .dockerignore still strips __pycache__,
# .venv, .env, and the _test_*.py scratch scripts either way.
COPY . .

# Talk to the API over the Docker network by service name, not localhost.
# Override at `docker run`/compose time; this default only makes sense if
# something else maps a container called "api" to this hostname.
ENV SMARTBIOPEP_API_BASE_URL=http://api:8000

EXPOSE 8501

# Streamlit's own health endpoint -- lets `docker ps` / compose report this
# container as unhealthy if the app process is stuck rather than just "up".
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
