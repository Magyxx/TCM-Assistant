.PHONY: api p7-gate test compile

api:
	uvicorn app.api.main:app --host 127.0.0.1 --port 8000

p7-gate:
	python scripts/run_p7_gate.py

test:
	python -m unittest discover -s tests

compile:
	python -m compileall -q app scripts tests
