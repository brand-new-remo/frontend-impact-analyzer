from __future__ import annotations

from .common import SRC_EXTS, STYLE_EXTS, module_name_from_path, normalize_path


class SourceClassifier:
    def classify(self, file_path: str) -> str:
        p = normalize_path(file_path).lower()
        filename = p.split("/")[-1]
        if any(p.endswith(x) for x in STYLE_EXTS):
            return "style"
        if not any(p.endswith(ext) for ext in SRC_EXTS):
            return "non-source"
        if "/pages/" in p or "/views/" in p:
            return "page"
        if "/router/" in p or "/routes/" in p or filename in {"router.ts", "router.tsx", "routes.ts", "routes.tsx"}:
            return "route"
        if "/api/" in p or "/services/" in p:
            return "api"
        if "/store/" in p or "/context/" in p:
            return "store"
        if "/hooks/" in p or filename.startswith("use"):
            return "hook"
        if "/components/common/" in p or "/common/" in p or "/shared/" in p or "/ui/" in p:
            return "shared-component"
        if "/components/" in p or "/features/" in p:
            return "business-component"
        if "/utils/" in p or "/helpers/" in p:
            return "utils"
        if "/constants/" in p or "/enums/" in p or "/schema/" in p:
            return "config-or-schema"
        return "unknown"

    def guess_module(self, file_path: str) -> str:
        return module_name_from_path(file_path)
