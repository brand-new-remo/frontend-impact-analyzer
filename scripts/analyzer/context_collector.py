from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from .common import normalize_path, rel_path, safe_read_text, uniq_keep_order


DOC_EXTS = {".md", ".txt", ".json", ".yaml", ".yml"}


class DocumentIndexer:
    def __init__(self, project_root: Path, config: Dict):
        self.project_root = project_root
        self.config = config

    def build(self) -> Dict:
        documents = []
        profile_file = self._path(self.config["paths"].get("projectProfileFile", ""))
        if profile_file.exists() and profile_file.is_file() and profile_file.suffix.lower() in DOC_EXTS:
            text = safe_read_text(profile_file)
            documents.append({
                "docId": self._doc_id("project-profile", profile_file),
                "kind": "project-profile",
                "path": rel_path(profile_file, self.project_root),
                "title": self._title(profile_file, text),
                "headings": self._headings(text),
                "keywords": self._keywords(profile_file, text),
                "charCount": len(text),
                "_text": text,
            })
        for kind, key in [
            ("repo-wiki", "repoWikiDir"),
            ("requirement", "requirementsDir"),
            ("spec", "specsDir"),
        ]:
            root = self._path(self.config["paths"].get(key, ""))
            if not root.exists() or not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in DOC_EXTS:
                    text = safe_read_text(path)
                    documents.append({
                        "docId": self._doc_id(kind, path),
                        "kind": kind,
                        "path": rel_path(path, self.project_root),
                        "title": self._title(path, text),
                        "headings": self._headings(text),
                        "keywords": self._keywords(path, text),
                        "charCount": len(text),
                        "_text": text,
                    })
        return {
            "documentCount": len(documents),
            "documents": documents,
        }

    @staticmethod
    def strip_cached_text(document_index: Dict) -> Dict:
        """Return a copy of the document index without the cached _text fields,
        suitable for writing to disk."""
        return {
            "documentCount": document_index.get("documentCount", 0),
            "documents": [
                {k: v for k, v in doc.items() if k != "_text"}
                for doc in document_index.get("documents", [])
            ],
        }

    def retrieve(self, document_index: Dict, cluster: Dict, limit: int = 6) -> List[Dict]:
        keywords = self._cluster_keywords(cluster)
        scored = []
        for doc in document_index.get("documents", []):
            text = doc.get("_text") or safe_read_text(self.project_root / doc["path"])
            snippets = self._snippets(text, keywords)
            matched = uniq_keep_order([kw for kw in keywords if kw and kw.lower() in (doc["path"] + " " + doc["title"] + " " + text[:12000]).lower()])
            if matched and not snippets:
                snippets = self._leading_snippets(text, matched)
            score = len(matched) * 3 + len(snippets)
            if score <= 0:
                continue
            scored.append({
                "docId": doc["docId"],
                "kind": doc["kind"],
                "path": doc["path"],
                "title": doc["title"],
                "matchedKeywords": matched[:20],
                "matchedHeadings": self._matched_headings(doc.get("headings", []), keywords),
                "candidateSnippets": snippets[:3],
                "score": score,
            })
        scored.sort(key=lambda item: (-item["score"], item["kind"], item["path"]))
        return scored[:limit]

    def _path(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else self.project_root / path

    def _doc_id(self, kind: str, path: Path) -> str:
        rel = rel_path(path, self.project_root)
        value = re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-").lower()
        return f"{kind}-{value}"

    def _title(self, path: Path, text: str) -> str:
        for line in text.splitlines():
            if line.strip().startswith("#"):
                return line.strip("# ").strip()
        return path.stem.replace("-", " ").replace("_", " ").title()

    def _headings(self, text: str) -> List[str]:
        headings = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.strip("# ").strip())
        return headings[:30]

    def _keywords(self, path: Path, text: str) -> List[str]:
        tokens = []
        tokens.extend(_tokens(path.stem))
        tokens.extend(_tokens(text[:8000]))
        return uniq_keep_order(tokens)[:120]

    def _cluster_keywords(self, cluster: Dict) -> List[str]:
        parts: List[str] = []
        for file_path in cluster.get("changedFiles", []) + cluster.get("candidatePages", []):
            parts.extend(Path(file_path).parts)
            parts.append(Path(file_path).stem)
        parts.extend(cluster.get("changedSymbols", []))
        parts.extend(cluster.get("semanticTags", []))
        parts.extend(cluster.get("candidateRoutes", []))
        parts.append(cluster.get("title", ""))
        return uniq_keep_order([token for part in parts for token in _tokens(str(part)) if len(token) > 1])[:80]

    def _snippets(self, text: str, keywords: List[str]) -> List[Dict]:
        paragraphs = _paragraphs_with_headings(text)
        hits = []
        for idx, paragraph in enumerate(paragraphs):
            lower = paragraph["text"].lower()
            matched = [kw for kw in keywords if kw.lower() in lower]
            if not matched:
                continue
            hits.append({
                "index": idx,
                "heading": paragraph["heading"],
                "matchedKeywords": uniq_keep_order(matched)[:12],
                "snippet": paragraph["text"][:1200],
            })
        hits.sort(key=lambda item: -len(item["matchedKeywords"]))
        return hits

    def _matched_headings(self, headings: List[str], keywords: List[str]) -> List[str]:
        matches = []
        for heading in headings:
            lower = heading.lower()
            if any(keyword.lower() in lower for keyword in keywords):
                matches.append(heading)
        return uniq_keep_order(matches)[:10]

    def _leading_snippets(self, text: str, matched_keywords: List[str]) -> List[Dict]:
        snippets = []
        for idx, paragraph in enumerate(_paragraphs_with_headings(text)[:3]):
            snippets.append({
                "index": idx,
                "heading": paragraph["heading"],
                "matchedKeywords": matched_keywords[:12],
                "snippet": paragraph["text"][:1200],
                "fallbackReason": "Document path/title matched this cluster; no exact paragraph keyword match was found.",
            })
        return snippets


class ClusterContextCollector:
    def __init__(
        self,
        project_root: Path,
        config: Dict,
        imports: Dict[str, List[str]],
        reverse_imports: Dict[str, List[str]],
        ast_facts: Dict[str, Dict],
        document_index: Dict,
        routes: List | None = None,
    ):
        self.project_root = project_root
        self.config = config
        self.imports = imports
        self.reverse_imports = reverse_imports
        self.ast_facts = ast_facts
        self.document_index = document_index
        self.routes = routes or []
        self.doc_indexer = DocumentIndexer(project_root, config)
        self._file_cache: Dict[str, str] = {}

    def _cached_read(self, file_path: str) -> str:
        """Read a source file with per-instance caching to avoid redundant I/O."""
        if file_path not in self._file_cache:
            self._file_cache[file_path] = safe_read_text(self.project_root / file_path)
        return self._file_cache[file_path]

    def collect(self, cluster: Dict, diff_index: Dict) -> Dict:
        max_files = int(self.config["analysis"].get("maxFilesPerClusterContext", 8))
        max_doc_snippets = int(self.config["analysis"].get("maxDocumentSnippetsPerCluster", 6))
        files = self._context_files(cluster)[:max_files]
        diff_by_file = {item["path"]: item for item in diff_index.get("files", [])}
        code_evidence = [self._code_evidence(path, cluster, diff_by_file.get(path)) for path in files]
        document_candidates = self.doc_indexer.retrieve(self.document_index, cluster, max_doc_snippets)
        comment_evidence = self._comment_evidence(files, cluster, diff_by_file)

        context = {
            "clusterId": cluster["clusterId"],
            "clusterSummary": {
                "title": cluster.get("title", ""),
                "changedFiles": cluster.get("changedFiles", []),
                "changedSymbols": cluster.get("changedSymbols", []),
                "candidatePages": cluster.get("candidatePages", []),
                "candidateRoutes": cluster.get("candidateRoutes", []),
                "semanticTags": cluster.get("semanticTags", []),
                "confidence": cluster.get("confidence", "low"),
                "reason": cluster.get("reason", ""),
            },
            "diffEvidence": [diff_by_file[file_path] for file_path in cluster.get("changedFiles", []) if file_path in diff_by_file],
            "traceEvidence": self._trace_evidence(cluster),
            "routeEvidence": self._route_evidence(cluster),
            "flowHints": self._flow_hints(cluster),
            "codeEvidence": code_evidence,
            "commentEvidence": comment_evidence,
            "documentCandidates": document_candidates,
            "riskHints": self._risk_hints(cluster),
            "analysisPrompt": (
                "Analyze only this cluster. Determine the precise user-visible change, affected function units, "
                "evidence, confidence, uncertainties, and QA cases. Use documentCandidates when relevant; "
                "open original documents if snippets are insufficient. Treat commentEvidence as candidate business evidence, "
                "not final proof. Do not broaden scope beyond evidence."
            ),
        }
        return self._apply_context_budget(context)

    def _context_files(self, cluster: Dict) -> List[str]:
        files: List[str] = []
        files.extend(cluster.get("changedFiles", []))
        files.extend(cluster.get("candidatePages", []))
        for file_path in list(files):
            files.extend(self.imports.get(file_path, [])[:3])
            files.extend(self.reverse_imports.get(file_path, [])[:2])
        return uniq_keep_order(files)

    def _code_evidence(self, file_path: str, cluster: Dict, diff_item: Dict | None) -> Dict:
        content = self._cached_read(file_path)
        snippet = self._focused_snippet(content, cluster)
        return {
            "file": normalize_path(file_path),
            "kind": self._evidence_kind(file_path, cluster),
            "whyIncluded": self._why_included(file_path, cluster),
            "symbols": self.ast_facts.get(file_path, {}).get("exports", []) + self.ast_facts.get(file_path, {}).get("component_names", []),
            "semanticTags": self.ast_facts.get(file_path, {}).get("semantic_tags", []),
            "diffPreview": (diff_item or {}).get("changedLinePreview", {}),
            "hunks": (diff_item or {}).get("hunks", []),
            "snippet": snippet,
        }

    def _focused_snippet(self, content: str, cluster: Dict) -> str:
        max_chars = int(self.config["analysis"].get("maxSnippetChars", 5000))
        if len(content) <= max_chars:
            return content

        keywords = uniq_keep_order(cluster.get("changedSymbols", []) + cluster.get("semanticTags", []))
        lines = content.splitlines()
        selected: List[str] = []
        hit_indexes = []
        for idx, line in enumerate(lines):
            if any(keyword and keyword in line for keyword in keywords):
                hit_indexes.append(idx)
        for idx in hit_indexes[:8]:
            start = max(0, idx - 8)
            end = min(len(lines), idx + 20)
            selected.append("\n".join(lines[start:end]))
        snippet = "\n\n...\n\n".join(selected) if selected else content[:max_chars]
        return snippet[:max_chars]

    def _evidence_kind(self, file_path: str, cluster: Dict) -> str:
        if file_path in cluster.get("changedFiles", []):
            return "changed-file"
        if file_path in cluster.get("candidatePages", []):
            return "candidate-page"
        return "neighbor-dependency"

    def _why_included(self, file_path: str, cluster: Dict) -> str:
        if file_path in cluster.get("changedFiles", []):
            return "This file is directly changed in the diff for this cluster."
        if file_path in cluster.get("candidatePages", []):
            return "This page is a traced candidate impact page for changed files in this cluster."
        for seed in cluster.get("seeds", []):
            for trace in seed.get("traces", []):
                if file_path in trace:
                    return "This file appears in an import trace from a changed file to a candidate page."
        return "This file is a direct neighboring dependency of a changed file or candidate page."

    def _comment_evidence(self, files: List[str], cluster: Dict, diff_by_file: Dict[str, Dict]) -> List[Dict]:
        limit = int(self.config["analysis"].get("maxCommentEvidencePerCluster", 20))
        comments: List[Dict] = []
        for file_path in files:
            content = self._cached_read(file_path)
            if not content:
                continue
            hunk_ranges = self._hunk_line_ranges(diff_by_file.get(file_path, {}))
            symbols = cluster.get("changedSymbols", [])
            semantic_tags = cluster.get("semanticTags", [])
            comments.extend(self._comments_from_content(file_path, content, hunk_ranges, symbols, semantic_tags))
        comments.sort(key=lambda item: (
            not item["nearChangedHunk"],
            not item["nearChangedSymbol"],
            not item["nearBusinessKeyword"],
            item["file"],
            item["line"],
        ))
        return comments[:limit]

    def _comments_from_content(self, file_path: str, content: str, hunk_ranges: List[range], symbols: List[str], semantic_tags: List[str]) -> List[Dict]:
        lines = content.splitlines()
        comments: List[Dict] = []
        business_keywords = self._business_comment_keywords(semantic_tags)
        for idx, line in enumerate(lines, start=1):
            text = self._extract_comment_text(line.strip())
            if not text:
                continue
            near_hunk = self._line_near_ranges(idx, hunk_ranges, radius=20)
            near_symbol = self._near_symbol(lines, idx, symbols)
            near_keyword = any(keyword.lower() in text.lower() for keyword in business_keywords)
            if not (near_hunk or near_symbol or near_keyword):
                continue
            comments.append({
                "file": normalize_path(file_path),
                "line": idx,
                "text": text[:200],
                "nearChangedHunk": near_hunk,
                "nearChangedSymbol": near_symbol,
                "nearBusinessKeyword": near_keyword,
                "reason": self._comment_reason(near_hunk, near_symbol, near_keyword),
                "usageGuidance": "Candidate business evidence only. Use it with code or document support; do not treat comments as final proof.",
            })
        return comments

    def _extract_comment_text(self, stripped: str) -> str:
        if stripped.startswith("//"):
            return stripped[2:].strip()
        if stripped.startswith("/*") and stripped.endswith("*/"):
            return stripped[2:-2].strip(" *")
        if stripped.startswith("{/*") and stripped.endswith("*/}"):
            return stripped[3:-3].strip(" *")
        return ""

    def _hunk_line_ranges(self, diff_item: Dict) -> List[range]:
        ranges = []
        for hunk in diff_item.get("hunks", []):
            start = int(hunk.get("newStart") or 0)
            count = int(hunk.get("newLines") or 0)
            if start:
                ranges.append(range(start, start + max(count, 1)))
        return ranges

    def _line_near_ranges(self, line_no: int, ranges: List[range], radius: int) -> bool:
        for line_range in ranges:
            if line_no >= max(1, line_range.start - radius) and line_no <= line_range.stop + radius:
                return True
        return False

    def _near_symbol(self, lines: List[str], line_no: int, symbols: List[str]) -> bool:
        if not symbols:
            return False
        start = max(0, line_no - 8)
        end = min(len(lines), line_no + 8)
        window = "\n".join(lines[start:end])
        return any(symbol and symbol in window for symbol in symbols)

    def _business_comment_keywords(self, semantic_tags: List[str]) -> List[str]:
        base = [
            "权限", "角色", "管理员", "提交", "保存", "刷新", "筛选", "分页", "批量", "审批",
            "状态", "禁用", "校验", "回显", "弹窗", "列表", "详情", "删除", "新增", "编辑",
            "permission", "role", "submit", "save", "refresh", "filter", "pagination", "batch",
            "status", "disabled", "validation", "modal", "list", "detail", "delete", "create", "edit",
        ]
        tag_keywords = {
            "permission": ["权限", "角色", "permission", "role"],
            "submit": ["提交", "保存", "submit", "save"],
            "list-query": ["筛选", "分页", "刷新", "filter", "pagination", "refresh"],
            "modal": ["弹窗", "modal"],
            "disabled-state": ["禁用", "disabled"],
            "validation": ["校验", "validation"],
        }
        for tag in semantic_tags:
            base.extend(tag_keywords.get(tag, []))
        return uniq_keep_order(base)

    def _comment_reason(self, near_hunk: bool, near_symbol: bool, near_keyword: bool) -> str:
        reasons = []
        if near_hunk:
            reasons.append("near changed hunk")
        if near_symbol:
            reasons.append("near changed symbol")
        if near_keyword:
            reasons.append("contains business keyword")
        return ", ".join(reasons)

    def _trace_evidence(self, cluster: Dict) -> List[Dict]:
        evidence = []
        for seed in cluster.get("seeds", []):
            for trace in seed.get("traces", []):
                if not trace:
                    continue
                candidate_page = trace[-1] if trace[-1] in cluster.get("candidatePages", []) else ""
                evidence.append({
                    "changedFile": seed.get("changedFile", ""),
                    "candidatePage": candidate_page,
                    "candidateRoutes": seed.get("candidateRoutes", []),
                    "trace": trace,
                    "hopCount": max(0, len(trace) - 1),
                    "confidence": seed.get("confidence", "low"),
                    "matchedSymbols": seed.get("symbols", []),
                    "semanticTags": seed.get("semanticTags", []),
                    "whyIncluded": "Import/reverse-import tracing connected the changed file to this candidate page.",
                })
        return evidence

    def _route_evidence(self, cluster: Dict) -> List[Dict]:
        candidate_pages = set(cluster.get("candidatePages", []))
        candidate_routes = set(cluster.get("candidateRoutes", []))
        evidence = []
        for route in self.routes:
            route_path = self._route_value(route, "route_path")
            linked_page = self._route_value(route, "linked_page")
            if route_path not in candidate_routes and linked_page not in candidate_pages:
                continue
            evidence.append({
                "routePath": route_path,
                "linkedPage": linked_page,
                "sourceFile": self._route_value(route, "source_file"),
                "routeComponent": self._route_value(route, "route_component"),
                "parentRoute": self._route_value(route, "parent_route"),
                "confidence": self._route_value(route, "confidence") or "medium",
                "routeComment": self._route_value(route, "route_comment") or "",
                "displayName": self._route_value(route, "display_name") or "",
                "displayNameSource": self._route_value(route, "display_name_source") or "",
                "whyIncluded": "Route binding matched a candidate route or candidate page in this cluster.",
            })
        return evidence

    def _risk_hints(self, cluster: Dict) -> List[Dict]:
        hints = []
        for seed in cluster.get("seeds", []):
            changed_file = seed.get("changedFile", "")
            file_type = seed.get("fileType", "unknown")
            global_classification = seed.get("globalClassification", {})
            if global_classification.get("isGlobal"):
                hints.append({
                    "file": changed_file,
                    "kind": "global-change",
                    "confidence": global_classification.get("confidence", "medium"),
                    "hint": "Global or cross-cutting infrastructure changed. Analyze representative affected flows; do not generate cases for every page.",
                    "globalKind": global_classification.get("kind", ""),
                    "blastRadiusPolicy": global_classification.get("blastRadiusPolicy", "do-not-expand-to-all-pages"),
                })
            if seed.get("unresolved"):
                hints.append({
                    "file": changed_file,
                    "kind": "unresolved-trace",
                    "confidence": "low",
                    "hint": "No candidate page trace was found; keep conclusions tentative unless documents or manual inspection support them.",
                })
            if file_type == "shared-component":
                hints.append({
                    "file": changed_file,
                    "kind": "shared-component",
                    "confidence": "medium",
                    "hint": "Shared component change should be validated only on traced candidate pages, not expanded to the whole app by default.",
                })
            if file_type == "api" or seed.get("apiChanges"):
                hints.append({
                    "file": changed_file,
                    "kind": "api-contract-candidate",
                    "confidence": seed.get("confidence", "medium"),
                    "hint": "API-like change may affect request fields, response mapping, error handling, or refresh behavior; verify with code and docs.",
                    "apiChanges": seed.get("apiChanges", []),
                })
            if "permission" in seed.get("semanticTags", []):
                hints.append({
                    "file": changed_file,
                    "kind": "permission-candidate",
                    "confidence": seed.get("confidence", "medium"),
                    "hint": "Permission signal found; verify role visibility and operation availability only when supported by local code evidence.",
                })
        return hints

    def _flow_hints(self, cluster: Dict) -> List[Dict]:
        hints = []
        semantic_tags = cluster.get("semanticTags", [])
        actions = self._possible_user_actions(semantic_tags)
        states = self._possible_state_changes(semantic_tags)
        for trace in self._trace_evidence(cluster):
            hints.append({
                "entry": {
                    "route": (trace.get("candidateRoutes") or [""])[0],
                    "page": trace.get("candidatePage", ""),
                },
                "changedFile": trace.get("changedFile", ""),
                "trace": trace.get("trace", []),
                "possibleUserActions": actions,
                "possibleStateChanges": states,
                "directEvidence": [
                    {"type": "traceEvidence", "changedFile": trace.get("changedFile", ""), "candidatePage": trace.get("candidatePage", "")}
                ],
                "note": "This is a navigation/execution-flow hint for Claude, not a final impact conclusion.",
            })
        if not hints:
            hints.append({
                "entry": {
                    "route": (cluster.get("candidateRoutes") or [""])[0],
                    "page": (cluster.get("candidatePages") or [""])[0],
                },
                "changedFile": (cluster.get("changedFiles") or [""])[0],
                "trace": [],
                "possibleUserActions": actions,
                "possibleStateChanges": states,
                "directEvidence": [],
                "note": "No page trace was available; use this only as a weak flow hint.",
            })
        return hints

    def _possible_user_actions(self, semantic_tags: List[str]) -> List[str]:
        mapping = {
            "button": "click an affected button or action entry",
            "modal": "open, cancel, and confirm the affected modal",
            "form": "enter field values and submit the affected form",
            "validation": "trigger empty, invalid, and valid field validation",
            "table": "load the list and interact with affected rows or table controls",
            "columns": "inspect affected list columns and mapped values",
            "api": "trigger the affected request and inspect page feedback",
            "list-query": "change query conditions and refresh the list",
            "detail": "enter detail/edit view and verify displayed or echoed data",
            "delete": "trigger delete and confirm result feedback",
            "permission": "compare visibility and operation availability across roles",
            "navigation": "enter through the route, navigate away, refresh, and return",
            "route": "enter through the route, navigate away, refresh, and return",
            "upload": "select a file and complete upload validation and submission",
            "disabled-state": "verify disabled/read-only conditions and blocked operations",
            "submit": "submit the affected operation and inspect success/error feedback",
        }
        return uniq_keep_order([mapping[tag] for tag in semantic_tags if tag in mapping])

    def _possible_state_changes(self, semantic_tags: List[str]) -> List[str]:
        mapping = {
            "disabled-state": "control enabled/disabled or read-only state may change",
            "loading": "loading and pending feedback may change",
            "api": "request parameters, response mapping, or error feedback may change",
            "list-query": "list data, pagination, filter, or sort state may change",
            "form": "form field value, validation, or dirty state may change",
            "validation": "validation error visibility or blocking condition may change",
            "modal": "modal visibility or submit/cancel state may change",
            "permission": "role-based visibility or authorization state may change",
            "navigation": "route entry, redirect, refresh, or back behavior may change",
            "route": "route entry, redirect, refresh, or back behavior may change",
            "table": "row selection, row action, or displayed cell state may change",
            "columns": "displayed column value or column visibility may change",
            "submit": "submit result, toast, refresh, or error state may change",
        }
        return uniq_keep_order([mapping[tag] for tag in semantic_tags if tag in mapping])

    def _route_value(self, route, name: str):
        if isinstance(route, dict):
            return route.get(name)
        return getattr(route, name, None)

    def _apply_context_budget(self, context: Dict) -> Dict:
        max_chars = int(self.config["analysis"].get("maxClusterContextChars", 60000))
        estimated = self._estimated_chars(context)
        context["contextBudget"] = {
            "maxChars": max_chars,
            "estimatedChars": estimated,
            "truncated": False,
            "strategy": "trim code snippets first, then document snippets",
        }
        if estimated <= max_chars:
            return context

        # Trim code snippets — track saved chars instead of re-serialising.
        for item in context.get("codeEvidence", []):
            snippet = item.get("snippet", "")
            if len(snippet) > 1200:
                estimated -= (len(snippet) - 1200)
                item["snippet"] = snippet[:1200]
                item["snippetTruncatedByBudget"] = True
            if estimated <= max_chars:
                context["contextBudget"]["truncated"] = True
                context["contextBudget"]["estimatedChars"] = estimated
                return context

        # Trim document snippets.
        for doc in context.get("documentCandidates", []):
            for snippet in doc.get("candidateSnippets", []):
                text = snippet.get("snippet", "")
                if len(text) > 500:
                    estimated -= (len(text) - 500)
                    snippet["snippet"] = text[:500]
                    snippet["snippetTruncatedByBudget"] = True
            if estimated <= max_chars:
                context["contextBudget"]["truncated"] = True
                context["contextBudget"]["estimatedChars"] = estimated
                return context

        context["contextBudget"]["truncated"] = True
        context["contextBudget"]["estimatedChars"] = estimated
        return context

    def _estimated_chars(self, value: Dict) -> int:
        return len(json.dumps(value, ensure_ascii=False))


def _tokens(text: str) -> List[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    ascii_tokens = re.findall(r"[A-Za-z0-9_]{2,}", spaced.lower())
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    return uniq_keep_order(ascii_tokens + cjk_tokens)


def _paragraphs_with_headings(text: str) -> List[Dict[str, str]]:
    current_heading = ""
    chunks = []
    current: List[str] = []
    current_chunk_heading = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current:
                chunks.append({"heading": current_chunk_heading, "text": "\n".join(current).strip()})
                current = []
            current_heading = stripped.strip("# ").strip()
            current_chunk_heading = current_heading
            continue
        if not stripped:
            if current:
                chunks.append({"heading": current_chunk_heading, "text": "\n".join(current).strip()})
                current = []
            current_chunk_heading = current_heading
            continue
        if not current:
            current_chunk_heading = current_heading
        current.append(line)
    if current:
        chunks.append({"heading": current_chunk_heading, "text": "\n".join(current).strip()})
    if chunks:
        return [chunk for chunk in chunks if chunk["text"]]

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if len(blocks) > 1:
        return [{"heading": "", "text": block} for block in blocks]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [{"heading": "", "text": "\n".join(lines[idx:idx + 8])} for idx in range(0, len(lines), 8)]
