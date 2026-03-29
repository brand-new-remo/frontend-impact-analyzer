from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

SRC_EXTS = {".ts", ".tsx", ".js", ".jsx"}
STYLE_EXTS = {".css", ".scss", ".less"}
IGNORE_DIRS = {
    "node_modules", ".git", ".idea", ".vscode", "dist", "build",
    "coverage", ".next", "out", "tmp", "temp"
}
API_NAMES = {"fetch", "axios", "request", "get", "post", "put", "delete", "patch"}


def normalize_path(p: str) -> str:
    return p.replace("\\", "/").strip()


def rel_path(path: Path, root: Path) -> str:
    try:
        return normalize_path(str(path.relative_to(root)))
    except Exception:
        return normalize_path(str(path))


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def uniq_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def title_from_file(path_str: str) -> str:
    name = Path(path_str).stem
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = name.replace("-", " ").replace("_", " ")
    return name.strip().title() or name


def module_name_from_path(path_str: str) -> str:
    p = normalize_path(path_str)
    parts = p.split("/")
    ignore = {
        "src", "pages", "views", "components", "features", "router", "routes",
        "common", "shared", "api", "services", "hooks", "store", "context"
    }
    for part in parts:
        if not part or part in ignore:
            continue
        if part.endswith((".tsx", ".ts", ".jsx", ".js")):
            continue
        return part
    return "unknown"


def confidence_to_priority(conf: str) -> str:
    return {"high": "high", "medium": "medium"}.get(conf, "low")


def load_tsconfig_aliases(project_root: Path) -> Dict[str, List[str]]:
    tsconfig = project_root / "tsconfig.json"
    aliases: Dict[str, List[str]] = {"@/*": ["src/*"]}
    if tsconfig.exists():
        aliases.update(_load_tsconfig_aliases_from_file(project_root, tsconfig, set()))
    return aliases


def resolve_alias_targets(project_root: Path, raw_target: str, aliases: Dict[str, List[str]]) -> List[Path]:
    candidates: List[Path] = []
    for alias, values in aliases.items():
        alias_prefix = alias[:-1] if alias.endswith("*") else alias
        if not raw_target.startswith(alias_prefix):
            continue
        suffix = raw_target[len(alias_prefix):]
        for pattern in values:
            real_prefix = pattern[:-1] if pattern.endswith("*") else pattern
            raw_path = real_prefix + suffix
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = (project_root / raw_path).resolve()
            candidates.append(candidate)
    return candidates


def _load_tsconfig_aliases_from_file(project_root: Path, config_path: Path, seen: set[Path]) -> Dict[str, List[str]]:
    resolved_path = config_path.resolve()
    if resolved_path in seen or not resolved_path.exists():
        return {}

    seen.add(resolved_path)
    data = _read_json_file(resolved_path)
    aliases: Dict[str, List[str]] = {}

    extends_value = data.get("extends")
    if isinstance(extends_value, str):
        parent_config = _resolve_extended_tsconfig(resolved_path.parent, extends_value)
        if parent_config:
            aliases.update(_load_tsconfig_aliases_from_file(project_root, parent_config, seen))

    compiler_options = data.get("compilerOptions") or {}
    paths = compiler_options.get("paths") or {}
    base_url = compiler_options.get("baseUrl", ".")
    config_base = (resolved_path.parent / base_url).resolve()

    for key, values in paths.items():
        if isinstance(values, list) and values:
            aliases[key] = [_normalize_alias_target(project_root, config_base, str(value)) for value in values]

    return aliases


def _read_json_file(path: Path) -> Dict:
    try:
        return json.loads(safe_read_text(path) or "{}")
    except Exception:
        return {}


def _resolve_extended_tsconfig(config_dir: Path, extends_value: str) -> Optional[Path]:
    candidate = Path(extends_value)
    if not candidate.suffix:
        candidate = Path(f"{extends_value}.json")
    if candidate.is_absolute():
        return candidate
    return (config_dir / candidate).resolve()


def _normalize_alias_target(project_root: Path, config_base: Path, value: str) -> str:
    target = Path(value)
    if not target.is_absolute():
        target = (config_base / target).resolve()

    try:
        return normalize_path(str(target.relative_to(project_root)))
    except Exception:
        return normalize_path(str(target))
