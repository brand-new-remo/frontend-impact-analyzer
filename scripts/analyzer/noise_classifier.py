from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


LOCK_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "uv.lock",
    "poetry.lock",
}

GENERATED_HINTS = (
    "/generated/",
    "/__generated__/",
    ".generated.",
    ".gen.",
)

TEST_HINTS = (
    "/__tests__/",
    "/test/",
    "/tests/",
    "/fixtures/",
    "/mocks/",
    "/__mocks__/",
)

STYLE_EXTS = {".css", ".scss", ".sass", ".less", ".styl"}
SRC_EXTS = {".ts", ".tsx", ".js", ".jsx"}


class NoiseClassifier:
    def classify(self, file_path: str, added_lines: List[str], removed_lines: List[str], is_format_only: bool = False) -> Dict:
        path = file_path.replace("\\", "/")
        lower = path.lower()
        signals: List[str] = []
        confidence = "low"
        kind = "logic-change"
        should_analyze = True

        if is_format_only:
            signals.append("format-only")
            kind = "format-only"
            confidence = "high"
            should_analyze = False

        path_kind = self._path_noise_kind(lower)
        if path_kind:
            signals.append(path_kind)
            if path_kind in {"lockfile", "generated-file"}:
                kind = path_kind
                confidence = "high"
                should_analyze = False
            elif path_kind in {"test-only", "style-only"} and kind == "logic-change":
                kind = path_kind
                confidence = "medium"
                should_analyze = False

        if kind == "logic-change":
            content_kind = self._content_noise_kind(added_lines, removed_lines)
            if content_kind:
                signals.append(content_kind)
                kind = content_kind
                confidence = "high" if content_kind in {"comment-only", "import-only"} else "medium"
                should_analyze = content_kind in {"type-only", "text-only"}

        logic_score = self._logic_change_score(kind, confidence, added_lines, removed_lines)
        return {
            "kind": kind,
            "signals": self._uniq(signals),
            "confidence": confidence,
            "shouldAnalyze": should_analyze,
            "logicChangeScore": logic_score,
            "reason": self._reason(kind),
        }

    def _path_noise_kind(self, lower_path: str) -> str:
        filename = lower_path.split("/")[-1]
        suffix = Path(lower_path).suffix
        if filename in LOCK_FILES:
            return "lockfile"
        if any(hint in lower_path for hint in GENERATED_HINTS):
            return "generated-file"
        if lower_path.endswith(".map"):
            return "generated-file"
        if suffix in STYLE_EXTS:
            return "style-only"
        if any(hint in lower_path for hint in TEST_HINTS) or re.search(r"\.(test|spec)\.[jt]sx?$", lower_path):
            return "test-only"
        return ""

    def _content_noise_kind(self, added_lines: List[str], removed_lines: List[str]) -> str:
        changed = [line for line in added_lines + removed_lines if line.strip()]
        if not changed:
            return "format-only"
        if all(self._is_comment_line(line) for line in changed):
            return "comment-only"
        if all(self._is_import_export_line(line) for line in changed):
            return "import-only"
        if all(self._is_type_line(line) for line in changed):
            return "type-only"
        if all(self._is_text_like_line(line) for line in changed):
            return "text-only"
        return ""

    def _is_comment_line(self, line: str) -> bool:
        stripped = line.strip()
        return (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.startswith("*/")
            or stripped.startswith("{/*")
            or stripped.endswith("*/")
        )

    def _is_import_export_line(self, line: str) -> bool:
        stripped = line.strip()
        return (
            stripped.startswith("import ")
            or stripped.startswith("export {")
            or stripped.startswith("export type ")
            or stripped.startswith("export * from")
        )

    def _is_type_line(self, line: str) -> bool:
        stripped = line.strip()
        return bool(re.match(r"^(export\s+)?(type|interface)\b", stripped)) or stripped in {"}", "};"}

    def _is_text_like_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return True
        if re.match(r"^[\w.-]+\s*:\s*['\"].*['\"],?$", stripped):
            return True
        if re.match(r"^[A-Za-z0-9_.-]+\s*=\s*['\"].*['\"]$", stripped):
            return True
        return False

    def _logic_change_score(self, kind: str, confidence: str, added_lines: List[str], removed_lines: List[str]) -> float:
        if kind in {"format-only", "comment-only", "import-only", "lockfile", "generated-file"}:
            return 0.0
        if kind in {"test-only", "style-only"}:
            return 0.2
        if kind in {"type-only", "text-only"}:
            return 0.35 if confidence == "medium" else 0.25
        changed_count = len([line for line in added_lines + removed_lines if line.strip()])
        if changed_count <= 2:
            return 0.55
        if changed_count <= 8:
            return 0.75
        return 0.9

    def _reason(self, kind: str) -> str:
        return {
            "format-only": "only formatting changed",
            "comment-only": "only comments changed",
            "import-only": "only imports or re-exports changed",
            "type-only": "only type/interface declarations changed",
            "text-only": "only text-like key/value lines changed",
            "style-only": "style file change; keep outside logic analysis unless manually selected",
            "test-only": "test/mock/fixture change; not a product behavior change by default",
            "generated-file": "generated artifact change",
            "lockfile": "dependency lockfile change",
            "logic-change": "logic-like code change",
        }.get(kind, "unclassified change")

    def _uniq(self, items: List[str]) -> List[str]:
        out = []
        seen = set()
        for item in items:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out
