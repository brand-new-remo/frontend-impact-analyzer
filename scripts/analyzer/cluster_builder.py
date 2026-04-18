from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

from .common import module_name_from_path, title_from_file, uniq_keep_order
from .models import ChangedFile, PageImpact


class ChangeClusterBuilder:
    def __init__(self, diff_text: str):
        self.diff_text = diff_text
        self.diff_previews = self._extract_diff_previews(diff_text)

    def build_diff_index(self, changed_files: List[ChangedFile]) -> Dict:
        files = []
        ignored = []
        for cf in changed_files:
            preview = self.diff_previews.get(cf.path, {})
            item = {
                "path": cf.path,
                "changeType": cf.change_type,
                "fileType": cf.file_type,
                "moduleGuess": cf.module_guess,
                "addedLines": cf.added_lines,
                "removedLines": cf.removed_lines,
                "isFormatOnly": cf.is_format_only,
                "noiseClassification": cf.noise_classification,
                "globalClassification": cf.global_classification,
                "symbols": cf.symbols,
                "semanticTags": cf.semantic_tags,
                "apiChanges": cf.api_changes,
                "hunkCount": preview.get("hunkCount", 0),
                "hunks": preview.get("hunks", []),
                "changedLinePreview": {
                    "added": preview.get("added", [])[:30],
                    "removed": preview.get("removed", [])[:30],
                },
                "analysisBucket": self._analysis_bucket(cf),
            }
            files.append(item)
            if item["analysisBucket"] != "deep-analysis":
                ignored.append({
                    "file": cf.path,
                    "bucket": item["analysisBucket"],
                    "reason": self._bucket_reason(item["analysisBucket"]),
                })

        return {
            "totalChangedFiles": len(changed_files),
            "files": files,
            "ignoredOrShallowFiles": ignored,
        }

    def build_file_impact_seeds(self, changed_files: List[ChangedFile], impacts: List[PageImpact], unresolved: List[Dict]) -> Dict:
        by_file: Dict[str, List[PageImpact]] = defaultdict(list)
        for impact in impacts:
            by_file[impact.changed_file].append(impact)

        unresolved_by_file = {item.get("file"): item for item in unresolved}
        seeds = []
        for cf in changed_files:
            file_impacts = by_file.get(cf.path, [])
            candidate_pages = uniq_keep_order([item.page_file for item in file_impacts])
            candidate_routes = uniq_keep_order([item.route_path for item in file_impacts if item.route_path])
            traces = [item.trace for item in file_impacts]
            semantic_tags = uniq_keep_order(cf.semantic_tags + [tag for item in file_impacts for tag in item.semantic_tags])
            confidence = self._seed_confidence(cf, file_impacts)
            seeds.append({
                "changedFile": cf.path,
                "changeType": cf.change_type,
                "fileType": cf.file_type,
                "moduleGuess": cf.module_guess,
                "noiseClassification": cf.noise_classification,
                "globalClassification": cf.global_classification,
                "symbols": cf.symbols,
                "semanticTags": semantic_tags,
                "apiChanges": cf.api_changes,
                "candidatePages": candidate_pages,
                "candidateRoutes": candidate_routes,
                "traces": traces,
                "confidence": confidence,
                "unresolved": unresolved_by_file.get(cf.path),
            })

        return {
            "seeds": seeds,
            "unresolvedFiles": unresolved,
        }

    def build_clusters(self, seeds_data: Dict, max_deep_clusters: int = 30) -> Dict:
        grouped: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        for seed in seeds_data.get("seeds", []):
            if not seed.get("noiseClassification", {}).get("shouldAnalyze", True):
                continue
            if seed.get("globalClassification", {}).get("isGlobal"):
                grouped[("global", seed["globalClassification"].get("kind") or "global-change")].append(seed)
                continue
            if seed.get("candidatePages"):
                for page in seed["candidatePages"]:
                    grouped[("page", page)].append(seed)
            else:
                tags = "-".join(seed.get("semanticTags", [])[:3]) or "no-tags"
                grouped[("module", f"{seed.get('moduleGuess') or 'unknown'}:{tags}")].append(seed)

        clusters = []
        for idx, ((kind, key), seeds) in enumerate(grouped.items(), start=1):
            changed_files = uniq_keep_order([seed["changedFile"] for seed in seeds])
            pages = uniq_keep_order([page for seed in seeds for page in seed.get("candidatePages", [])])
            routes = uniq_keep_order([route for seed in seeds for route in seed.get("candidateRoutes", [])])
            semantic_tags = uniq_keep_order([tag for seed in seeds for tag in seed.get("semanticTags", [])])
            symbols = uniq_keep_order([symbol for seed in seeds for symbol in seed.get("symbols", [])])
            api_changes = [change for seed in seeds for change in seed.get("apiChanges", [])]
            confidence = self._cluster_confidence(kind, seeds)
            needs_deep = idx <= max_deep_clusters and any(seed.get("confidence") != "low" for seed in seeds)
            cluster_id = f"cluster-{idx:03d}"
            title = self._cluster_title(kind, key, pages, seeds)
            clusters.append({
                "clusterId": cluster_id,
                "clusterKey": f"{kind}:{key}",
                "scope": "global" if kind == "global" else "page-or-module",
                "title": title,
                "changedFiles": changed_files,
                "changedSymbols": symbols,
                "candidatePages": pages,
                "candidateRoutes": routes,
                "semanticTags": semantic_tags,
                "apiChanges": api_changes,
                "globalClassification": self._merge_global_classification(seeds),
                "reason": self._cluster_reason(kind, pages),
                "confidence": confidence,
                "needsDeepAnalysis": needs_deep,
                "seeds": seeds,
            })

        clusters.sort(key=lambda item: (not item["needsDeepAnalysis"], item["clusterKey"], item["clusterId"]))
        return {
            "clusterCount": len(clusters),
            "clusters": clusters,
        }

    def build_coverage(self, diff_index: Dict, clusters_data: Dict, diagnostics: List[Dict]) -> Dict:
        files = diff_index.get("files", [])
        buckets: Dict[str, int] = defaultdict(int)
        for item in files:
            buckets[item.get("analysisBucket", "unknown")] += 1
        noise_buckets: Dict[str, int] = defaultdict(int)
        for item in files:
            noise_kind = item.get("noiseClassification", {}).get("kind", "unknown")
            noise_buckets[noise_kind] += 1
        clusters = clusters_data.get("clusters", [])
        return {
            "totalChangedFiles": len(files),
            "deepAnalysisClusterCount": len([item for item in clusters if item.get("needsDeepAnalysis")]),
            "shallowAnalysisClusterCount": len([item for item in clusters if not item.get("needsDeepAnalysis")]),
            "ignoredOrShallowFileCount": len(diff_index.get("ignoredOrShallowFiles", [])),
            "filesByBucket": dict(sorted(buckets.items())),
            "filesByNoiseKind": dict(sorted(noise_buckets.items())),
            "noiseFileCount": len([item for item in files if not item.get("noiseClassification", {}).get("shouldAnalyze", True)]),
            "diagnosticCount": len(diagnostics),
            "warnings": diagnostics,
        }

    def _analysis_bucket(self, cf: ChangedFile) -> str:
        noise = cf.noise_classification or {}
        if not noise.get("shouldAnalyze", True):
            return f"noise-{noise.get('kind', 'unknown')}"
        if cf.is_format_only:
            return "format-only"
        if cf.file_type == "non-source":
            return "non-source"
        if cf.file_type == "style":
            return "shallow-style"
        if cf.file_type in {"page", "route", "api", "store", "hook", "business-component", "shared-component"}:
            return "deep-analysis"
        if cf.file_type in {"utils", "config-or-schema"} and (cf.semantic_tags or cf.api_changes):
            return "deep-analysis"
        return "shallow-analysis"

    def _bucket_reason(self, bucket: str) -> str:
        return {
            "format-only": "format-only change",
            "noise-format-only": "only formatting changed",
            "noise-comment-only": "only comments changed",
            "noise-import-only": "only imports or re-exports changed",
            "noise-lockfile": "dependency lockfile change",
            "noise-generated-file": "generated artifact change",
            "noise-test-only": "test/mock/fixture change; not a product behavior change by default",
            "noise-style-only": "style change; keep outside logic analysis unless manually selected",
            "non-source": "non-source file",
            "shallow-style": "style change, keep as shallow risk unless tied to page evidence",
            "shallow-analysis": "weak impact signals; keep as shallow candidate",
        }.get(bucket, "not selected for deep analysis")

    def _seed_confidence(self, cf: ChangedFile, impacts: List[PageImpact]) -> str:
        if cf.is_format_only or not cf.noise_classification.get("shouldAnalyze", True):
            return "low"
        if cf.global_classification.get("isGlobal"):
            return "medium"
        if any(item.confidence == "high" for item in impacts):
            return "high"
        if impacts:
            return "medium"
        return "low"

    def _cluster_confidence(self, kind: str, seeds: List[Dict]) -> str:
        confidences = [seed.get("confidence") for seed in seeds]
        if kind == "page" and "high" in confidences:
            return "high"
        if kind == "global":
            return "medium" if confidences else "low"
        if "medium" in confidences or "high" in confidences:
            return "medium"
        return "low"

    def _cluster_title(self, kind: str, key: str, pages: List[str], seeds: List[Dict]) -> str:
        if kind == "global":
            return f"Global {key.replace('-', ' ')} change cluster"
        if pages:
            return f"{title_from_file(pages[0])} impact cluster"
        modules = uniq_keep_order([seed.get("moduleGuess", "unknown") for seed in seeds])
        return f"{modules[0] if modules else module_name_from_path(key)} candidate impact cluster"

    def _cluster_reason(self, kind: str, pages: List[str]) -> str:
        if kind == "global":
            return "changed files are global or cross-cutting infrastructure; analyze separately without expanding to every page"
        if kind == "page":
            return "changed files trace to the same candidate page and should be analyzed together"
        if pages:
            return "changed files have overlapping page evidence"
        return "changed files lack page trace and are grouped by module plus semantic tags"

    def _merge_global_classification(self, seeds: List[Dict]) -> Dict:
        globals_ = [seed.get("globalClassification", {}) for seed in seeds if seed.get("globalClassification", {}).get("isGlobal")]
        if not globals_:
            return {}
        kinds = uniq_keep_order([item.get("kind", "") for item in globals_ if item.get("kind")])
        signals = uniq_keep_order([signal for item in globals_ for signal in item.get("signals", [])])
        return {
            "isGlobal": True,
            "kinds": kinds,
            "signals": signals,
            "confidence": "medium",
            "blastRadiusPolicy": "do-not-expand-to-all-pages",
            "recommendedAnalysis": "Analyze cross-cutting behavior and representative flows; do not generate cases for every page.",
        }

    def _extract_diff_previews(self, diff_text: str) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        current = ""
        current_hunk = None
        hunk_re = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_lines>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_lines>\d+))? @@")
        for raw_line in diff_text.splitlines():
            m = re.match(r"^diff --git a/(.*?) b/(.*?)$", raw_line)
            if m:
                if current and current_hunk:
                    out[current]["hunks"].append(current_hunk)
                current = m.group(2).replace("\\", "/")
                out[current] = {"added": [], "removed": [], "hunkCount": 0, "hunks": []}
                current_hunk = None
                continue
            if not current:
                continue
            if raw_line.startswith("@@"):
                if current_hunk:
                    out[current]["hunks"].append(current_hunk)
                hunk_match = hunk_re.match(raw_line)
                if hunk_match:
                    old_start = int(hunk_match.group("old_start"))
                    old_lines = int(hunk_match.group("old_lines") or "1")
                    new_start = int(hunk_match.group("new_start"))
                    new_lines = int(hunk_match.group("new_lines") or "1")
                else:
                    old_start = old_lines = new_start = new_lines = 0
                out[current]["hunkCount"] += 1
                current_hunk = {
                    "oldStart": old_start,
                    "oldLines": old_lines,
                    "newStart": new_start,
                    "newLines": new_lines,
                    "header": raw_line,
                    "addedPreview": [],
                    "removedPreview": [],
                }
                continue
            if current_hunk is None:
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                payload = raw_line[1:]
                if len(out[current]["added"]) < 80:
                    out[current]["added"].append(payload)
                if len(current_hunk["addedPreview"]) < 20:
                    current_hunk["addedPreview"].append(payload)
            elif raw_line.startswith("-") and not raw_line.startswith("---"):
                payload = raw_line[1:]
                if len(out[current]["removed"]) < 80:
                    out[current]["removed"].append(payload)
                if len(current_hunk["removedPreview"]) < 20:
                    current_hunk["removedPreview"].append(payload)
        if current and current_hunk:
            out[current]["hunks"].append(current_hunk)
        return out
