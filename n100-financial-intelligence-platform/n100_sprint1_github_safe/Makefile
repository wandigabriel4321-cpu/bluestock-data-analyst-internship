PYTHON ?= python

.PHONY: setup inventory load validate schema full-load manual-review explore final-check test clean

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt

inventory:
	$(PYTHON) -m src.etl.inventory --input-dir data/raw --additional-dir data/supporting --output output/source_inventory.json

load:
	$(PYTHON) -m src.etl.loader --input-dir data/raw --supporting-dir data/supporting --processed-dir data/processed --output-dir output --maximum-sprint 1

validate:
	$(PYTHON) -m src.etl.validator --processed-dir data/processed --output-dir output

schema:
	$(PYTHON) -c "import sqlite3; c=sqlite3.connect('db/nifty100.db'); c.executescript(open('db/schema.sql', encoding='utf-8').read()); c.close()"

full-load:
	$(PYTHON) -m src.etl.pipeline

manual-review:
	$(PYTHON) -m src.etl.manual_review

explore:
	$(PYTHON) -m src.analytics.run_queries

final-check: full-load manual-review explore test

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

clean:
	$(PYTHON) -c "from pathlib import Path; [p.unlink() for p in Path('output').glob('*') if p.is_file()]"
