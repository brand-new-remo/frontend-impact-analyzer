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
        if cf.file_type == "page":
            return self._build_page_direct_impacts(cf), None
        traces = self._trace_to_pages(cf.path)
        if not traces:
            return [], {
                "file": cf.path,
                "fileType": cf.file_type,
                "confidence": "low",
                "reason": "cannot trace to page via reverse imports",
            }
        impacts: List[PageImpact] = []
        for trace in traces:
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
                    impact_reason=self._reason(cf.file_type, trace, semantics),
                    semantic_tags=semantics,
                ))
        return impacts, None

    def _build_page_direct_impacts(self, cf: ChangedFile) -> List[PageImpact]:
        semantics = self._merge_semantics(cf.path, cf.semantic_tags)
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
        ) for rp in self.route_map.get(cf.path, [None])]

    def _trace_to_pages(self, start_file: str) -> List[List[str]]:
        q = deque([(start_file, [start_file])])
        visited = set()
        found: List[List[str]] = []
        while q:
            cur, trace = q.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            if cur in self.pages:
                found.append(trace)
                continue
            for parent in self.reverse_imports.get(cur, []):
                if parent not in visited:
                    q.append((parent, trace + [parent]))
        uniq = []
        seen = set()
        for tr in found:
            k = " -> ".join(tr)
            if k not in seen:
                seen.add(k)
                uniq.append(tr)
        return uniq

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

    def _reason(self, file_type: str, trace: List[str], semantics: List[str]) -> str:
        sem = ", ".join(semantics[:6]) if semantics else "no semantic tag"
        return f"{file_type} changed, traced to page through {len(trace)} hop(s), semantics: {sem}"
