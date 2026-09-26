# MLflow's web server currently fails under the local Python 3.14 runtime.
# Keep the container stack on Python 3.13 while the research code remains
# compatible with Python >=3.11.
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY frontend ./frontend
COPY artifacts ./artifacts
RUN pip install --no-cache-dir .

ENV VRIDHI_RISK_MODEL_DIR=/app/artifacts/risk/reference
CMD ["uvicorn", "vridhi_sim.backend:app", "--host", "0.0.0.0", "--port", "8000"]
