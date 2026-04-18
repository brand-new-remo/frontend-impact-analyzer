from __future__ import annotations

import json
import re
import subprocess
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
    },
}


def load_config(project_root: Path, config_file: Optional[Path] = None) -> Dict:
    path = config_file or project_root / "impact-analyzer.config.json"
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))

    loaded = json.loads(safe_read_text(path) or "{}")
    return _deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), loaded)


def write_default_config(project_root: Path, config_file: Optional[Path] = None) -> Path:
    path = config_file or project_root / "impact-analyzer.config.json"
    path.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


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

    exclude_args = []
    for pattern in _ignore_pathspecs(config, extra_ignore_dirs or []):
        exclude_args.append(f":(exclude){pattern}")

    cmd = ["git", "diff", "--no-ext-diff", f"{base_branch}...{compare_branch}", "--", "."] + exclude_args
    result = subprocess.run(cmd, cwd=project_root, text=True, capture_output=True, check=True)
    diff_file.write_text(result.stdout, encoding="utf-8")
    return diff_file


def ensure_run_dir(manifest: Dict) -> Path:
    run_dir = Path(manifest["outputDir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cluster-context").mkdir(parents=True, exist_ok=True)
    (run_dir / "cluster-analysis").mkdir(parents=True, exist_ok=True)
    return run_dir


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
        result = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=project_root, text=True, capture_output=True, check=True)
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


def _ignore_pathspecs(config: Dict, extra_ignore_dirs: List[str]) -> List[str]:
    patterns: List[str] = []
    for item in config["diff"].get("ignoreDirs", []) + extra_ignore_dirs:
        cleaned = str(item).strip().strip("/")
        if cleaned:
            patterns.append(f"{cleaned}/**")
    patterns.extend(str(item).strip() for item in config["diff"].get("ignoreFiles", []) if str(item).strip())
    patterns.extend(str(item).strip() for item in config["diff"].get("ignoreGlobs", []) if str(item).strip())
    return patterns
