from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .cluster_analysis_validator import ClusterAnalysisValidator
from .common import uniq_keep_order
from .workflow import write_json


class ClusterAnalysisMerger:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir

    def merge(self, fallback_result: Dict | None = None) -> Dict:
        manifest = self._read_json(self.run_dir / "00-run-manifest.json", {})
        coverage = self._read_json(self.run_dir / "90-coverage-report.json", {})
        clusters = self._read_json(self.run_dir / "05-change-clusters.json", {}).get("clusters", [])
        analyses = self._read_cluster_analyses()
        route_display_names = self._route_display_names()
        validator = ClusterAnalysisValidator()

        analysis_by_cluster = {item.get("clusterId"): item for item in analyses if item.get("clusterId")}
        cases: List[Dict] = []
        cluster_summaries = []
        validation_reports = []

        for cluster in clusters:
            cluster_id = cluster["clusterId"]
            analysis = analysis_by_cluster.get(cluster_id)
            if analysis:
                validation_report = validator.validate(cluster, analysis)
                validation_reports.append(validation_report)
                normalized_cases = [
                    self._normalize_analysis_case(cluster, analysis, case, route_display_names)
                    for case in analysis.get("cases", [])
                ]
                cases.extend(normalized_cases)
                cluster_summaries.append(self._analysis_summary(cluster, analysis, len(normalized_cases), validation_report))
            else:
                cluster_summaries.append({
                    "clusterId": cluster_id,
                    "title": cluster.get("title", ""),
                    "status": "missing-analysis",
                    "caseCount": 0,
                    "confidence": cluster.get("confidence", "low"),
                    "uncertainties": ["Claude cluster-analysis file is missing; no cases are generated for this cluster."],
                })

        cases = self._dedupe_cases(cases)
        used_analyses = [item for item in analyses if item.get("clusterId") in {cluster["clusterId"] for cluster in clusters}]
        orphan_analyses = [item for item in analyses if item.get("clusterId") not in {cluster["clusterId"] for cluster in clusters}]

        return {
            "meta": {
                "outputContract": "cluster-analysis-result-v1",
                "runId": manifest.get("runId"),
                "analysisStatus": self._status(clusters, used_analyses),
                "resultSource": "cluster-analysis-merge",
            },
            "summary": {
                "clusterCount": len(clusters),
                "analyzedClusterCount": len(used_analyses),
                "missingAnalysisClusterCount": max(0, len(clusters) - len(used_analyses)),
                "caseCount": len(cases),
                "fallbackCaseCount": 0,
                "validationIssueCount": sum(item["issueCount"] for item in validation_reports),
                "validationWarningCount": sum(item["warningCount"] for item in validation_reports),
                "candidatePages": uniq_keep_order([
                    page for cluster in clusters for page in cluster.get("candidatePages", [])
                ]),
                "candidateRoutes": uniq_keep_order([
                    route for cluster in clusters for route in cluster.get("candidateRoutes", [])
                ]),
            },
            "coverage": coverage,
            "clusters": cluster_summaries,
            "clusterAnalyses": used_analyses,
            "validationReports": validation_reports,
            "orphanClusterAnalyses": orphan_analyses,
            "cases": cases,
            "fallbackCases": [],
            "nextStepsForClaude": [
                "Use the case-refiner agent when available to refine final cases after merge.",
                "Read 99-merged-result.json, validationReports, 05-change-clusters.json, and cluster-analysis/*.analysis.json.",
                "Write 99-refined-cases.json matching schemas/refined-cases.schema.json.",
                "Only improve wording, dedupe, split, remove, or reorder cases without changing case intent, user flow, scope, evidence, priority, or confidence.",
            ],
        }

    def write(self, output_path: Path, fallback_result: Dict | None = None) -> Dict:
        result = self.merge(fallback_result)
        write_json(output_path, result)
        write_json(self.run_dir / "99-merged-result.json", result)
        return result

    def _read_cluster_analyses(self) -> List[Dict]:
        analysis_dir = self.run_dir / "cluster-analysis"
        if not analysis_dir.exists():
            return []
        analyses = []
        for path in sorted(analysis_dir.glob("*.analysis.json")):
            item = self._read_json(path, {})
            if item:
                item.setdefault("analysisFile", str(path))
                analyses.append(item)
        return analyses

    def _normalize_analysis_case(self, cluster: Dict, analysis: Dict, case: Dict, route_display_names: Dict[str, str]) -> Dict:
        evidence = case.get("evidence") or []
        if not evidence:
            evidence = analysis.get("codeEvidenceUsed", []) + analysis.get("docEvidenceUsed", [])
        return {
            "clusterId": cluster["clusterId"],
            "caseSource": "cluster-analysis",
            "moduleName": case.get("moduleName") or self._module_from_cluster(cluster),
            "pageName": case.get("pageName") or self._display_page_from_cluster(cluster, route_display_names),
            "routePath": case.get("routePath") or self._first(cluster.get("candidateRoutes", [])),
            "caseName": case.get("caseName") or case.get("用例名称") or "",
            "businessGoal": case.get("businessGoal") or "",
            "entry": case.get("entry") or {},
            "preconditions": case.get("preconditions") or case.get("前置条件") or [],
            "testSteps": case.get("testSteps") or case.get("测试步骤") or [],
            "expectedResults": case.get("expectedResults") or case.get("预期结果") or [],
            "priority": case.get("priority") or case.get("用例等级") or analysis.get("confidence") or cluster.get("confidence") or "medium",
            "confidence": case.get("confidence") or case.get("用例可置信度") or analysis.get("confidence") or cluster.get("confidence") or "medium",
            "changeIntent": case.get("changeIntent") or analysis.get("changeIntent") or "",
            "userVisibleChange": case.get("userVisibleChange") or analysis.get("userVisibleChange") or "",
            "affectedFunctionUnit": case.get("affectedFunctionUnit") or "",
            "impactReason": case.get("impactReason") or case.get("来源描述") or analysis.get("userVisibleChange") or cluster.get("reason", ""),
            "evidence": evidence,
            "uncertainties": case["uncertainties"] if "uncertainties" in case else analysis.get("uncertainties", []),
        }

    def _analysis_summary(self, cluster: Dict, analysis: Dict, case_count: int, validation_report: Dict) -> Dict:
        return {
            "clusterId": cluster["clusterId"],
            "title": cluster.get("title", ""),
            "status": "analyzed",
            "changeIntent": analysis.get("changeIntent", ""),
            "userVisibleChange": analysis.get("userVisibleChange", ""),
            "affectedFunctionUnits": analysis.get("affectedFunctionUnits", []),
            "caseCount": case_count,
            "confidence": analysis.get("confidence") or cluster.get("confidence", "medium"),
            "uncertainties": analysis.get("uncertainties", []),
            "validationStatus": validation_report.get("status", "pass"),
            "validationIssueCount": validation_report.get("issueCount", 0),
            "validationWarningCount": validation_report.get("warningCount", 0),
        }

    def _dedupe_cases(self, cases: List[Dict]) -> List[Dict]:
        out = []
        seen = set()
        for case in cases:
            key = (
                case.get("clusterId"),
                case.get("caseSource"),
                case.get("pageName"),
                case.get("caseName"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(case)
        return out

    def _status(self, clusters: List[Dict], analyses: List[Dict]) -> str:
        if not clusters:
            return "success"
        if len(analyses) >= len(clusters):
            return "success"
        if analyses:
            return "partial_success"
        return "needs_cluster_analysis"

    def _module_from_cluster(self, cluster: Dict) -> str:
        for seed in cluster.get("seeds", []):
            module = seed.get("moduleGuess")
            if module and module != "unknown":
                return module
        for page in cluster.get("candidatePages", []):
            parts = Path(page).parts
            if "pages" in parts:
                idx = parts.index("pages")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        return "unknown"

    def _page_from_cluster(self, cluster: Dict) -> str:
        page = self._first(cluster.get("candidatePages", []))
        return Path(page).stem if page else cluster.get("title", "")

    def _display_page_from_cluster(self, cluster: Dict, route_display_names: Dict[str, str]) -> str:
        for route in cluster.get("candidateRoutes", []):
            if route_display_names.get(route):
                return route_display_names[route]
        return self._page_from_cluster(cluster)

    def _first(self, items: List[str]) -> str:
        return items[0] if items else ""

    def _read_json(self, path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _route_display_names(self) -> Dict[str, str]:
        state = self._read_json(self.run_dir / "98-analysis-state.json", {})
        routes = state.get("codeGraph", {}).get("routes", [])
        return {
            item.get("route_path"): item.get("display_name")
            for item in routes
            if item.get("route_path") and item.get("display_name")
        }
