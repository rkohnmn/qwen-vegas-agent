"""Cross-platform local task runner for M1 and repository verification."""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from orchestrator.childenv import safe_child_environment

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements-dev.txt"
FIXTURE_ROOT = ROOT / "tests" / "fixtures"
VERSIONED_CONTRACTS = (
    "words",
    "speakers",
    "catalog",
    "edl",
    "ops",
    "timeline",
    "compile_report",
    "verify_report",
    "run_manifest",
)
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
    completed = subprocess.run(arguments, cwd=ROOT, check=False, env=safe_child_environment())
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
        [
            python,
            "-m",
            "ruff",
            "check",
            "orchestrator",
            "perception",
            "tests/unit",
            "tests/integration",
            "tasks.py",
        ],
        [
            python,
            "-m",
            "ruff",
            "format",
            "--check",
            "orchestrator",
            "perception",
            "tests/unit",
            "tests/integration",
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
        check_compile_report,
        check_edl_against,
        check_ops,
        check_run_manifest,
        check_timeline,
        check_verify_report,
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
    if contract == "timeline":
        return check_timeline(document)
    if contract == "compile_report":
        return check_compile_report(document)
    if contract == "verify_report":
        return check_verify_report(document)
    if contract == "run_manifest":
        return check_run_manifest(document)
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


def _privacy_scan() -> list[str]:
    """Scan tracked and unignored working files without echoing sensitive matches."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
            env=safe_child_environment(),
        )
    except (OSError, subprocess.CalledProcessError):
        return ["privacy scan could not list repository files"]

    user_path_pattern = re.compile(
        r"[A-Za-z]:\\(?:Users|Documents and Settings)\\[^\\/\s]+"
        r"|/(?:Users|home)/[^/\s]+",
        re.IGNORECASE,
    )
    sensitive_names: list[str] = []
    local_config = ROOT / "config.local.json"
    if local_config.is_file():
        try:
            local_value = load_json(local_config)
        except (OSError, json.JSONDecodeError):
            local_value = None

        def collect_media_names(value: Any) -> None:
            if isinstance(value, dict):
                for nested in value.values():
                    collect_media_names(nested)
            elif isinstance(value, list):
                for nested in value:
                    collect_media_names(nested)
            elif isinstance(value, str):
                candidate = Path(value).name
                if Path(candidate).suffix.lower() in {
                    ".mp4",
                    ".mkv",
                    ".mov",
                    ".avi",
                    ".m4v",
                    ".webm",
                }:
                    sensitive_names.append(candidate.casefold())

        collect_media_names(local_value)

    hostname = socket.gethostname().casefold().strip()
    text_suffixes = {
        ".bat",
        ".cfg",
        ".cs",
        ".gitignore",
        ".ini",
        ".json",
        ".md",
        ".py",
        ".ps1",
        ".schema.json",
        ".sh",
        ".toml",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
    failures: list[str] = []
    for relative in listed.stdout.splitlines():
        path = ROOT / relative
        if not path.is_file() or not any(
            relative.lower().endswith(suffix) for suffix in text_suffixes
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        lowered = content.casefold()
        reason = None
        if user_path_pattern.search(content):
            reason = "absolute user path"
        elif hostname and len(hostname) >= 5 and hostname in lowered:
            reason = "machine hostname"
        elif any(name in lowered for name in sensitive_names):
            reason = "local video basename"
        if reason:
            failures.append(f"{relative}: contains a {reason}")

    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "config.local.json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            shell=False,
            env=safe_child_environment(),
        )
    except OSError:
        return [*failures, "config.local.json ignore rule could not be checked"]
    if ignored.returncode != 0:
        failures.append("config.local.json is not ignored by Git")
    return failures


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

    failures.extend(_privacy_scan())

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Documentation links, referenced paths, contract versions, and changelog entries agree.")
    return 0


def task_dry_run(args: argparse.Namespace) -> int:
    from orchestrator.cli import DryRunError, run_dry_run
    from orchestrator.planner import PlannerError
    from orchestrator.renderer import RenderError
    from perception.asr import AsrError
    from perception.audio import AudioExtractionError

    if not args.video:
        print("dry-run requires --video", file=sys.stderr)
        return 2
    try:
        output = run_dry_run(
            args.video,
            max_seconds=args.max_seconds,
            planner_name=args.planner,
            recorded_edl=args.recorded_edl,
            llm_endpoint=args.llm_endpoint,
            llm_model=args.llm_model,
        )
    except (
        DryRunError,
        PlannerError,
        AsrError,
        AudioExtractionError,
        RenderError,
        OSError,
        ValueError,
    ) as error:
        print(f"dry-run blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"dry-run artifacts written under {output.relative_to(ROOT)}")
    return 0


def task_preflight(args: argparse.Namespace) -> int:
    from perception.preflight import MediaToolError, probe_media

    try:
        result = probe_media(args.video)
    except MediaToolError as error:
        print(f"preflight blocked or failed: {error}", file=sys.stderr)
        return 1
    report = {
        "container_names": list(result.container_names),
        "duration": str(result.duration) if result.duration is not None else None,
        "frame_rate": str(result.frame_rate) if result.frame_rate is not None else None,
        "real_frame_rate": str(result.real_frame_rate)
        if result.real_frame_rate is not None
        else None,
        "vfr_detected": result.vfr_detected,
        "sampled_frame_timestamps": [str(item) for item in result.sampled_frame_timestamps],
        "streams": [
            {
                "index": stream.index,
                "kind": stream.kind,
                "codec": stream.codec,
                "profile": stream.profile,
                "duration": str(stream.duration) if stream.duration is not None else None,
                "frame_rate": str(stream.frame_rate) if stream.frame_rate is not None else None,
                "real_frame_rate": str(stream.real_frame_rate)
                if stream.real_frame_rate is not None
                else None,
                "sample_rate": stream.sample_rate,
                "channels": stream.channels,
                "channel_layout": stream.channel_layout,
                "width": stream.width,
                "height": stream.height,
            }
            for stream in result.streams
        ],
        "warnings": [
            {"code": warning.code.value, "message": warning.message} for warning in result.warnings
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


def task_transcribe(args: argparse.Namespace) -> int:
    from orchestrator.cli import DryRunError
    from orchestrator.stages import run_transcribe
    from perception.asr import AsrError
    from perception.audio import AudioExtractionError
    from perception.preflight import MediaToolError

    try:
        output = run_transcribe(
            args.video, max_seconds=args.max_seconds, output_root=args.output_dir
        )
    except (
        DryRunError,
        AsrError,
        AudioExtractionError,
        MediaToolError,
        OSError,
        ValueError,
    ) as error:
        print(f"transcribe blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"transcript artifacts written under {output.relative_to(ROOT)}")
    return 0


def task_plan(args: argparse.Namespace) -> int:
    from orchestrator.cli import DryRunError
    from orchestrator.stages import run_plan

    try:
        output = run_plan(
            args.words,
            output_root=args.output_dir,
            recorded_edl=args.recorded_edl,
        )
    except (DryRunError, OSError, ValueError) as error:
        print(f"plan blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"plan artifacts written under {output.relative_to(ROOT)}")
    return 0


def task_compile(args: argparse.Namespace) -> int:
    from orchestrator.cli import DryRunError
    from orchestrator.stages import run_compile
    from perception.audio import AudioExtractionError

    try:
        output = run_compile(
            args.words,
            args.timeline,
            args.edl,
            output_root=args.output_dir,
            audio_path=args.audio,
        )
    except (AudioExtractionError, DryRunError, OSError, ValueError) as error:
        print(f"compile blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"compile artifacts written under {output.relative_to(ROOT)}")
    return 0


def task_integration() -> int:
    print(
        "SKIPPED by default: integration requires local media tools, ASR weights, and an "
        "explicitly configured environment."
    )
    return 0


def task_eval() -> int:
    from orchestrator.evaluation import run_synthetic_eval

    print(json.dumps(run_synthetic_eval(), ensure_ascii=False, indent=2))
    return 0


def task_truth_template(args: argparse.Namespace) -> int:
    from orchestrator.contracts import validate
    from orchestrator.evaluation import truth_template

    words_path = Path(args.words)
    output_path = Path(args.output)
    try:
        document = load_json(words_path)
    except (OSError, json.JSONDecodeError):
        print("words document could not be read", file=sys.stderr)
        return 1
    if validate("words", document):
        print("words document failed contract validation", file=sys.stderr)
        return 1
    root = ROOT.resolve()
    resolved_output = output_path.resolve()
    if not resolved_output.is_relative_to(root):
        print("truth template output must stay within the repository", file=sys.stderr)
        return 1
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(truth_template(document), ensure_ascii=False, indent=2) + chr(10),
        encoding="utf-8",
    )
    print(f"truth template written under {resolved_output.relative_to(root)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="task", required=True)
    for name in (
        "setup",
        "lint",
        "test",
        "schemas",
        "docs-check",
        "dry-run",
        "eval",
        "truth-template",
        "preflight",
        "transcribe",
        "plan",
        "compile",
        "integration",
    ):
        subparser = subparsers.add_parser(name)
        if name == "dry-run":
            subparser.add_argument("--video", required=False)
            subparser.add_argument("--max-seconds", type=int, default=120)
            subparser.add_argument(
                "--planner", choices=("baseline", "recorded", "llm"), default="baseline"
            )
            subparser.add_argument("--recorded-edl", default=None)
            subparser.add_argument("--llm-endpoint", default=None)
            subparser.add_argument("--llm-model", default="qwen")
        if name == "truth-template":
            subparser.add_argument("--words", required=True)
            subparser.add_argument("--output", required=True)
        if name in {"preflight", "transcribe"}:
            subparser.add_argument("--video", required=True)
        if name == "transcribe":
            subparser.add_argument("--max-seconds", type=int, default=120)
            subparser.add_argument("--output-dir", default=None)
        if name == "plan":
            subparser.add_argument("--words", required=True)
            subparser.add_argument("--recorded-edl", default=None)
            subparser.add_argument("--output-dir", default=None)
        if name == "compile":
            subparser.add_argument("--words", required=True)
            subparser.add_argument("--timeline", required=True)
            subparser.add_argument("--edl", required=True)
            subparser.add_argument("--audio", default=None)
            subparser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    project_python = task_python()
    if (
        args.task
        in {
            "schemas",
            "eval",
            "dry-run",
            "truth-template",
            "preflight",
            "transcribe",
            "plan",
            "compile",
        }
        and Path(sys.executable).resolve() != project_python.resolve()
    ):
        forwarded = list(argv) if argv is not None else sys.argv[1:]
        return run_command([str(project_python), str(ROOT / "tasks.py"), *forwarded])

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
    if args.task == "dry-run":
        return task_dry_run(args)
    if args.task == "eval":
        return task_eval()
    if args.task == "truth-template":
        return task_truth_template(args)
    if args.task == "preflight":
        return task_preflight(args)
    if args.task == "transcribe":
        return task_transcribe(args)
    if args.task == "plan":
        return task_plan(args)
    if args.task == "compile":
        return task_compile(args)
    if args.task == "integration":
        return task_integration()
    raise AssertionError("unknown task")


if __name__ == "__main__":
    raise SystemExit(main())
