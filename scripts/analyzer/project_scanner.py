from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .ast_analyzer import TsAstAnalyzer
from .common import IGNORE_DIRS, SRC_EXTS, load_tsconfig_aliases, normalize_path, rel_path, resolve_alias_target, safe_read_text, uniq_keep_order
from .models import RouteInfo


class ProjectScanner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_root = project_root / "src"
        self.ast = TsAstAnalyzer()
        self.aliases = load_tsconfig_aliases(project_root)

    def scan(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], List[str], List[RouteInfo], Dict[str, Dict], Dict[str, List[str]], List[str]]:
        imports: Dict[str, List[str]] = {}
        reverse_imports: Dict[str, List[str]] = defaultdict(list)
        pages: List[str] = []
        routes: List[RouteInfo] = []
        ast_facts: Dict[str, Dict] = {}
        barrel_files: List[str] = []

        for file_path in self._collect_source_files():
            rel = rel_path(file_path, self.project_root)
            content = safe_read_text(file_path)
            facts = self.ast.parse_file(file_path, content)
            facts.file = rel
            ast_facts[rel] = facts.__dict__

            resolved_imports: List[str] = []
            for raw in facts.imports + facts.reexports + facts.lazy_imports:
                resolved = self._resolve_import(file_path.parent, raw)
                if resolved:
                    dep = rel_path(resolved, self.project_root)
                    resolved_imports.append(dep)
                    reverse_imports[dep].append(rel)
            imports[rel] = uniq_keep_order(resolved_imports)

            if facts.reexports:
                barrel_files.append(rel)
            if self._is_page(rel):
                pages.append(rel)

        reverse_imports = {k: uniq_keep_order(v) for k, v in reverse_imports.items()}
        pages = uniq_keep_order(pages)

        for rel_file, facts in ast_facts.items():
            route_paths = facts.get("route_paths", [])
            route_components = facts.get("route_components", [])
            imported_files = imports.get(rel_file, [])
            if route_paths:
                routes.extend(self._expand_routes(rel_file, route_paths, route_components, imported_files, ast_facts, pages))

        return imports, reverse_imports, pages, routes, ast_facts, self.aliases, uniq_keep_order(barrel_files)

    def _collect_source_files(self) -> List[Path]:
        base = self.src_root if self.src_root.exists() else self.project_root
        out = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in files:
                path = Path(root) / name
                if path.suffix.lower() in SRC_EXTS:
                    out.append(path)
        return out

    def _resolve_import(self, current_dir: Path, raw_target: str) -> Optional[Path]:
        if raw_target.startswith('.'):
            return self._resolve_candidate((current_dir / raw_target).resolve())
        alias_target = resolve_alias_target(self.project_root, raw_target, self.aliases)
        if alias_target:
            return self._resolve_candidate(alias_target)
        return None

    def _resolve_candidate(self, base: Path) -> Optional[Path]:
        candidates = [
            base,
            Path(str(base) + ".ts"),
            Path(str(base) + ".tsx"),
            Path(str(base) + ".js"),
            Path(str(base) + ".jsx"),
            base / "index.ts",
            base / "index.tsx",
            base / "index.js",
            base / "index.jsx",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _is_page(self, rel_file: str) -> bool:
        p = normalize_path(rel_file).lower()
        return "/pages/" in p or "/views/" in p

    def _expand_routes(self, rel_file: str, route_paths: List[str], route_components: List[str], imported_files: List[str], ast_facts: Dict[str, Dict], pages: List[str]) -> List[RouteInfo]:
        results: List[RouteInfo] = []
        normalized_paths = self._flatten_nested_paths(route_paths)
        linked_page = self._guess_linked_page(imported_files, route_components, ast_facts, pages)
        parent = None
        for idx, path in enumerate(normalized_paths):
            results.append(RouteInfo(
                route_path=path,
                source_file=rel_file,
                linked_page=linked_page,
                route_component=route_components[0] if route_components else None,
                parent_route=parent,
                confidence="high" if linked_page else "medium",
            ))
            parent = path if idx == 0 else parent
        return results

    def _flatten_nested_paths(self, route_paths: List[str]) -> List[str]:
        cleaned = [p for p in route_paths if p]
        if not cleaned:
            return []
        # heuristic: preserve raw paths and also parent/child concatenations
        out: List[str] = []
        parent_stack: List[str] = []
        for p in cleaned:
            if p.startswith('/'):
                parent_stack = [p.rstrip('/') or '/']
                out.append(parent_stack[0])
            else:
                parent = parent_stack[-1] if parent_stack else ''
                full = (parent.rstrip('/') + '/' + p.lstrip('/')).replace('//', '/')
                out.append(full)
                parent_stack.append(full)
        return uniq_keep_order(out)

    def _guess_linked_page(self, imported_files: List[str], route_components: List[str], ast_facts: Dict[str, Dict], pages: List[str]) -> Optional[str]:
        page_set = set(pages)
        for dep in imported_files:
            if dep in page_set:
                return dep
        if route_components:
            target_names = set(route_components)
            for p in pages:
                facts = ast_facts.get(p, {})
                comps = set(facts.get("component_names", []))
                exports = set(facts.get("exports", []))
                if comps & target_names or exports & target_names:
                    return p
        for dep in imported_files:
            dn = normalize_path(dep).lower()
            if "/pages/" in dn or "/views/" in dn:
                return dep
        return None
