PYTHON ?= python

.PHONY: setup lint test schemas docs-check revisit-check dry-run eval run-job watch-render
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
revisit-check:
	$(PYTHON) tasks.py revisit-check
dry-run:
	$(PYTHON) tasks.py dry-run $(if $(JOB),--job "$(JOB)")
eval:
	$(PYTHON) tasks.py eval
run-job:
	$(PYTHON) tasks.py run-job $(ARGS)

watch-render:
	$(PYTHON) tasks.py watch-render $(ARGS)
