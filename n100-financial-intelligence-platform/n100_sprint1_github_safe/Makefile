PYTHON ?= python

.PHONY: setup inventory load validate schema full-load manual-review explore cagr-audit cashflow-audit ratio-engine sector-review sprint2-review sprint2-final-check final-check test test-profitability test-leverage test-cagr test-cashflow test-ratio-engine test-sector-review test-sprint2-review clean

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

cagr-audit:
	$(PYTHON) -m src.analytics.cagr --database db/nifty100.db --output output/cagr_day10.csv

cashflow-audit:
	$(PYTHON) -m src.analytics.cashflow_kpis --database db/nifty100.db --output output/capital_allocation.csv --audit-output output/cashflow_kpis_day11.csv

ratio-engine:
	$(PYTHON) -m src.analytics.ratio_engine --database db/nifty100.db --schema db/schema.sql --reference data/supporting/financial_ratios.xlsx --output-dir output

sector-review: ratio-engine

sprint2-review:
	$(PYTHON) -m src.analytics.sprint2_review

sprint2-final-check: ratio-engine sprint2-review test

final-check: full-load manual-review explore test

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

test-profitability:
	$(PYTHON) -m unittest tests.kpi.test_profitability -v

test-leverage:
	$(PYTHON) -m unittest tests.kpi.test_leverage -v

test-cagr:
	$(PYTHON) -m unittest tests.kpi.test_cagr -v

test-cashflow:
	$(PYTHON) -m unittest tests.kpi.test_cashflow_kpis -v

test-ratio-engine:
	$(PYTHON) -m unittest tests.kpi.test_ratio_engine -v

test-sector-review:
	$(PYTHON) -m unittest tests.kpi.test_sector_roce -v

test-sprint2-review:
	$(PYTHON) -m unittest tests.kpi.test_sprint2_review -v

clean:
	$(PYTHON) -c "from pathlib import Path; [p.unlink() for p in Path('output').glob('*') if p.is_file()]"
