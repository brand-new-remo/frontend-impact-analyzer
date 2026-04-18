from __future__ import annotations

from typing import Dict, List


GENERIC_CASE_TERMS = [
    "页面基础回归",
    "页面正常加载",
    "无报错",
    "无白屏",
    "符合预期",
    "关键操作",
    "主流程",
    "相关按钮",
    "相关页面",
    "功能正常",
]


ACTION_WORDS = [
    "click",
    "submit",
    "open",
    "close",
    "enter",
    "select",
    "search",
    "filter",
    "save",
    "delete",
    "upload",
    "refresh",
    "navigate",
    "点击",
    "提交",
    "打开",
    "关闭",
    "进入",
    "选择",
    "搜索",
    "筛选",
    "保存",
    "删除",
    "上传",
    "刷新",
    "跳转",
    "输入",
    "清空",
]


class ClusterAnalysisValidator:
    def validate(self, cluster: Dict, analysis: Dict) -> Dict:
        issues: List[Dict] = []
        warnings: List[Dict] = []

        self._validate_required_cluster_fields(analysis, issues)
        self._validate_confidence(analysis, warnings)
        self._validate_cases(analysis, issues, warnings)

        status = "pass"
        if issues:
            status = "fail"
        elif warnings:
            status = "warn"

        return {
            "clusterId": cluster.get("clusterId") or analysis.get("clusterId", ""),
            "status": status,
            "issueCount": len(issues),
            "warningCount": len(warnings),
            "issues": issues,
            "warnings": warnings,
        }

    def _validate_required_cluster_fields(self, analysis: Dict, issues: List[Dict]) -> None:
        for field in ["clusterId", "changeIntent", "userVisibleChange", "affectedFunctionUnits", "confidence", "uncertainties", "cases"]:
            if field not in analysis:
                issues.append(self._issue("missing-field", f"Missing required field `{field}`."))
        if not analysis.get("changeIntent"):
            issues.append(self._issue("empty-change-intent", "`changeIntent` must describe the kind of change."))
        if not analysis.get("userVisibleChange"):
            issues.append(self._issue("empty-user-visible-change", "`userVisibleChange` must describe the actual user-visible behavior."))

    def _validate_confidence(self, analysis: Dict, warnings: List[Dict]) -> None:
        if analysis.get("confidence") != "high":
            return
        if not analysis.get("codeEvidenceUsed"):
            warnings.append(self._issue("high-confidence-without-code-evidence", "High confidence analysis should cite code evidence."))

    def _validate_cases(self, analysis: Dict, issues: List[Dict], warnings: List[Dict]) -> None:
        cases = analysis.get("cases", [])
        if not isinstance(cases, list):
            issues.append(self._issue("cases-not-array", "`cases` must be an array."))
            return

        for idx, case in enumerate(cases):
            label = f"cases[{idx}]"
            for field in ["caseName", "testSteps", "expectedResults"]:
                if field not in case:
                    issues.append(self._issue("case-missing-field", f"{label} is missing `{field}`.", idx))

            case_name = str(case.get("caseName") or case.get("用例名称") or "")
            steps = case.get("testSteps") or case.get("测试步骤") or []
            expected = case.get("expectedResults") or case.get("预期结果") or []
            evidence = case.get("evidence") or analysis.get("codeEvidenceUsed", []) + analysis.get("docEvidenceUsed", [])
            combined = " ".join([case_name] + [str(item) for item in steps] + [str(item) for item in expected])

            if not evidence:
                issues.append(self._issue("case-without-evidence", f"{label} has no case evidence and no analysis-level evidence.", idx))
            if self._is_generic_case(case_name, combined):
                warnings.append(self._issue("generic-case-language", f"{label} uses generic template-like language.", idx))
            if not self._has_action(steps):
                warnings.append(self._issue("case-without-clear-action", f"{label} testSteps do not contain a clear user action.", idx))
            if not expected:
                issues.append(self._issue("case-without-expected-results", f"{label} has no expected results.", idx))

    def _is_generic_case(self, case_name: str, combined: str) -> bool:
        if any(term in case_name for term in GENERIC_CASE_TERMS):
            return True
        generic_hits = sum(1 for term in GENERIC_CASE_TERMS if term in combined)
        return generic_hits >= 2

    def _has_action(self, steps: List[str]) -> bool:
        text = " ".join(str(item).lower() for item in steps)
        return any(word.lower() in text for word in ACTION_WORDS)

    def _issue(self, kind: str, message: str, case_index: int | None = None) -> Dict:
        item = {"kind": kind, "message": message}
        if case_index is not None:
            item["caseIndex"] = case_index
        return item
