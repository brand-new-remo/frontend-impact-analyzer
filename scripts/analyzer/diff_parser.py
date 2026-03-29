from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .common import uniq_keep_order
from .models import ChangedFile


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

    def __init__(self, diff_text: str):
        self.diff_text = diff_text

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
                    current.is_format_only = self._is_format_only_change(added_content, removed_content)
                    if current.is_format_only:
                        current.symbols = []
                        current.semantic_tags = []
                    current.symbols = uniq_keep_order(current.symbols)
                    current.semantic_tags = uniq_keep_order(current.semantic_tags)
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
            current.is_format_only = self._is_format_only_change(added_content, removed_content)
            if current.is_format_only:
                current.symbols = []
                current.semantic_tags = []
            current.symbols = uniq_keep_order(current.symbols)
            current.semantic_tags = uniq_keep_order(current.semantic_tags)
            changed_files.append(current)

        return commit_types, changed_files

    def _inspect_line(self, cf: ChangedFile, line: str):
        for pattern in self.SYMBOL_PATTERNS:
            for m in pattern.finditer(line):
                cf.symbols.append(m.group(1))
        for tag, patterns in self.SEMANTIC_PATTERNS.items():
            if any(re.search(p, line, re.I) for p in patterns):
                cf.semantic_tags.append(tag)

    def _is_format_only_change(self, added_lines: List[str], removed_lines: List[str]) -> bool:
        if not added_lines or not removed_lines:
            return False
        return self._normalize_for_format_compare(added_lines) == self._normalize_for_format_compare(removed_lines)

    def _normalize_for_format_compare(self, lines: List[str]) -> str:
        text = "".join(lines)
        return re.sub(r"""[\s,'"`;"]+""", "", text)
