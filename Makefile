.PHONY: install run test replay fmt clean help

help:
	@echo "Available targets:"
	@echo "  make install  - Install dependencies"
	@echo "  make run      - Start FastAPI server"
	@echo "  make test     - Run tests"
	@echo "  make replay   - Run replay script"
	@echo "  make fmt      - Format code (placeholder)"
	@echo "  make clean    - Clean cache files"

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

run-frontend:
	cd frontend && python flask_app.py

test:
	pytest -q tests/

replay:
	python scripts/run_replay.py

fmt:
	@echo "Formatting not configured. Consider using black or ruff."

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true

