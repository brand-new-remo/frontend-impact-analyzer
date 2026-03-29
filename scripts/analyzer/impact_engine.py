from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

from .common import module_name_from_path, uniq_keep_order
from .models import ChangedFile, PageImpact, RouteInfo


class ImpactAnalyzer:
    def __init__(self, imports: Dict[str, List[str]], reverse_imports: Dict[str, List[str]], pages: List[str], routes: List[RouteInfo], ast_facts: Dict[str, Dict]):
        self.imports = imports
        self.reverse_imports = reverse_imports
        self.pages = set(pages)
        self.routes = routes
        self.ast_facts = ast_facts
        self.route_map = self._build_route_map()

    def _build_route_map(self) -> Dict[str, List[str]]:
        d = defaultdict(list)
        for r in self.routes:
            if r.linked_page:
                d[r.linked_page].append(r.route_path)
        return d

    def analyze_file(self, cf: ChangedFile) -> Tuple[List[PageImpact], Optional[Dict]]:
        if cf.is_format_only:
            return [], None
        if cf.file_type == "page":
            return self._build_page_direct_impacts(cf), None
        changed_symbols = self._changed_symbols(cf.path, cf.symbols)
        traces = self._trace_to_pages(cf.path, changed_symbols)
        if not traces:
            return [], {
                "file": cf.path,
                "fileType": cf.file_type,
                "confidence": "low",
                "reason": "cannot trace to page via reverse imports",
            }
        impacts: List[PageImpact] = []
        for trace, matched_symbols in traces:
            page_file = trace[-1]
            for rp in self.route_map.get(page_file, [None]):
                semantics = self._merge_semantics(cf.path, cf.semantic_tags)
                impacts.append(PageImpact(
                    changed_file=cf.path,
                    page_file=page_file,
                    route_path=rp,
                    module_name=module_name_from_path(page_file),
                    trace=trace,
                    impact_type=self._impact_type(cf.file_type),
                    confidence=self._confidence(cf.file_type, trace, semantics),
                    impact_reason=self._reason(cf.file_type, trace, semantics, matched_symbols),
                    semantic_tags=semantics,
                    matched_symbols=matched_symbols,
                ))
        return impacts, None

    def _build_page_direct_impacts(self, cf: ChangedFile) -> List[PageImpact]:
        semantics = self._merge_semantics(cf.path, cf.semantic_tags)
        changed_symbols = self._changed_symbols(cf.path, cf.symbols)
        return [PageImpact(
            changed_file=cf.path,
            page_file=cf.path,
            route_path=rp,
            module_name=cf.module_guess,
            trace=[cf.path],
            impact_type="direct",
            confidence="high",
            impact_reason="changed file is page",
            semantic_tags=semantics,
            matched_symbols=changed_symbols,
        ) for rp in self.route_map.get(cf.path, [None])]

    def _trace_to_pages(self, start_file: str, changed_symbols: List[str]) -> List[Tuple[List[str], List[str]]]:
        q = deque([(start_file, [start_file], changed_symbols, True)])
        visited = set()
        found: List[Tuple[List[str], List[str]]] = []
        while q:
            cur, trace, active_symbols, strict_symbols = q.popleft()
            visit_key = (cur, tuple(active_symbols), strict_symbols)
            if visit_key in visited:
                continue
            visited.add(visit_key)
            if cur in self.pages:
                found.append((trace, active_symbols))
                continue
            for parent in self.reverse_imports.get(cur, []):
                transition = self._symbols_for_parent(cur, parent, active_symbols, strict_symbols)
                if transition is None:
                    continue
                next_symbols, next_strict = transition
                next_key = (parent, tuple(next_symbols), next_strict)
                if next_key not in visited:
                    q.append((parent, trace + [parent], next_symbols, next_strict))
        uniq = []
        seen = set()
        for tr, matched_symbols in found:
            k = " -> ".join(tr) + "::" + ",".join(matched_symbols)
            if k not in seen:
                seen.add(k)
                uniq.append((tr, matched_symbols))
        return uniq

    def _changed_symbols(self, file_path: str, diff_symbols: List[str]) -> List[str]:
        facts = self.ast_facts.get(file_path, {})
        available_symbols = uniq_keep_order(
            list(facts.get("exports", []))
            + list(facts.get("component_names", []))
            + list(facts.get("hook_names", []))
        )
        if not diff_symbols:
            return []
        matched = [symbol for symbol in diff_symbols if symbol in set(available_symbols)]
        return uniq_keep_order(matched)

    def _symbols_for_parent(self, current_file: str, parent_file: str, active_symbols: List[str], strict_symbols: bool) -> Optional[Tuple[List[str], bool]]:
        parent_facts = self.ast_facts.get(parent_file, {})
        import_bindings = parent_facts.get("resolved_import_bindings", [])
        reexport_bindings = parent_facts.get("resolved_reexport_bindings", [])
        identifier_counts = parent_facts.get("identifier_counts", {})

        if not strict_symbols:
            return active_symbols, False

        binding_matches: List[str] = []
        for binding in import_bindings:
            if binding.get("resolved") != current_file:
                continue
            imported_name = binding.get("imported")
            local_name = binding.get("local")
            if active_symbols and imported_name not in {"*", "default"} and imported_name not in active_symbols:
                continue
            if local_name and identifier_counts.get(local_name, 0) <= 1:
                continue
            if imported_name == "*" or imported_name == "default":
                binding_matches.extend(active_symbols)
            else:
                binding_matches.append(imported_name)

        reexport_matches: List[str] = []
        for binding in reexport_bindings:
            if binding.get("resolved") != current_file:
                continue
            imported_name = binding.get("imported")
            exported_name = binding.get("exported")
            if imported_name == "*":
                reexport_matches.extend(active_symbols or ["*"])
                continue
            if active_symbols and imported_name not in active_symbols:
                continue
            reexport_matches.append(exported_name or imported_name)

        if reexport_matches:
            return uniq_keep_order(reexport_matches), True
        if binding_matches:
            return uniq_keep_order(binding_matches or active_symbols), False
        if not active_symbols:
            return active_symbols, False
        return None

    def _merge_semantics(self, file_path: str, diff_tags: List[str]) -> List[str]:
        ast_tags = self.ast_facts.get(file_path, {}).get("semantic_tags", [])
        return uniq_keep_order(diff_tags + ast_tags)

    def _impact_type(self, file_type: str) -> str:
        if file_type in {"route", "page", "business-component", "api", "hook", "store"}:
            return "direct"
        return "indirect"

    def _confidence(self, file_type: str, trace: List[str], semantics: List[str]) -> str:
        if file_type in {"page", "route"}:
            return "high"
        if file_type in {"business-component", "api", "hook", "store"} and len(trace) <= 3:
            return "high"
        if file_type == "shared-component":
            return "medium" if any(x in semantics for x in ["form", "table", "modal", "button"]) else "low"
        if file_type in {"utils", "config-or-schema", "style"}:
            return "low"
        return "medium"

    def _reason(self, file_type: str, trace: List[str], semantics: List[str], matched_symbols: List[str]) -> str:
        sem = ", ".join(semantics[:6]) if semantics else "no semantic tag"
        symbol_part = f", symbols: {', '.join(matched_symbols)}" if matched_symbols else ""
        return f"{file_type} changed, traced to page through {len(trace)} hop(s), semantics: {sem}{symbol_part}"
