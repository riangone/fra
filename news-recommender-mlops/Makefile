.PHONY: setup data pipeline serve test

setup:
	pip install -r requirements.txt

data:
	python scripts/generate_synthetic_data.py

pipeline:
	python scripts/run_pipeline.py

serve:
	uvicorn newsreco.serving.api:app --reload --port 8001 --app-dir src

test:
	pytest tests -v
