"""Cross-platform local task runner for M1 and repository verification."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
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
    "captions",
)
DOC_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9_])((?:docs|schemas)/[A-Za-z0-9_./*-]+)")
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REVISIT_ID_PATTERN = re.compile(r"\bRV-[0-9]{3}\b")
PROMPT_SOURCE_NAMES = {
    "T1.md",
    "T2_DEBUG_FAILING_RUN.md",
    "T3_VERIFY_AND_SIGN_OFF.md",
    "HUMAN_GATES.md",
    "STYLE_INTERVIEW.md",
}


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


def task_setup(*, asr: bool = False) -> int:
    env_dir = ROOT / ".venv"
    if not env_dir.exists():
        venv.EnvBuilder(with_pip=True).create(env_dir)
    python = task_python()
    development_status = run_command(
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
    if development_status != 0 or not asr:
        return development_status
    return task_setup_asr(python)


def task_setup_asr(python: Path) -> int:
    """Install the optional, pinned ASR stack without changing dev requirements."""
    nvidia_smi = shutil.which("nvidia-smi")
    cuda_capable = False
    if nvidia_smi is not None:
        probe = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=safe_child_environment(),
        )
        cuda_capable = probe.returncode == 0 and bool(probe.stdout.strip())

    if cuda_capable:
        install_status = run_command(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--index-url",
                "https://download.pytorch.org/whl/cu128",
                "torch==2.8.0+cu128",
                "torchaudio==2.8.0+cu128",
                "torchvision==0.23.0+cu128",
            ]
        )
        if install_status == 0:
            check = subprocess.run(
                [
                    str(python),
                    "-c",
                    "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                env=safe_child_environment(),
            )
            install_status = check.returncode
        if install_status != 0:
            print("CUDA PyTorch unavailable after official-wheel attempt; falling back to CPU.")
            install_status = run_command(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--index-url",
                    "https://download.pytorch.org/whl/cpu",
                    "torch==2.8.0+cpu",
                    "torchaudio==2.8.0+cpu",
                    "torchvision==0.23.0+cpu",
                ]
            )
    else:
        print("No NVIDIA GPU was detected; installing the official PyTorch CPU wheels.")
        install_status = run_command(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
                "torch==2.8.0+cpu",
                "torchaudio==2.8.0+cpu",
                "torchvision==0.23.0+cpu",
            ]
        )
    if install_status != 0:
        return install_status
    return run_command(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--requirement",
            str(ROOT / "requirements-asr.txt"),
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
        [
            python,
            "-m",
            "mypy",
            "--strict",
            "--explicit-package-bases",
            "orchestrator",
            "perception",
        ],
    ]
    for check in checks:
        status = run_command(check)
        if status != 0:
            return status
    return 0


def task_test() -> int:
    """Run unit tests with a project-local temp directory that is removed afterward."""
    with tempfile.TemporaryDirectory(prefix=".pytest-temp-", dir=ROOT) as temp_root:
        status = run_command(
            [
                str(task_python()),
                "-m",
                "pytest",
                "tests/unit",
                "--basetemp",
                temp_root,
            ]
        )
    return status if status != 0 else task_revisit_check()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as source:
        return json.load(source)


def fixture_issues(
    contract: str,
    document: dict[str, Any],
    refs: dict[str, dict[str, Any]],
) -> list[Any]:
    from orchestrator.contracts import (
        check_captions,
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
    if contract == "captions":
        return check_captions(document, refs.get("words"))
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


def _is_prompt_input_document(path: Path) -> bool:
    """Prompt sources are task inputs, not project docs with link obligations."""
    relative = path.relative_to(ROOT)
    if relative.parts and relative.parts[0] == "completed prompts":
        return True
    if len(relative.parts) != 1:
        return False
    return path.name in PROMPT_SOURCE_NAMES or path.name.endswith("_GOAL.md")


def task_revisit_check() -> int:
    """Require every ASSUMED marker and revisit reference to resolve."""
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
        print("revisit-check could not list repository files", file=sys.stderr)
        return 1

    revisit_path = ROOT / "REVISIT.md"
    if not revisit_path.is_file():
        print("REVISIT.md is missing", file=sys.stderr)
        return 1
    revisit_text = revisit_path.read_text(encoding="utf-8")
    defined = set(REVISIT_ID_PATTERN.findall(revisit_text))
    failures: list[str] = []
    for relative_name in listed.stdout.splitlines():
        path = ROOT / relative_name
        if _is_prompt_input_document(path) or not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".py", ".cs", ".json", ".toml"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(lines, start=1):
            ids = set(REVISIT_ID_PATTERN.findall(line))
            unknown = ids - defined
            if unknown:
                failures.append(
                    f"{relative}:{line_number}: unknown revisit ID {sorted(unknown)[0]}"
                )
            checker_rule = relative == "tasks.py" and (
                '"ASSUMED" in line' in line
                or '"@pytest.mark.revisit" in line' in line
                or "Require every ASSUMED marker" in line
                or "ASSUMED marker has no RV-### reference" in line
                or "revisit test marker has no RV-### reference" in line
            )
            if "ASSUMED" in line and not ids and not checker_rule:
                failures.append(f"{relative}:{line_number}: ASSUMED marker has no RV-### reference")
            if "@pytest.mark.revisit" in line and not ids and not checker_rule:
                failures.append(
                    f"{relative}:{line_number}: revisit test marker has no RV-### reference"
                )
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Revisit markers resolve to {len(defined)} registered items.")
    return 0


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
        if _is_prompt_input_document(markdown_path):
            continue
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
        if _is_prompt_input_document(markdown_path):
            continue
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
    return task_revisit_check()


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
    ask_user_path = output / "ask_user.json"
    if ask_user_path.is_file():
        try:
            ask_user = json.loads(ask_user_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ask_user = {}
        if ask_user.get("status") == "awaiting_user":
            pending = next(
                (row for row in ask_user.get("questions", []) if row.get("status") == "pending"),
                None,
            )
            if pending is not None:
                print("speaker identification is pending; answer it before planning:")
                command = (
                    "python tasks.py answer-speaker --job-dir "
                    + str(output.relative_to(ROOT))
                    + " --speaker-key "
                    + pending["speaker_key"]
                )
                print(command)
                print("continue with planning from this job's saved words.json")
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


def task_enroll(args: argparse.Namespace) -> int:
    """Validate an enrollment input, then require an accepted local encoder."""
    from perception.speakers import EnrollmentError, read_pcm16_wav

    try:
        samples, sample_rate = read_pcm16_wav(args.audio)
        if len(samples) / sample_rate < 3.0:
            raise EnrollmentError("enrollment sample is too short")
        raise EnrollmentError(
            "no accepted local speaker embedding engine is configured; complete G2 and RV-005 first"
        )
    except OSError:
        print("enroll blocked: audio file could not be read", file=sys.stderr)
        return 1
    except (EnrollmentError, ValueError) as error:
        print(f"enroll blocked: {error}", file=sys.stderr)
        return 1


def task_answer_speaker(args: argparse.Namespace) -> int:
    """Show the speaker-map diff and persist it only after CLI confirmation."""
    from orchestrator.artifacts import write_json
    from orchestrator.contracts import validate
    from perception.speakers import (
        SpeakerError,
        apply_identification_answer,
        expire_pending_questions,
    )

    job_dir = Path(args.job_dir)
    job_root = (ROOT / job_dir).resolve() if not job_dir.is_absolute() else job_dir.resolve()
    if not job_root.is_relative_to(ROOT.resolve()):
        print(
            "answer-speaker blocked: job directory must stay inside the workspace", file=sys.stderr
        )
        return 1
    try:
        ask_path = job_root / "ask_user.json"
        words_path = job_root / "words.json"
        speakers_path = job_root / "speakers.json"
        questions_doc = json.loads(ask_path.read_text(encoding="utf-8"))
        words_doc = json.loads(words_path.read_text(encoding="utf-8"))
        speakers_doc = json.loads(speakers_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("answer-speaker blocked: job artifacts could not be read", file=sys.stderr)
        return 1
    warnings = expire_pending_questions(
        questions_doc,
        now_epoch=time.time(),
        timeout_s=int(questions_doc.get("timeout_s", 86400)),
    )
    if warnings:
        write_json(ask_path, questions_doc)
        print(warnings[0]["warning"], file=sys.stderr)
        return 1
    question = next(
        (
            row
            for row in questions_doc.get("questions", [])
            if row.get("speaker_key") == args.speaker_key
        ),
        None,
    )
    if (
        questions_doc.get("status") != "awaiting_user"
        or not isinstance(question, dict)
        or question.get("status", "pending") != "pending"
    ):
        print(
            "answer-speaker blocked: no pending question exists for that speaker", file=sys.stderr
        )
        return 1
    display_name = args.name or input("Speaker name: ").strip()
    try:
        diff = apply_identification_answer(speakers_doc, words_doc, args.speaker_key, display_name)
    except (SpeakerError, ValueError) as error:
        print(f"answer-speaker blocked: {error}", file=sys.stderr)
        return 1
    print("Proposed speakers.json change:")
    print(json.dumps(diff, indent=2, ensure_ascii=False))
    if input("Apply this confirmed diff? [y/N] ").strip().casefold() != "y":
        print("speaker update cancelled; no files were changed")
        return 1
    if validate("speakers", speakers_doc) or validate("words", words_doc):
        print(
            "answer-speaker blocked: updated artifacts failed contract validation", file=sys.stderr
        )
        return 1
    question["status"] = "answered"
    question["answer_display"] = display_name.strip()[:80]
    if all(row.get("status") == "answered" for row in questions_doc.get("questions", [])):
        questions_doc["status"] = "answered"
    write_json(speakers_path, speakers_doc)
    write_json(words_path, words_doc)
    write_json(ask_path, questions_doc)
    persistent_speakers = ROOT / "speakers.json"
    write_json(persistent_speakers, speakers_doc)
    print("speaker update saved to the run and local speakers.json")
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
    ask_user_path = output / "ask_user.json"
    if ask_user_path.is_file():
        try:
            ask_user = json.loads(ask_user_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ask_user = {}
        if ask_user.get("status") == "awaiting_user":
            print("speaker identification is pending; answer the listed questions before planning")
            for question in ask_user.get("questions", []):
                if question.get("status") == "pending":
                    command = (
                        "python tasks.py answer-speaker --job-dir "
                        + str(output.relative_to(ROOT))
                        + " --speaker-key "
                        + question["speaker_key"]
                    )
                    print(command)
    return 0


def task_plan(args: argparse.Namespace) -> int:
    from orchestrator.cli import DryRunError
    from orchestrator.stages import run_plan

    try:
        output = run_plan(
            args.words,
            output_root=args.output_dir,
            recorded_edl=args.recorded_edl,
            catalog_path=args.catalog,
            enable_catalog_suggestions=args.catalog_suggestions,
            sfx_trigger_tags=tuple(args.sfx_trigger_tag or []),
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
            speakers_path=args.speakers,
            catalog_path=args.catalog,
            capabilities_path=args.capabilities,
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


def task_watch_render(args: argparse.Namespace) -> int:
    """Wait for a manually rendered file inside one ignored run directory."""
    import hashlib

    from orchestrator.job_pipeline import JobStageFailure, wait_for_manual_render

    runs_root = (ROOT / "runs").resolve()
    job_dir = Path(args.job_dir).resolve()
    if not job_dir.is_relative_to(runs_root) or not job_dir.is_dir():
        print("watch-render job directory must be an existing folder under runs/", file=sys.stderr)
        return 2
    output = Path(args.output)
    if output.is_absolute():
        candidate = output.resolve()
    else:
        candidate = (job_dir / output).resolve()
    try:
        ready = wait_for_manual_render(
            candidate,
            working_dir=job_dir,
            stop_file=job_dir / "STOP",
            timeout_s=args.timeout_s,
        )
    except JobStageFailure as error:
        print(
            f"watch-render blocked at {error.stage} [{error.code}]: {error.message}",
            file=sys.stderr,
        )
        return 1
    digest_state = hashlib.sha256()
    with ready.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest_state.update(chunk)
    digest = digest_state.hexdigest()
    result = {
        "status": "stable_file_detected",
        "filename": ready.name,
        "sha256": f"sha256:{digest}",
        "size_bytes": ready.stat().st_size,
    }
    result_path = job_dir / "manual_render_result.json"
    result_path.write_text(json.dumps(result, indent=2) + chr(10), encoding="utf-8")
    print(f"stable manual render detected: {result_path.relative_to(ROOT)}")
    return 0


def task_run_job(args: argparse.Namespace) -> int:
    """Run the resumable pipeline from a Vegas copy plus validated artifacts."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from orchestrator.job_pipeline import JobOptions, JobStageFailure, run_job
    from orchestrator.planner import PlannerError, RecordedPlanner

    if args.resume and not args.output_dir:
        print("run-job resume requires --output-dir", file=sys.stderr)
        return 2
    if args.planner == "recorded" and not args.recorded_edl:
        print("run-job recorded planner requires --recorded-edl", file=sys.stderr)
        return 2
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else ROOT / "runs" / f"job_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    )
    if not output_dir.is_relative_to((ROOT / "runs").resolve()):
        print("run-job output must stay under runs/", file=sys.stderr)
        return 2
    planner = RecordedPlanner.from_file(args.recorded_edl) if args.planner == "recorded" else None
    options = JobOptions(
        mode=args.mode,
        max_fix_iterations=args.max_fix_iterations,
        stop_after_stage=args.stop_after_stage,
    )
    try:
        result = run_job(
            project_path=args.project,
            source_media_paths=args.media,
            timeline_path=args.timeline,
            words_path=args.words,
            speakers_path=args.speakers,
            audio_path=args.audio,
            run_dir=output_dir,
            options=options,
            planner=planner,
            recorded_edl_path=args.recorded_edl,
            decisions_path=args.decisions,
            resume=args.resume,
        )
    except JobStageFailure as error:
        print(
            f"run-job blocked at {error.stage} [{error.code}]: {error.message}",
            file=sys.stderr,
        )
        return 1
    except (PlannerError, OSError, ValueError) as error:
        print(f"run-job blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"run-job artifacts written under {result.relative_to(ROOT)}")
    return 0


def task_burn_captions(args: argparse.Namespace) -> int:
    """Burn a generated ASS sidecar into a render confined to one ignored run directory."""
    from orchestrator.caption_renderers import AssBurnInRenderer, CaptionRenderError

    runs_root = (ROOT / "runs").resolve()
    job_dir = Path(args.job_dir).resolve()
    if not job_dir.is_relative_to(runs_root) or not job_dir.is_dir():
        print("burn-captions job directory must be an existing folder under runs/", file=sys.stderr)
        return 2

    def job_path(value: str) -> Path:
        candidate = Path(value)
        return candidate.resolve() if candidate.is_absolute() else (job_dir / candidate).resolve()

    video_path = job_path(args.video)
    ass_path = job_path(args.ass)
    output_path = job_path(args.output)
    try:
        result = AssBurnInRenderer().burn_in(
            video_path,
            ass_path,
            output_path,
            allowed_root=job_dir,
        )
    except (CaptionRenderError, OSError, ValueError) as error:
        print(f"burn-captions blocked or failed: {error}", file=sys.stderr)
        return 1
    print(f"captioned render written under {result.relative_to(ROOT)}")
    return 0


def task_eval() -> int:
    from orchestrator.evaluation import run_synthetic_eval

    print(json.dumps(run_synthetic_eval(), ensure_ascii=False, indent=2))
    return 0


def task_catalog_build(args: argparse.Namespace) -> int:
    from orchestrator.catalog import (
        CatalogBuildError,
        build_catalog_from_dump,
        generate_tag_file,
        merge_tag_file,
        model_catalog_summary,
    )

    dump_path = Path(args.dump)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    resolved_output = output_dir.resolve()
    runs_root = (ROOT / "runs").resolve()
    if not resolved_output.is_relative_to(runs_root) or resolved_output == runs_root:
        print("catalog output must be a child of runs", file=sys.stderr)
        return 1
    try:
        plugin_dump = json.loads(dump_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        print("catalog dump could not be read as JSON", file=sys.stderr)
        return 1
    if not isinstance(plugin_dump, dict):
        print("catalog dump must be a JSON object", file=sys.stderr)
        return 1
    resolved_output.mkdir(parents=True, exist_ok=True)
    tag_path = resolved_output / "catalog_tags.json"
    catalog_path = resolved_output / "catalog.json"
    summary_path = resolved_output / "catalog_summary.json"
    if not args.overwrite and (catalog_path.exists() or summary_path.exists()):
        print(
            "catalog outputs already exist; pass --overwrite to replace derived files",
            file=sys.stderr,
        )
        return 1
    try:
        catalog, warnings = build_catalog_from_dump(plugin_dump, vegas_version=args.vegas_version)
        if args.sfx_index:
            sfx_document = json.loads(Path(args.sfx_index).read_text(encoding="utf-8-sig"))
            if (
                not isinstance(sfx_document, dict)
                or sfx_document.get("schema_version") != "1.0.0"
                or not isinstance(sfx_document.get("entries"), list)
            ):
                raise CatalogBuildError("SFX index has an unsupported shape")
            for source_entry in sfx_document["entries"]:
                if not isinstance(source_entry, dict):
                    raise CatalogBuildError("SFX index contains an invalid entry")
                catalog["sfx"].append(
                    {
                        field: source_entry[field]
                        for field in (
                            "key",
                            "kind",
                            "tags",
                            "params_mode",
                            "enabled",
                            "path",
                            "duration",
                            "loudness_lufs",
                            "license",
                            "source",
                            "sample_rate",
                            "peak_dbfs",
                            "fingerprint",
                        )
                        if field in source_entry
                    }
                )
        if tag_path.exists():
            tag_file = json.loads(tag_path.read_text(encoding="utf-8-sig"))
            if not isinstance(tag_file, dict):
                raise CatalogBuildError("tag file must be a JSON object")
        else:
            tag_file = generate_tag_file(catalog)
        catalog = merge_tag_file(catalog, tag_file)
        summary = model_catalog_summary(catalog)
    except (CatalogBuildError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError):
        print("catalog build failed contract or tag validation", file=sys.stderr)
        return 1
    if not tag_path.exists():
        tag_json = json.dumps(generate_tag_file(catalog), indent=2) + "\n"
        tag_path.write_text(tag_json, encoding="utf-8")
    catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    summary_json = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    catalog_path.write_text(catalog_json, encoding="utf-8")
    summary_path.write_text(summary_json, encoding="utf-8")
    for warning in warnings:
        print(f"warning: {warning}")
    total = sum(
        len(catalog[group])
        for group in ("transitions", "video_fx", "audio_fx", "text_presets", "sfx")
    )
    print(f"catalog entries: {len(summary['entries'])} enabled of {total} total")
    return 0


def task_sfx_index(args: argparse.Namespace) -> int:
    from orchestrator.sfx import SfxIndexError, index_sfx_directory

    library_dir = Path(args.library)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    resolved_output = output_dir.resolve()
    runs_root = (ROOT / "runs").resolve()
    if not resolved_output.is_relative_to(runs_root) or resolved_output == runs_root:
        print("SFX index output must be a child of runs", file=sys.stderr)
        return 1
    index_path = resolved_output / "sfx_index.json"
    if index_path.exists() and not args.overwrite:
        print("SFX index already exists; pass --overwrite to replace it", file=sys.stderr)
        return 1
    try:
        index, warnings = index_sfx_directory(library_dir)
    except (SfxIndexError, OSError, ValueError):
        print(
            "SFX indexing failed; check the local audio tools and library metadata", file=sys.stderr
        )
        return 1
    resolved_output.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enabled = sum(entry["enabled"] is True for entry in index["entries"])
    print(f"SFX entries: {len(index['entries'])}; licensed: {enabled}; warnings: {len(warnings)}")
    for warning in warnings:
        print(f"warning: {warning}")
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
        "catalog-build",
        "sfx-index",
        "truth-template",
        "preflight",
        "transcribe",
        "enroll",
        "answer-speaker",
        "plan",
        "compile",
        "burn-captions",
        "integration",
        "run-job",
        "watch-render",
        "revisit-check",
    ):
        subparser = subparsers.add_parser(name)
        if name == "setup":
            subparser.add_argument(
                "--asr", action="store_true", help="also install optional WhisperX dependencies"
            )
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
        if name == "catalog-build":
            subparser.add_argument("dump", help="read-only CatalogDump JSON")
            subparser.add_argument("--output-dir", default="runs/catalog")
            subparser.add_argument("--vegas-version", default="unknown")
            subparser.add_argument("--sfx-index", default=None, help="local sfx-index JSON")
            subparser.add_argument("--overwrite", action="store_true")
        if name == "sfx-index":
            subparser.add_argument("library", help="local SFX library folder")
            subparser.add_argument("--output-dir", default="runs/sfx-index")
            subparser.add_argument("--overwrite", action="store_true")
        if name in {"preflight", "transcribe"}:
            subparser.add_argument("--video", required=True)
        if name == "transcribe":
            subparser.add_argument("--max-seconds", type=int, default=120)
            subparser.add_argument("--output-dir", default=None)
        if name == "enroll":
            subparser.add_argument("--name", required=True)
            subparser.add_argument("--audio", required=True)
        if name == "answer-speaker":
            subparser.add_argument("--job-dir", required=True)
            subparser.add_argument("--speaker-key", required=True)
            subparser.add_argument("--name", default=None)
        if name == "plan":
            subparser.add_argument("--words", required=True)
            subparser.add_argument("--recorded-edl", default=None)
            subparser.add_argument("--catalog", default=None)
            subparser.add_argument("--catalog-suggestions", action="store_true")
            subparser.add_argument("--sfx-trigger-tag", action="append", default=[])
            subparser.add_argument("--output-dir", default=None)
        if name == "burn-captions":
            subparser.add_argument("--job-dir", required=True)
            subparser.add_argument("--video", default="final_render.mp4")
            subparser.add_argument("--ass", default="captions.ass")
            subparser.add_argument("--output", default="final_captioned.mp4")
        if name == "compile":
            subparser.add_argument("--words", required=True)
            subparser.add_argument("--timeline", required=True)
            subparser.add_argument("--edl", required=True)
            subparser.add_argument("--audio", default=None)
            subparser.add_argument("--speakers", default=None)
            subparser.add_argument("--catalog", default=None)
            subparser.add_argument("--capabilities", default=None)
            subparser.add_argument("--output-dir", default=None)
        if name == "watch-render":
            subparser.add_argument("--job-dir", required=True)
            subparser.add_argument("--output", required=True)
            subparser.add_argument("--timeout-s", type=int, default=3600)
        if name == "run-job":
            subparser.add_argument(
                "--project", required=True, help="source .veg project, read-only"
            )
            subparser.add_argument(
                "--media",
                action="append",
                required=True,
                help="declared source media; repeat per source file",
            )
            subparser.add_argument("--timeline", required=True, help="validated timeline dump")
            subparser.add_argument(
                "--words", required=True, help="validated aligned words artifact"
            )
            subparser.add_argument(
                "--speakers", default=None, help="speaker map; defaults beside words.json"
            )
            subparser.add_argument(
                "--audio", required=True, help="normalized mono PCM16 preview source"
            )
            subparser.add_argument("--mode", choices=("dry-run", "review"), default="dry-run")
            subparser.add_argument(
                "--planner", choices=("baseline", "recorded"), default="baseline"
            )
            subparser.add_argument("--recorded-edl", default=None)
            subparser.add_argument("--decisions", default=None)
            subparser.add_argument("--output-dir", default=None)
            subparser.add_argument("--resume", action="store_true")
            subparser.add_argument("--max-fix-iterations", type=int, choices=(0, 1, 2), default=2)
            subparser.add_argument(
                "--stop-after-stage",
                choices=(
                    "project_copy",
                    "ingest",
                    "perceive",
                    "pack",
                    "plan",
                    "compile",
                    "dry_run",
                    "approve",
                    "execute",
                    "verify_fix_loop",
                    "render_final",
                ),
                default=None,
            )
    args = parser.parse_args(argv)
    project_python = task_python()
    if (
        args.task
        in {
            "schemas",
            "eval",
            "catalog-build",
            "sfx-index",
            "dry-run",
            "truth-template",
            "preflight",
            "transcribe",
            "enroll",
            "answer-speaker",
            "plan",
            "compile",
            "burn-captions",
            "run-job",
            "watch-render",
            "revisit-check",
        }
        and Path(sys.executable).resolve() != project_python.resolve()
    ):
        forwarded = list(argv) if argv is not None else sys.argv[1:]
        return run_command([str(project_python), str(ROOT / "tasks.py"), *forwarded])

    if args.task == "setup":
        return task_setup(asr=args.asr)
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
    if args.task == "watch-render":
        return task_watch_render(args)
    if args.task == "revisit-check":
        return task_revisit_check()
    if args.task == "dry-run":
        return task_dry_run(args)
    if args.task == "eval":
        return task_eval()
    if args.task == "catalog-build":
        return task_catalog_build(args)
    if args.task == "sfx-index":
        return task_sfx_index(args)
    if args.task == "truth-template":
        return task_truth_template(args)
    if args.task == "preflight":
        return task_preflight(args)
    if args.task == "transcribe":
        return task_transcribe(args)
    if args.task == "enroll":
        return task_enroll(args)
    if args.task == "answer-speaker":
        return task_answer_speaker(args)
    if args.task == "plan":
        return task_plan(args)
    if args.task == "compile":
        return task_compile(args)
    if args.task == "burn-captions":
        return task_burn_captions(args)
    if args.task == "integration":
        return task_integration()
    if args.task == "run-job":
        return task_run_job(args)
    raise AssertionError("unknown task")


if __name__ == "__main__":
    raise SystemExit(main())
