.PHONY: test analyze-example

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

analyze-example:
	PYTHONPATH=src python3 scripts/analyze_raw_transactions.py --input examples/transactions.jsonl --format json

