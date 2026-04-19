from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from .common import normalize_path, safe_read_text


DEFAULT_CONFIG: Dict = {
    "project": {
        "name": "frontend-project",
        "defaultBaseBranch": "main",
        "defaultCompareBranch": "HEAD",
        "sourceRoot": ".",
    },
    "paths": {
        "projectProfileFile": "impact-analyzer-project-profile.md",
        "repoWikiDir": "repo-wiki",
        "requirementsDir": "requirements",
        "specsDir": "specs",
        "diffDir": ".impact-analysis/diffs",
        "outputDir": ".impact-analysis/runs",
    },
    "diff": {
        "ignoreDirs": [
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".next",
            "out",
            "generated",
        ],
        "ignoreFiles": [
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
        ],
        "ignoreGlobs": [
            "*.map",
            "**/__snapshots__/**",
            "**/generated/**",
        ],
    },
    "analysis": {
        "requireRepoWiki": True,
        "requireRequirements": False,
        "requireSpecs": False,
        "maxClustersForDeepAnalysis": 30,
        "maxFilesPerClusterContext": 8,
        "maxDocumentSnippetsPerCluster": 6,
        "maxSnippetChars": 5000,
        "maxClusterContextChars": 60000,
        "maxCommentEvidencePerCluster": 20,
        "phasedExecutionThreshold": 1000,
    },
}


def load_config(project_root: Path, config_file: Optional[Path] = None) -> Dict:
    path = config_file or project_root / "impact-analyzer.config.json"
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))

    loaded = json.loads(safe_read_text(path) or "{}")
    return _deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), loaded)


def write_default_config(project_root: Path, config_file: Optional[Path] = None, force: bool = False) -> Dict:
    """Create default config file.  Returns a status dict with ``path``, ``action``
    (``created`` / ``exists`` / ``overwritten``), and ``message``."""
    path = config_file or project_root / "impact-analyzer.config.json"
    if path.exists() and not force:
        return {
            "path": str(path),
            "action": "exists",
            "userActionRequired": False,
            "message": f"Config already exists at {path}. Use --force-config to overwrite.",
        }
    action = "overwritten" if path.exists() else "created"
    path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "action": action,
        "userActionRequired": True,
        "message": (
            f"Config {action} at {path}.\n"
            ">>> STOP: Do NOT proceed to diff or analysis yet. <<<\n"
            "Ask the user to review the config file and confirm or modify it before continuing.\n"
            "Key sections to review:\n"
            "  - diff.ignoreDirs: directories excluded from git diff (e.g. node_modules, dist)\n"
            "  - diff.ignoreFiles: specific files excluded (e.g. lock files)\n"
            "  - diff.ignoreGlobs: glob patterns excluded (e.g. *.map, __snapshots__)\n"
            "  - paths.repoWikiDir, paths.requirementsDir, paths.specsDir: document directories\n"
            "  - analysis.requireRepoWiki: whether repo-wiki is required\n"
            "The user MUST confirm the config is acceptable before the workflow continues."
        ),
    }


def build_run_manifest(
    project_root: Path,
    config: Dict,
    base_branch: Optional[str],
    compare_branch: Optional[str],
    diff_file: Optional[Path],
    run_id: Optional[str] = None,
) -> Dict:
    base = base_branch or config["project"].get("defaultBaseBranch") or "main"
    compare = compare_branch or config["project"].get("defaultCompareBranch") or "HEAD"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    effective_run_id = run_id or f"run_{stamp}_{sanitize_branch(base)}_to_{sanitize_branch(compare)}"
    output_dir = _resolve_project_path(project_root, config["paths"]["outputDir"]) / effective_run_id
    return {
        "runId": effective_run_id,
        "projectRoot": normalize_path(str(project_root)),
        "baseBranch": base,
        "compareBranch": compare,
        "diffFile": normalize_path(str(diff_file)) if diff_file else "",
        "outputDir": normalize_path(str(output_dir)),
        "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": config,
    }


def preflight(project_root: Path, config: Dict) -> Dict:
    checks: List[Dict] = []

    for name, path_key, required_key in [
        ("repo-wiki", "repoWikiDir", "requireRepoWiki"),
        ("requirements", "requirementsDir", "requireRequirements"),
        ("specs", "specsDir", "requireSpecs"),
    ]:
        path = _resolve_project_path(project_root, config["paths"][path_key])
        required = bool(config["analysis"].get(required_key))
        exists = path.exists() and path.is_dir()
        checks.append({
            "name": name,
            "path": normalize_path(str(path)),
            "required": required,
            "status": "ok" if exists else ("missing" if required else "optional_missing"),
            "message": "found" if exists else f"{name} directory does not exist",
        })

    git_check = _git_check(project_root)
    checks.append(git_check)

    blocking = [item for item in checks if item["status"] == "missing"]
    return {
        "status": "blocked" if blocking else "ok",
        "checks": checks,
        "blockingActions": [
            f"Create or generate {item['name']} at {item['path']}" for item in blocking
        ],
    }


def doctor(project_root: Path, skill_root: Path) -> Dict:
    checks: List[Dict] = []

    uv_path = shutil.which("uv")
    checks.append({
        "name": "uv",
        "required": True,
        "status": "ok" if uv_path else "missing",
        "message": f"found at {uv_path}" if uv_path else "uv is required for the recommended skill command",
    })

    checks.append({
        "name": "python",
        "required": True,
        "status": "ok" if sys.version_info >= (3, 12) else "missing",
        "message": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    })

    for package_name, module_name in [
        ("tree-sitter", "tree_sitter"),
        ("tree-sitter-typescript", "tree_sitter_typescript"),
    ]:
        try:
            __import__(module_name)
            status = "ok"
            message = "importable in current Python environment"
        except Exception as exc:
            status = "missing"
            message = str(exc)
        checks.append({
            "name": package_name,
            "required": True,
            "status": status,
            "message": message,
        })

    checks.append({
        "name": "skill-root",
        "required": True,
        "status": "ok" if (skill_root / "SKILL.md").exists() and (skill_root / "scripts" / "front_end_impact_analyzer.py").exists() else "missing",
        "message": normalize_path(str(skill_root)),
    })

    checks.append(_git_check(project_root))

    # Detect potential venv conflict: if VIRTUAL_ENV is set and points to a
    # different project, the skill's dependencies may not be available.
    active_venv = os.environ.get("VIRTUAL_ENV", "")
    skill_venv = str(skill_root / ".venv")
    if active_venv and not Path(active_venv).resolve().is_relative_to(skill_root.resolve()):
        checks.append({
            "name": "venv-isolation",
            "required": False,
            "status": "warning",
            "message": (
                f"VIRTUAL_ENV is set to {active_venv} which belongs to another project. "
                "This may cause import errors. Deactivate the current venv first, or "
                "prefix the command with: VIRTUAL_ENV= uv run --project ..."
            ),
        })
    else:
        checks.append({
            "name": "venv-isolation",
            "required": False,
            "status": "ok",
            "message": "no conflicting VIRTUAL_ENV detected",
        })

    # Check if CWD has a different pyproject.toml that might confuse uv
    cwd_pyproject = Path.cwd() / "pyproject.toml"
    if cwd_pyproject.exists() and cwd_pyproject.resolve() != (skill_root / "pyproject.toml").resolve():
        checks.append({
            "name": "cwd-project-isolation",
            "required": False,
            "status": "info",
            "message": (
                f"CWD has its own pyproject.toml at {cwd_pyproject}. "
                "The --project flag should isolate the skill environment, but if you see "
                "import errors, ensure you are using: uv run --project \"<skill_root>\" ..."
            ),
        })

    missing = [item for item in checks if item["required"] and item["status"] != "ok"]
    warnings = [item for item in checks if item["status"] == "warning"]
    analyzer_script = skill_root / "scripts" / "front_end_impact_analyzer.py"
    return {
        "status": "ok" if not missing else "blocked",
        "checks": checks,
        "warnings": [item["message"] for item in warnings],
        "recommendedCommandPrefix": f'uv run --project "{skill_root}" python "{analyzer_script}"',
        "blockingActions": [_doctor_action(item) for item in missing],
    }


def make_diff_file(
    project_root: Path,
    config: Dict,
    base_branch: str,
    compare_branch: str,
    extra_ignore_dirs: Optional[List[str]] = None,
) -> Path:
    diff_dir = _resolve_project_path(project_root, config["paths"]["diffDir"])
    diff_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    diff_file = diff_dir / f"diff_{sanitize_branch(base_branch)}_to_{sanitize_branch(compare_branch)}_{stamp}.patch"

    pathspecs = _ignore_pathspecs(config, extra_ignore_dirs or [])
    exclude_args = [f":(exclude){p}" for p in pathspecs]

    # Diagnostic output so the user can verify ignores are applied
    print(f"[make-diff] applying {len(pathspecs)} exclude pathspecs from config:")
    for p in pathspecs:
        print(f"  :(exclude){p}")

    cmd = ["git", "diff", "--no-ext-diff", f"{base_branch}...{compare_branch}", "--", "."] + exclude_args
    print(f"[make-diff] running: git diff --no-ext-diff {base_branch}...{compare_branch} -- . <{len(exclude_args)} excludes>")
    result = subprocess.run(cmd, cwd=project_root, capture_output=True, encoding="utf-8", errors="replace", check=True)
    diff_text = result.stdout or ""
    diff_file.write_text(diff_text, encoding="utf-8")

    line_count = diff_text.count("\n")
    size_kb = len(diff_text.encode("utf-8")) / 1024
    print(f"[make-diff] diff written to: {diff_file}")
    print(f"[make-diff] diff size: {line_count} lines, {size_kb:.1f} KB")
    return diff_file


def ensure_run_dir(manifest: Dict) -> Path:
    run_dir = Path(manifest["outputDir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cluster-context").mkdir(parents=True, exist_ok=True)
    (run_dir / "cluster-analysis").mkdir(parents=True, exist_ok=True)
    return run_dir


def install_claude_agents(
    project_root: Path,
    templates_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> Dict:
    source_dir = templates_dir or Path(__file__).resolve().parents[2] / "agents" / "claude"
    target_dir = project_root / ".claude" / "agents"
    report = {
        "sourceDir": normalize_path(str(source_dir)),
        "targetDir": normalize_path(str(target_dir)),
        "installed": [],
        "skipped": [],
        "status": "ok",
        "message": "",
    }

    if not project_root.exists() or not project_root.is_dir():
        report["status"] = "missing-project-root"
        report["message"] = "Target project root does not exist or is not a directory."
        return report

    if not source_dir.exists() or not source_dir.is_dir():
        report["status"] = "missing-source"
        report["message"] = "Claude agent template directory does not exist."
        return report

    target_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.glob("*.md")):
        target = target_dir / source.name
        existed = target.exists()
        if target.exists() and not overwrite:
            report["skipped"].append({
                "file": source.name,
                "reason": "target exists; use --overwrite-claude-agents to replace it",
            })
            continue
        shutil.copyfile(source, target)
        report["installed"].append({
            "file": source.name,
            "action": "overwritten" if existed and overwrite else "installed",
        })

    report["message"] = f"installed {len(report['installed'])}, skipped {len(report['skipped'])}"
    return report


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_branch(branch: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", branch.strip())
    return value.strip("-") or "unknown"


def _deep_merge(base: Dict, override: Dict) -> Dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _resolve_project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _git_check(project_root: Path) -> Dict:
    try:
        result = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_root, capture_output=True, encoding="utf-8", errors="replace", check=True)
        ok = result.stdout.strip() == "true"
        return {
            "name": "git",
            "path": normalize_path(str(project_root)),
            "required": True,
            "status": "ok" if ok else "missing",
            "message": "inside git work tree" if ok else "not a git work tree",
        }
    except Exception as exc:
        return {
            "name": "git",
            "path": normalize_path(str(project_root)),
            "required": True,
            "status": "missing",
            "message": str(exc),
        }


def _doctor_action(item: Dict) -> str:
    name = item.get("name")
    if name == "uv":
        return "Install uv, then run analyzer commands with `uv run --project <skill_root> ...`."
    if name == "python":
        return "Use Python 3.12 or newer."
    if name in {"tree-sitter", "tree-sitter-typescript"}:
        return "Run `uv sync --project <skill_root>` or use `uv run --project <skill_root> ...` so dependencies are available."
    if name == "skill-root":
        return "Run commands with the absolute path to the frontend-impact-analyzer skill root."
    if name == "git":
        return "Set `--project-root` to the target git worktree."
    return item.get("message", "Resolve missing requirement.")


def _ignore_pathspecs(config: Dict, extra_ignore_dirs: List[str]) -> List[str]:
    patterns: List[str] = []
    for item in config["diff"].get("ignoreDirs", []) + extra_ignore_dirs:
        cleaned = str(item).strip().strip("/")
        if cleaned:
            patterns.append(f"{cleaned}/**")
    patterns.extend(str(item).strip() for item in config["diff"].get("ignoreFiles", []) if str(item).strip())
    patterns.extend(str(item).strip() for item in config["diff"].get("ignoreGlobs", []) if str(item).strip())
    return patterns


# ---------------------------------------------------------------------------
# Phase checkpoint helpers
# ---------------------------------------------------------------------------

_PHASE_FILES = {
    "parse": "phase-01-parse.json",
    "scan": "phase-02-scan.json",
}

_PHASE_PREREQUISITES = {
    "scan": ["parse"],
    "analyze": ["parse", "scan"],
}


def write_phase_json(path: Path, data: Dict) -> None:
    """Write a phase checkpoint file with compact JSON (no indent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def build_phase_checkpoint(phase_id: str, project_root: Path, **data) -> Dict:
    """Build a phase checkpoint envelope."""
    return {
        "phaseId": phase_id,
        "phaseVersion": 1,
        "completedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "projectRoot": normalize_path(str(project_root)),
        **data,
    }


def load_phase_artifact(run_dir: Path, phase_id: str) -> Dict:
    """Load and validate a phase checkpoint file."""
    filename = _PHASE_FILES.get(phase_id)
    if not filename:
        raise SystemExit(f"Unknown phase id: {phase_id}")
    path = run_dir / filename
    if not path.exists():
        raise SystemExit(
            f"Phase '{phase_id}' checkpoint not found: {path}\n"
            f"Run --phase {phase_id} first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("phaseId") != phase_id:
        raise SystemExit(
            f"Phase checkpoint {path} has phaseId='{data.get('phaseId')}', "
            f"expected '{phase_id}'."
        )
    return data


def validate_phase_prerequisites(
    run_dir: Path, phase: str, project_root: Path,
) -> Dict[str, Dict]:
    """Check that all prerequisite phases have completed and return their data."""
    prereqs = _PHASE_PREREQUISITES.get(phase, [])
    if not prereqs:
        return {}
    loaded: Dict[str, Dict] = {}
    for req in prereqs:
        loaded[req] = load_phase_artifact(run_dir, req)
    # Stale data warning: check timestamps
    if "parse" in loaded and "scan" in loaded:
        parse_ts = loaded["parse"].get("completedAt", "")
        scan_ts = loaded["scan"].get("completedAt", "")
        if scan_ts and parse_ts and scan_ts < parse_ts:
            print(
                "[warning] phase-02-scan.json was created before phase-01-parse.json. "
                "The scan results may be stale. Consider re-running --phase scan."
            )
    # Project root mismatch warning
    for req, data in loaded.items():
        stored_root = data.get("projectRoot", "")
        current_root = normalize_path(str(project_root))
        if stored_root and stored_root != current_root:
            print(
                f"[warning] --project-root ({current_root}) differs from "
                f"phase '{req}' project root ({stored_root}). "
                "Results may be inconsistent."
            )
    return loaded
