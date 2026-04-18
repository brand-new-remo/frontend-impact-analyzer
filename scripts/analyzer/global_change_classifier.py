from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List


class GlobalChangeClassifier:
    def classify(self, file_path: str, file_type: str, semantic_tags: List[str]) -> Dict:
        path = file_path.replace("\\", "/")
        lower = path.lower()
        filename = Path(lower).name
        signals: List[str] = []
        kind = ""

        if filename in {"app.tsx", "app.ts", "main.tsx", "main.ts"} and self._near_src_root(lower):
            kind = "app-entry"
            signals.append("app-entry")
        elif "/providers/" in lower or "/provider/" in lower or re.search(r"(provider|providers)\.[jt]sx?$", lower):
            kind = "app-provider"
            signals.append("provider")
        elif "/layouts/" in lower or "/layout/" in lower or re.search(r"(layout|shell)\.[jt]sx?$", lower):
            kind = "app-layout"
            signals.append("layout")
        elif "theme" in lower or "design-token" in lower or "global.css" in lower:
            kind = "theme-or-global-style"
            signals.append("theme-or-global-style")
        elif "i18n" in lower or "locale" in lower or "/locales/" in lower:
            kind = "i18n"
            signals.append("i18n")
        elif "permission" in lower or "auth" in lower or "access" in lower:
            kind = "auth-or-permission"
            signals.append("auth-or-permission")
        elif self._is_request_infrastructure(lower):
            kind = "request-infrastructure"
            signals.append("request-infrastructure")
        elif file_type == "route" and self._is_route_root(lower):
            kind = "route-root"
            signals.append("route-root")

        if not kind and "permission" in semantic_tags:
            kind = "auth-or-permission"
            signals.append("permission-signal")

        is_global = bool(kind)
        return {
            "isGlobal": is_global,
            "kind": kind,
            "signals": signals,
            "confidence": "medium" if is_global else "low",
            "blastRadiusPolicy": "do-not-expand-to-all-pages" if is_global else "",
            "reason": self._reason(kind),
            "recommendedAnalysis": (
                "Analyze cross-cutting behavior and representative flows; do not generate cases for every page."
                if is_global else ""
            ),
        }

    def _near_src_root(self, lower_path: str) -> bool:
        parts = lower_path.split("/")
        if "src" not in parts:
            return False
        src_idx = parts.index("src")
        return len(parts) - src_idx <= 2

    def _is_request_infrastructure(self, lower_path: str) -> bool:
        filename = Path(lower_path).name
        return (
            filename in {"request.ts", "request.tsx", "http.ts", "http.tsx", "httpclient.ts", "axios.ts"}
            or "interceptor" in lower_path
            or lower_path.endswith("/api/client.ts")
            or lower_path.endswith("/services/client.ts")
        )

    def _is_route_root(self, lower_path: str) -> bool:
        filename = Path(lower_path).name
        return filename in {"index.ts", "index.tsx", "routes.ts", "routes.tsx", "router.ts", "router.tsx"}

    def _reason(self, kind: str) -> str:
        return {
            "app-entry": "application entry or root app file changed",
            "app-provider": "application provider changed",
            "app-layout": "application layout or shell changed",
            "theme-or-global-style": "theme, design token, or global style changed",
            "i18n": "global i18n or locale infrastructure changed",
            "auth-or-permission": "auth, permission, or access infrastructure changed",
            "request-infrastructure": "request client or interceptor infrastructure changed",
            "route-root": "root route configuration changed",
        }.get(kind, "")
