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
    aliases: Dict[str, List[str]] = {"@/*": ["src/*"]}
    tsconfig = project_root / "tsconfig.json"
    if not tsconfig.exists():
        return aliases
    try:
        data = json.loads(safe_read_text(tsconfig) or "{}")
        paths = (((data.get("compilerOptions") or {}).get("paths")) or {})
        for key, values in paths.items():
            if isinstance(values, list) and values:
                aliases[key] = [str(v) for v in values]
    except Exception:
        pass
    return aliases


def resolve_alias_target(project_root: Path, raw_target: str, aliases: Dict[str, List[str]]) -> Optional[Path]:
    for alias, values in aliases.items():
        alias_prefix = alias[:-1] if alias.endswith("*") else alias
        if not raw_target.startswith(alias_prefix):
            continue
        suffix = raw_target[len(alias_prefix):]
        for pattern in values:
            real_prefix = pattern[:-1] if pattern.endswith("*") else pattern
            candidate = (project_root / (real_prefix + suffix)).resolve()
            return candidate
    return None
