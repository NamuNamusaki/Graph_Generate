# SmartBioPep mock API container (Mock_backend.py).
#
# This exists so you can stand up a working multi-container stack TODAY --
# frontend + api + db + queue -- without waiting for a real API/worker
# service to be built. It builds from the same frontend/ folder as the
# Streamlit image (that's where Mock_backend.py currently lives) but runs
# a completely different process.
#
# When a real API service is split out of Mock_backend.py, give it its own
# folder (e.g. api/) with its own Dockerfile, and retire this file -- it's
# a bridge, not the long-term shape of the project.
#
# Build context is still frontend/:
#   docker build -t smartbiopep-api -f frontend/Dockerfile.api frontend

FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY . .

# So mock job results (Result_Sequence/*.csv) and completion emails link back
# to something reachable; override per-environment via docker-compose/.env.
ENV SMARTBIOPEP_PUBLIC_APP_URL=http://localhost:8501

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

CMD ["uvicorn", "Mock_backend:app", "--host", "0.0.0.0", "--port", "8000"]
