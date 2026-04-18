from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ast_analyzer import TsAstAnalyzer
from .common import IGNORE_DIRS, SRC_EXTS, load_tsconfig_aliases, normalize_path, rel_path, resolve_alias_targets, safe_read_text, uniq_keep_order
from .models import RouteInfo


class ProjectScanner:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_root = project_root / "src"
        self.ast = TsAstAnalyzer()
        self.aliases = load_tsconfig_aliases(project_root)

    def scan(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], List[str], List[RouteInfo], Dict[str, Dict], Dict[str, List[str]], List[str], Dict[str, List[str]], List[Dict[str, str]]]:
        imports: Dict[str, List[str]] = {}
        reverse_imports: Dict[str, List[str]] = defaultdict(list)
        pages: List[str] = []
        routes: List[RouteInfo] = []
        ast_facts: Dict[str, Dict] = {}
        barrel_files: List[str] = []
        barrel_evidence: Dict[str, List[str]] = {}
        diagnostics: List[Dict[str, str]] = []
        route_records_by_file: Dict[str, List[Dict]] = {}

        for file_path in self._collect_source_files():
            rel = rel_path(file_path, self.project_root)
            content = safe_read_text(file_path)
            facts = self.ast.parse_file(file_path, content)
            facts.file = rel
            route_records_by_file[rel] = self._extract_route_records(file_path, content)

            route_lazy_imports = [record["lazy_import"] for record in route_records_by_file[rel] if record.get("lazy_import")]
            resolved_imports: List[str] = []
            resolved_import_bindings: List[Dict] = []
            resolved_reexport_bindings: List[Dict] = []
            for raw in facts.imports + facts.reexports + facts.lazy_imports + route_lazy_imports:
                resolved_paths = self._resolve_imports(file_path.parent, raw)
                if not resolved_paths:
                    diagnostics.append({
                        "type": "unresolved-import",
                        "file": rel,
                        "target": raw,
                        "message": f"unable to resolve import target: {raw}",
                    })
                for resolved in resolved_paths:
                    dep = rel_path(resolved, self.project_root)
                    resolved_imports.append(dep)
                    reverse_imports[dep].append(rel)
            for binding in facts.import_bindings:
                for resolved in self._resolve_imports(file_path.parent, binding.get("source", "")):
                    resolved_import_bindings.append({**binding, "resolved": rel_path(resolved, self.project_root)})
            for binding in facts.reexport_bindings:
                for resolved in self._resolve_imports(file_path.parent, binding.get("source", "")):
                    resolved_reexport_bindings.append({**binding, "resolved": rel_path(resolved, self.project_root)})

            facts.resolved_import_bindings = resolved_import_bindings
            facts.resolved_reexport_bindings = resolved_reexport_bindings
            ast_facts[rel] = facts.__dict__
            imports[rel] = uniq_keep_order(resolved_imports)

            if facts.reexports:
                barrel_files.append(rel)
                barrel_evidence[rel] = imports[rel]
            if self._is_page(rel, facts.__dict__):
                pages.append(rel)

        reverse_imports = {k: uniq_keep_order(v) for k, v in reverse_imports.items()}
        pages = uniq_keep_order(pages)

        for rel_file, route_records in route_records_by_file.items():
            if route_records:
                routes.extend(self._expand_route_records(rel_file, route_records, imports, ast_facts, pages, diagnostics))

        return imports, reverse_imports, pages, routes, ast_facts, self.aliases, uniq_keep_order(barrel_files), barrel_evidence, diagnostics

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

    def _resolve_imports(self, current_dir: Path, raw_target: str) -> List[Path]:
        if raw_target.startswith('.'):
            resolved = self._resolve_candidate((current_dir / raw_target).resolve())
            return [resolved] if resolved else []

        resolved_candidates: List[Path] = []
        for alias_target in resolve_alias_targets(self.project_root, raw_target, self.aliases):
            resolved = self._resolve_candidate(alias_target)
            if resolved:
                resolved_candidates.append(resolved)
        return uniq_keep_order([str(path) for path in resolved_candidates]) and [Path(path) for path in uniq_keep_order([str(path) for path in resolved_candidates])]

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

    def _is_page(self, rel_file: str, facts: Dict) -> bool:
        p = normalize_path(rel_file).lower()
        if "/pages/" not in p and "/views/" not in p:
            return False
        return bool(facts.get("component_names") or facts.get("jsx_tags"))

    def _expand_route_records(self, rel_file: str, route_records: List[Dict], imports: Dict[str, List[str]], ast_facts: Dict[str, Dict], pages: List[str], diagnostics: List[Dict[str, str]]) -> List[RouteInfo]:
        results: List[RouteInfo] = []
        for record in route_records:
            self._append_route_record(results, rel_file, record, imports, ast_facts, pages, diagnostics, parent_path=None, parent_route=None)
        return results

    def _guess_linked_page(self, rel_file: str, route_component: Optional[str], route_lazy_import: Optional[str], imports: Dict[str, List[str]], ast_facts: Dict[str, Dict], pages: List[str]) -> Optional[str]:
        page_set = set(pages)
        reachable_pages = [dep for dep in self._collect_reachable_deps(rel_file, imports) if dep in page_set]

        if route_lazy_import:
            for resolved in self._resolve_imports((self.project_root / rel_file).parent, route_lazy_import):
                dep = rel_path(resolved, self.project_root)
                if dep in page_set:
                    return dep

        if route_component:
            for page in reachable_pages:
                facts = ast_facts.get(page, {})
                comps = set(facts.get("component_names", []))
                exports = set(facts.get("exports", []))
                if route_component in comps or route_component in exports:
                    return page

        if len(reachable_pages) == 1:
            return reachable_pages[0]
        return None

    def _collect_reachable_deps(self, start_file: str, imports: Dict[str, List[str]]) -> List[str]:
        stack = list(imports.get(start_file, []))
        seen = set()
        ordered: List[str] = []
        while stack:
            dep = stack.pop(0)
            if dep in seen:
                continue
            seen.add(dep)
            ordered.append(dep)
            stack.extend(imports.get(dep, []))
        return ordered

    def _append_route_record(
        self,
        results: List[RouteInfo],
        rel_file: str,
        route_record: Dict,
        imports: Dict[str, List[str]],
        ast_facts: Dict[str, Dict],
        pages: List[str],
        diagnostics: List[Dict[str, str]],
        parent_path: Optional[str],
        parent_route: Optional[str],
    ) -> None:
        full_path = self._join_route_paths(parent_path, route_record.get("path"))
        route_component = route_record.get("component")
        route_lazy_import = route_record.get("lazy_import")
        linked_page = self._guess_linked_page(
            rel_file,
            route_component,
            route_lazy_import,
            imports,
            ast_facts,
            pages,
        )

        if full_path and (route_component or route_lazy_import) and not linked_page:
            diagnostics.append({
                "type": "unbound-route",
                "file": rel_file,
                "target": full_path,
                "message": f"unable to bind route to page: {full_path}",
            })

        if full_path:
            results.append(
                RouteInfo(
                    route_path=full_path,
                    source_file=rel_file,
                    linked_page=linked_page,
                    route_component=route_component,
                    parent_route=parent_route,
                    confidence="high" if linked_page else "medium",
                    route_comment=route_record.get("route_comment", ""),
                    display_name=route_record.get("display_name", ""),
                    display_name_source=route_record.get("display_name_source", ""),
                )
            )

        for child in route_record.get("children", []):
            self._append_route_record(
                results,
                rel_file,
                child,
                imports,
                ast_facts,
                pages,
                diagnostics,
                parent_path=full_path or parent_path,
                parent_route=full_path or parent_route,
            )

    def _join_route_paths(self, parent_path: Optional[str], child_path: Optional[str]) -> Optional[str]:
        if not child_path:
            return parent_path
        if child_path.startswith("/"):
            return child_path.rstrip("/") or "/"
        if not parent_path:
            return f"/{child_path.lstrip('/')}".replace("//", "/")
        return f"{parent_path.rstrip('/')}/{child_path.lstrip('/')}".replace("//", "/")

    def _extract_route_records(self, file_path: Path, content: str) -> List[Dict]:
        parser = self.ast.tsx_parser if file_path.suffix.lower() in {".tsx", ".jsx"} else self.ast.ts_parser
        source_bytes = content.encode("utf-8")
        tree = parser.parse(source_bytes)
        return self._collect_route_objects(tree.root_node, content, source_bytes)

    def _collect_route_objects(self, node, source: str, source_bytes: bytes) -> List[Dict]:
        records: List[Dict] = []
        if node.type == "object":
            record = self._build_route_record(node, source, source_bytes)
            if record:
                return [record]
        for child in node.children:
            records.extend(self._collect_route_objects(child, source, source_bytes))
        return records

    def _build_route_record(self, node, source: str, source_bytes: bytes) -> Optional[Dict]:
        path_value: Optional[str] = None
        component_value: Optional[str] = None
        lazy_import_value: Optional[str] = None
        display_name_value: str = ""
        display_name_source: str = ""
        child_records: List[Dict] = []
        has_route_signal = False
        route_comment = self._nearest_route_comment(node, source, source_bytes)

        for child in node.children:
            if child.type != "pair":
                continue
            key_node = child.child_by_field_name("key")
            value_node = child.child_by_field_name("value")
            if key_node is None or value_node is None:
                continue

            key_text = self._strip_quotes(self._node_text(source_bytes, key_node).strip())
            value_text = self._node_text(source_bytes, value_node).strip()

            if key_text in {"path", "element", "component", "lazy", "children"}:
                has_route_signal = True

            if key_text == "path":
                path_value = self._strip_quotes(value_text)
            elif key_text == "element":
                component_value = self._extract_component_name(value_text)
            elif key_text == "component":
                component_value = self._extract_component_name(value_text)
            elif key_text == "lazy":
                lazy_import_value = self._extract_lazy_import(value_text)
            elif key_text in {"meta", "handle"}:
                title = self._extract_title_like(value_text)
                if title and not display_name_value:
                    display_name_value = title
                    display_name_source = f"{key_text}.title"
            elif key_text in {"name", "title"}:
                title = self._strip_quotes(value_text)
                if title and not display_name_value and not self._looks_like_component_name(title):
                    display_name_value = title
                    display_name_source = key_text
            elif key_text == "children" and value_node.type == "array":
                for grandchild in value_node.children:
                    if grandchild.type == "object":
                        route_record = self._build_route_record(grandchild, source, source_bytes)
                        if route_record:
                            child_records.append(route_record)

        if not has_route_signal:
            return None

        return {
            "path": path_value,
            "component": component_value,
            "lazy_import": lazy_import_value,
            "route_comment": route_comment,
            "display_name": display_name_value or route_comment,
            "display_name_source": display_name_source or ("route-comment" if route_comment else ""),
            "children": child_records,
        }

    def _extract_component_name(self, value_text: str) -> Optional[str]:
        match = self._first_match(value_text, [r"<([A-Z]\w*)", r"\b([A-Z]\w*)\b"])
        return match

    def _extract_lazy_import(self, value_text: str) -> Optional[str]:
        return self._first_match(value_text, [r"""import\(\s*['"]([^'"]+)['"]\s*\)"""])

    def _extract_title_like(self, value_text: str) -> str:
        return self._first_match(value_text, [
            r"""\btitle\s*:\s*['"]([^'"]+)['"]""",
            r"""\bmenuName\s*:\s*['"]([^'"]+)['"]""",
            r"""\bbreadcrumb\s*:\s*['"]([^'"]+)['"]""",
            r"""\blabel\s*:\s*['"]([^'"]+)['"]""",
        ]) or ""

    def _nearest_route_comment(self, node, source: str, source_bytes: bytes) -> str:
        lines = source.splitlines()
        line_idx = max(0, node.start_point[0])
        comments: List[str] = []
        for idx in range(line_idx - 1, max(-1, line_idx - 5), -1):
            stripped = lines[idx].strip()
            if not stripped:
                if comments:
                    break
                continue
            comment = self._comment_text(stripped)
            if comment:
                comments.append(comment)
                continue
            if comments:
                break
        comments.reverse()

        node_text = self._node_text(source_bytes, node)
        for line in node_text.splitlines()[:4]:
            comment = self._comment_text(line.strip())
            if comment:
                comments.append(comment)
                break
        return " / ".join(uniq_keep_order(comments))

    def _comment_text(self, line: str) -> str:
        if line.startswith("//"):
            return line[2:].strip()
        if line.startswith("/*") and line.endswith("*/"):
            return line[2:-2].strip(" *")
        if line.startswith("{/*") and line.endswith("*/}"):
            return line[3:-3].strip(" *")
        return ""

    def _node_text(self, source_bytes: bytes, node) -> str:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def _looks_like_component_name(self, value: str) -> bool:
        return bool(re.match(r"^[A-Z][A-Za-z0-9_]*$", value))

    def _first_match(self, value_text: str, patterns: List[str]) -> Optional[str]:
        import re

        for pattern in patterns:
            match = re.search(pattern, value_text)
            if match:
                return match.group(1)
        return None

    def _strip_quotes(self, value: str) -> str:
        return value.strip().strip("'").strip('"')
