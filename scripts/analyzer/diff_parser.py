from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .common import uniq_keep_order
from .models import ChangedFile
from .noise_classifier import NoiseClassifier


class GitDiffParser:
    DIFF_FILE_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
    NEW_FILE_RE = re.compile(r"^new file mode ")
    DELETE_FILE_RE = re.compile(r"^deleted file mode ")
    HUNK_RE = re.compile(r"^@@ .* @@")
    COMMIT_TYPE_RE = re.compile(r"\b(feat|fix|refactor|perf|style|chore|docs|test)(\([^)]+\))?:", re.I)

    SYMBOL_PATTERNS = [
        re.compile(r"\bfunction\s+([A-Za-z_]\w*)"),
        re.compile(r"\bconst\s+([A-Za-z_]\w*)\s*="),
        re.compile(r"\bclass\s+([A-Za-z_]\w*)"),
        re.compile(r"<([A-Z][A-Za-z0-9_]*)"),
    ]

    SEMANTIC_PATTERNS = {
        "button": [r"<Button", r"onClick", r"handleClick", r"\bbutton\b"],
        "modal": [r"<Modal", r"<Drawer", r"\bopen\s*=", r"\bvisible\s*=", r"setOpen", r"setVisible"],
        "form": [r"<Form", r"<Form\.Item", r"\brules\s*=", r"\brequired\b", r"\bvalidate"],
        "table": [r"<Table", r"\bcolumns\s*=", r"\browSelection\b", r"\bpagination\b", r"\bsorter\b", r"\bfilters\b"],
        "route": [r"createBrowserRouter", r"useRoutes", r"\bpath\s*:", r"\belement\s*:"],
        "permission": [r"permission", r"hasPermission", r"\brole\b", r"\bauth\b", r"\bcan[A-Z]"],
        "api": [r"\bfetch\(", r"\baxios", r"\brequest\(", r"\bget\(", r"\bpost\(", r"\bput\(", r"\bdelete\("],
        "state": [r"\buseState\b", r"\buseReducer\b", r"\buseEffect\b", r"\buseMemo\b", r"\bdispatch\(", r"\bset[A-Z]"],
        "navigation": [r"\bnavigate\(", r"\buseNavigate\b", r"<Link", r"\bto="],
        "validation": [r"\brules\s*=", r"\brequired\b", r"\bvalidator\b", r"\bpattern\b"],
        "list-query": [r"\bpage(Size|Num)?\b", r"\bquery\b", r"\bsearch\b", r"\bfilter\b"],
        "submit": [r"\bonSubmit\b", r"\bonOk\b", r"\bhandleSubmit\b"],
        "columns": [r"\bcolumns\s*="],
        "detail": [r"\bdetail\b", r"\bgetById\b", r"\brecord\b", r"\brow\."],
        "loading": [r"\bloading\b", r"\bsetLoading\b"],
        "disabled-state": [r"\bdisabled\b", r"\breadOnly\b"],
        "export": [r"\bexport\b"],
    }
    FIELD_NAME_PATTERNS = [
        re.compile(r"""["']([A-Za-z_]\w*)["']\s*:"""),
        re.compile(r"""\b([A-Za-z_]\w*)\s*:\s*[^:]"""),
    ]
    IDENTIFIER_PATTERN = re.compile(r"""\b([A-Za-z_]\w*)\b""")
    ENUM_VALUE_PATTERN = re.compile(r"""["']([A-Z][A-Z0-9_]+|[a-z][A-Za-z0-9_-]+)["']""")
    REQUEST_HINT_RE = re.compile(r"\b(params|payload|body|request|req|query)\b", re.I)
    RESPONSE_HINT_RE = re.compile(r"\b(response|result|data|res)\b", re.I)
    PAGINATION_HINT_RE = re.compile(r"\b(page|pageNum|pageNo|pageSize|limit|offset|cursor)\b", re.I)
    DETAIL_HINT_RE = re.compile(r"\bdetail\w*|\bgetById\b|\binfo\w*", re.I)
    LIST_HINT_RE = re.compile(r"\blist\w*|\bquery\b|\bsearch\b|\bfilter\w*", re.I)
    ENUM_HINT_RE = re.compile(r"\b(enum|status|type|state)\b", re.I)
    STRONG_API_SIGNAL_RE = re.compile(r"\b(params|payload|body|request|response|result|data|enum|pageNum|pageNo|pageSize|limit|offset|cursor|getById|detail\w*|list\s*:)\b", re.I)

    def __init__(self, diff_text: str):
        self.diff_text = diff_text
        self.noise_classifier = NoiseClassifier()

    def parse(self) -> Tuple[List[str], List[ChangedFile]]:
        commit_types = uniq_keep_order([m.group(1).lower() for m in self.COMMIT_TYPE_RE.finditer(self.diff_text)])
        changed_files: List[ChangedFile] = []
        current: Optional[ChangedFile] = None
        in_hunk = False
        added_content: List[str] = []
        removed_content: List[str] = []

        for raw_line in self.diff_text.splitlines():
            line = raw_line.rstrip("\n")
            m = self.DIFF_FILE_RE.match(line)
            if m:
                if current:
                    self._finalize_changed_file(current, added_content, removed_content)
                    changed_files.append(current)
                current = ChangedFile(path=m.group(2).replace('\\', '/'), change_type="modified")
                in_hunk = False
                added_content = []
                removed_content = []
                continue
            if current is None:
                continue
            if self.NEW_FILE_RE.match(line):
                current.change_type = "added"
                continue
            if self.DELETE_FILE_RE.match(line):
                current.change_type = "deleted"
                continue
            if self.HUNK_RE.match(line):
                in_hunk = True
                continue
            if not in_hunk:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                current.added_lines += 1
                payload = line[1:]
                added_content.append(payload)
                self._inspect_line(current, payload)
            elif line.startswith("-") and not line.startswith("---"):
                current.removed_lines += 1
                payload = line[1:]
                removed_content.append(payload)
                self._inspect_line(current, payload)

        if current:
            self._finalize_changed_file(current, added_content, removed_content)
            changed_files.append(current)

        return commit_types, changed_files

    def _finalize_changed_file(self, current: ChangedFile, added_content: List[str], removed_content: List[str]) -> None:
        current.is_format_only = self._is_format_only_change(added_content, removed_content)
        current.noise_classification = self.noise_classifier.classify(
            current.path,
            added_content,
            removed_content,
            current.is_format_only,
        )
        if not current.noise_classification.get("shouldAnalyze", True):
            current.symbols = []
            current.semantic_tags = []
            current.api_changes = []
        else:
            current.api_changes = self._analyze_api_changes(current.path, added_content, removed_content)
            current.semantic_tags.extend(self._semantic_tags_from_api_changes(current.api_changes))
        current.symbols = uniq_keep_order(current.symbols)
        current.semantic_tags = uniq_keep_order(current.semantic_tags)

    def _inspect_line(self, cf: ChangedFile, line: str):
        for pattern in self.SYMBOL_PATTERNS:
            for m in pattern.finditer(line):
                cf.symbols.append(m.group(1))
        for tag, patterns in self.SEMANTIC_PATTERNS.items():
            if any(self._matches_semantic_pattern(tag, p, line) for p in patterns):
                cf.semantic_tags.append(tag)

    def _matches_semantic_pattern(self, tag: str, pattern: str, line: str) -> bool:
        if tag == "disabled-state":
            return re.search(pattern, line) is not None
        return re.search(pattern, line, re.I) is not None

    def _is_format_only_change(self, added_lines: List[str], removed_lines: List[str]) -> bool:
        if not added_lines or not removed_lines:
            return False
        return self._normalize_for_format_compare(added_lines) == self._normalize_for_format_compare(removed_lines)

    def _normalize_for_format_compare(self, lines: List[str]) -> str:
        text = "".join(lines)
        return re.sub(r"""[\s,'"`;"]+""", "", text)

    def _analyze_api_changes(self, file_path: str, added_lines: List[str], removed_lines: List[str]) -> List[dict]:
        if not self._should_analyze_api_changes(file_path, added_lines, removed_lines):
            return []
        added_fields = self._extract_field_occurrences(added_lines)
        removed_fields = self._extract_field_occurrences(removed_lines)
        changes: List[dict] = []

        request_added = [item for item in added_fields if item["kind"] == "request-field-change"]
        request_removed = [item for item in removed_fields if item["kind"] == "request-field-change"]
        response_added = [item for item in added_fields if item["kind"] == "response-field-change"]
        response_removed = [item for item in removed_fields if item["kind"] == "response-field-change"]

        if len(request_added) == 1 and len(request_removed) == 1:
            changes.append({
                "kind": "request-field-change",
                "change": "rename",
                "field": request_added[0]["field"],
                "from": request_removed[0]["field"],
            })
        if len(response_added) == 1 and len(response_removed) == 1:
            changes.append({
                "kind": "response-field-change",
                "change": "rename",
                "field": response_added[0]["field"],
                "from": response_removed[0]["field"],
            })

        for group_name, items in (("added", added_fields), ("removed", removed_fields)):
            for item in items:
                changes.append({
                    "kind": item["kind"],
                    "change": group_name,
                    "field": item["field"],
                })

        enum_changes = self._extract_enum_changes(added_lines, removed_lines)
        changes.extend(enum_changes)
        return self._dedupe_api_changes(changes)

    def _should_analyze_api_changes(self, file_path: str, added_lines: List[str], removed_lines: List[str]) -> bool:
        if "/api/" in file_path or "/services/" in file_path:
            return True
        text = "\n".join(added_lines + removed_lines)
        return self.STRONG_API_SIGNAL_RE.search(text) is not None

    def _extract_field_occurrences(self, lines: List[str]) -> List[dict]:
        occurrences: List[dict] = []
        for line in lines:
            kinds = self._classify_api_line_kinds(line)
            for kind in kinds:
                for field in self._extract_fields_for_kind(line, kind):
                    occurrences.append({"kind": kind, "field": field})
        return occurrences

    def _extract_field_names(self, line: str) -> List[str]:
        fields: List[str] = []
        for pattern in self.FIELD_NAME_PATTERNS:
            for match in pattern.finditer(line):
                field = match.group(1)
                if field in {"return", "const", "function", "type"}:
                    continue
                fields.append(field)
        return uniq_keep_order(fields)

    def _classify_api_line_kinds(self, line: str) -> List[str]:
        kinds: List[str] = []
        if self.REQUEST_HINT_RE.search(line):
            kinds.append("request-field-change")
        if self.RESPONSE_HINT_RE.search(line):
            kinds.append("response-field-change")
        if self.PAGINATION_HINT_RE.search(line):
            kinds.append("pagination-shape-change")
        if self.DETAIL_HINT_RE.search(line):
            kinds.append("detail-schema-change")
        if self.LIST_HINT_RE.search(line):
            kinds.append("list-schema-change")
        return uniq_keep_order(kinds)

    def _extract_fields_for_kind(self, line: str, kind: str) -> List[str]:
        if kind == "request-field-change":
            fields = self._extract_brace_identifiers(line, {"params", "payload", "body", "request", "query"})
            return fields or self._extract_field_names(line)
        if kind == "response-field-change":
            fields = self._extract_brace_identifiers(line, {"response", "result", "data", "res"})
            return fields or self._extract_field_names(line)
        if kind == "pagination-shape-change":
            return uniq_keep_order([token for token in self._extract_brace_identifiers(line, set()) if self.PAGINATION_HINT_RE.search(token)])
        if kind == "detail-schema-change":
            fields = self._extract_brace_identifiers(line, {"detail", "info", "data", "response"})
            return [token for token in fields if self.DETAIL_HINT_RE.search(token)] or fields
        if kind == "list-schema-change":
            fields = self._extract_brace_identifiers(line, {"list", "columns"})
            return fields or self._extract_field_names(line)
        return self._extract_field_names(line)

    def _extract_brace_identifiers(self, line: str, ignore: set[str]) -> List[str]:
        tokens: List[str] = []
        for fragment in re.findall(r"\{([^{}]+)\}", line):
            for match in self.IDENTIFIER_PATTERN.finditer(fragment):
                token = match.group(1)
                if token in ignore:
                    continue
                tokens.append(token)
        return uniq_keep_order(tokens)

    def _extract_enum_changes(self, added_lines: List[str], removed_lines: List[str]) -> List[dict]:
        added_values = self._extract_enum_values(added_lines)
        removed_values = self._extract_enum_values(removed_lines)
        changes: List[dict] = []
        if not added_values and not removed_values:
            return changes
        if not any(self.ENUM_HINT_RE.search(line) for line in added_lines + removed_lines):
            return changes
        for value in added_values:
            changes.append({"kind": "enum-change", "change": "added", "field": value})
        for value in removed_values:
            changes.append({"kind": "enum-change", "change": "removed", "field": value})
        return changes

    def _extract_enum_values(self, lines: List[str]) -> List[str]:
        values: List[str] = []
        for line in lines:
            for match in self.ENUM_VALUE_PATTERN.finditer(line):
                values.append(match.group(1))
        return uniq_keep_order(values)

    def _semantic_tags_from_api_changes(self, api_changes: List[dict]) -> List[str]:
        mapping = {
            "request-field-change": ["api", "submit"],
            "response-field-change": ["api"],
            "enum-change": ["validation"],
            "pagination-shape-change": ["api", "list-query"],
            "detail-schema-change": ["api", "detail"],
            "list-schema-change": ["api", "list-query"],
        }
        tags: List[str] = []
        for change in api_changes:
            tags.extend(mapping.get(change["kind"], []))
        return uniq_keep_order(tags)

    def _dedupe_api_changes(self, changes: List[dict]) -> List[dict]:
        seen = set()
        out = []
        for change in changes:
            key = (change.get("kind"), change.get("change"), change.get("field"), change.get("from"))
            if key in seen:
                continue
            seen.add(key)
            out.append(change)
        return out
