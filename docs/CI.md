# Offline continuous integration

Pushes to main and pull requests run the existing task runner on Windows and Linux with Python 3.12 and the pinned development dependency constraints. Run the same checks locally with `python tasks.py lint`, `python tasks.py test`, `python tasks.py schemas`, and `python tasks.py docs-check`.

The unit suite includes deterministic compiler and fake pipeline tests. Integration tests contacting a real LLM are excluded; CI has no model credentials or weights. Optional FFmpeg tests run only if tools are already present. No ASR/GPU, VEGAS execution or editing-quality claim follows from these checks. Contracts and the runtime capability gates are unchanged.
