"""Cross-platform Milestone 0 task runner."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements-dev.txt"
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
VERSIONED_CONTRACTS = ("words", "speakers", "catalog", "edl", "ops")
DOC_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])((?:docs|schemas)/[A-Za-z0-9_./*-]+)")
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def task_python() -> Path:
    """Use the project venv after setup and the invoking Python before setup."""
    if sys.platform == "win32":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else Path(sys.executable)


def run_command(arguments: Sequence[str]) -> int:
    print("$ " + " ".join(arguments), flush=True)
    completed = subprocess.run(arguments, cwd=ROOT, check=False)
    return completed.returncode


def task_setup() -> int:
    env_dir = ROOT / ".venv"
    if not env_dir.exists():
        venv.EnvBuilder(with_pip=True).create(env_dir)
    python = task_python()
    return run_command(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--constraint",
            str(ROOT / "requirements-lock.txt"),
            "--requirement",
            str(REQUIREMENTS),
        ]
    )


def task_lint() -> int:
    python = str(task_python())
    checks = [
        [python, "-m", "ruff", "check", "orchestrator", "perception", "tests/unit", "tasks.py"],
        [
            python,
            "-m",
            "ruff",
            "format",
            "--check",
            "orchestrator",
            "perception",
            "tests/unit",
            "tasks.py",
        ],
        [python, "-m", "mypy", "--strict", "orchestrator"],
    ]
    for check in checks:
        status = run_command(check)
        if status != 0:
            return status
    return 0


def task_test() -> int:
    """Run unit tests with a project-local temp directory that is removed afterward."""
    with tempfile.TemporaryDirectory(prefix=".pytest-temp-", dir=ROOT) as temp_root:
        return run_command(
            [
                str(task_python()),
                "-m",
                "pytest",
                "tests/unit",
                "--basetemp",
                temp_root,
            ]
        )


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def fixture_issues(
    contract: str,
    document: dict[str, Any],
    refs: dict[str, dict[str, Any]],
) -> list[Any]:
    from orchestrator.contracts import (
        check_catalog,
        check_edl_against,
        check_ops,
        check_words,
    )

    if contract == "words":
        return check_words(document)
    if contract == "catalog":
        return check_catalog(document)
    if contract == "edl":
        return check_edl_against(
            document,
            refs["words"],
            refs["speakers"],
            refs["catalog"],
        )
    if contract == "ops":
        return check_ops(document, FIXTURE_ROOT)
    return []


def task_schemas() -> int:
    from jsonschema import Draft202012Validator

    from orchestrator.contracts import validate

    schema_paths = sorted((ROOT / "schemas").glob("*.schema.json"))
    try:
        for schema_path in schema_paths:
            schema = load_json(schema_path)
            Draft202012Validator.check_schema(schema)
    except Exception as error:
        print(f"schema definition invalid: {type(error).__name__}", file=sys.stderr)
        return 1

    sample_documents = [
        ("config", ROOT / "config.example.json"),
        ("speakers", ROOT / "speakers.example.json"),
    ]
    for contract, sample_path in sample_documents:
        sample_issues = validate(contract, load_json(sample_path))
        if sample_issues:
            print(f"{sample_path.relative_to(ROOT)}: invalid example", file=sys.stderr)
            return 1

    manifest = load_json(FIXTURE_ROOT / "manifest.json")
    fixture_entries = manifest["fixtures"]
    refs = {
        name: load_json(FIXTURE_ROOT / relative)
        for name, relative in manifest["references"].items()
    }
    listed_paths: set[Path] = set()
    failures: list[str] = []

    for entry in fixture_entries:
        contract = entry["contract"]
        relative = Path(entry["file"])
        fixture_path = (FIXTURE_ROOT / relative).resolve()
        if not fixture_path.is_relative_to(FIXTURE_ROOT.resolve()):
            failures.append(f"{entry['file']}: fixture path escapes fixture directory")
            continue
        listed_paths.add(fixture_path)
        document = load_json(fixture_path)
        expected = entry["expected"]
        schema_issues = validate(contract, document)
        actual_codes: set[str] = {issue.code.value for issue in schema_issues}
        if not schema_issues:
            actual_codes.update(
                issue.code.value for issue in fixture_issues(contract, document, refs)
            )
        if expected == "valid":
            if actual_codes:
                failures.append(f"{entry['file']}: expected valid, got {sorted(actual_codes)}")
        elif expected not in actual_codes:
            failures.append(
                f"{entry['file']}: expected {expected}, got {sorted(actual_codes) or ['valid']}"
            )

    actual_paths = {
        path.resolve() for path in FIXTURE_ROOT.rglob("*.json") if path.name != "manifest.json"
    }
    unlisted = actual_paths - listed_paths
    if unlisted:
        failures.append(
            "unlisted fixtures: "
            + ", ".join(str(path.relative_to(ROOT)) for path in sorted(unlisted))
        )
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Validated {len(schema_paths)} schemas and {len(fixture_entries)} fixtures.")
    return 0


def _markdown_targets(markdown_path: Path) -> list[str]:
    content = markdown_path.read_text(encoding="utf-8")
    return [match.group(1).strip() for match in MARKDOWN_LINK_PATTERN.finditer(content)]


def _target_path(target: str) -> str:
    cleaned = target.strip()
    if cleaned.startswith("<") and ">" in cleaned:
        cleaned = cleaned[1 : cleaned.index(">")]
    else:
        cleaned = cleaned.split(maxsplit=1)[0]
    return cleaned.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]


def task_docs_check() -> int:
    markdown_files = sorted(
        path
        for path in ROOT.rglob("*.md")
        if ".venv" not in path.parts and ".git" not in path.parts
    )
    failures: list[str] = []
    for markdown_path in markdown_files:
        relative_md = markdown_path.relative_to(ROOT)
        for target in _markdown_targets(markdown_path):
            path_text = _target_path(target)
            if not path_text or path_text.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            destination = (markdown_path.parent / path_text).resolve()
            if not destination.exists():
                failures.append(f"{relative_md}: broken relative link {path_text}")

    contract_versions: dict[str, str] = {}
    for contract in VERSIONED_CONTRACTS:
        schema = load_json(ROOT / "schemas" / f"{contract}.schema.json")
        version = schema["properties"]["schema_version"]["const"]
        contract_versions[contract] = version
        spec_path = ROOT / "docs" / "contracts" / f"{contract}.md"
        spec = spec_path.read_text(encoding="utf-8")
        if f"Schema version: {version}" not in spec:
            failures.append(f"{spec_path.relative_to(ROOT)}: schema version mismatch")
        if f"{contract}={version}" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
            failures.append(f"CHANGELOG.md: missing {contract} version {version}")

    for markdown_path in markdown_files:
        content = markdown_path.read_text(encoding="utf-8")
        for match in DOC_PATH_PATTERN.finditer(content):
            mentioned = match.group(1).rstrip(".,;:!?)]}")
            candidate = ROOT / mentioned
            if "*" in mentioned:
                if not list(ROOT.glob(mentioned)):
                    failures.append(
                        f"{markdown_path.relative_to(ROOT)}: missing documented path {mentioned}"
                    )
            elif not candidate.exists():
                failures.append(
                    f"{markdown_path.relative_to(ROOT)}: missing documented path {mentioned}"
                )

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Documentation links, referenced paths, contract versions, and changelog entries agree.")
    return 0


def task_stub(name: str) -> int:
    print(f"{name} is not implemented in Milestone 0.")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="task", required=True)
    for name in ("setup", "lint", "test", "schemas", "docs-check", "dry-run", "eval"):
        subparser = subparsers.add_parser(name)
        if name == "dry-run":
            subparser.add_argument("--job", default=None)
    args = parser.parse_args(argv)

    if args.task == "setup":
        return task_setup()
    if args.task == "lint":
        return task_lint()
    if args.task == "test":
        return task_test()
    if args.task == "schemas":
        project_python = task_python()
        if Path(sys.executable).resolve() != project_python.resolve():
            return run_command([str(project_python), str(ROOT / "tasks.py"), "schemas"])
        return task_schemas()
    if args.task == "docs-check":
        return task_docs_check()
    return task_stub(args.task)


if __name__ == "__main__":
    raise SystemExit(main())
