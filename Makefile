PYTHON ?= python

.PHONY: setup lint test schemas docs-check dry-run eval
setup:
	$(PYTHON) tasks.py setup
lint:
	$(PYTHON) tasks.py lint
test:
	$(PYTHON) tasks.py test
schemas:
	$(PYTHON) tasks.py schemas
docs-check:
	$(PYTHON) tasks.py docs-check
dry-run:
	$(PYTHON) tasks.py dry-run $(if $(JOB),--job "$(JOB)")
eval:
	$(PYTHON) tasks.py eval
