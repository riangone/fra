FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY data/ data/

# Train + register a production model at image build time so the container is
# immediately servable. In a real deployment this stage would instead be a
# separate CI/CD training job that pushes to a shared artifact store, and the
# serving image would only pull the `production` pointer at startup.
RUN python scripts/generate_synthetic_data.py && python scripts/run_pipeline.py

EXPOSE 8001
CMD ["uvicorn", "newsreco.serving.api:app", "--host", "0.0.0.0", "--port", "8001", "--app-dir", "src"]
