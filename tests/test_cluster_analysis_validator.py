from __future__ import annotations

from analyzer.cluster_analysis_validator import ClusterAnalysisValidator


def test_validator_flags_generic_case_without_evidence_or_action():
    report = ClusterAnalysisValidator().validate(
        {"clusterId": "cluster-001"},
        {
            "clusterId": "cluster-001",
            "changeIntent": "form-submit-flow",
            "userVisibleChange": "用户列表搜索提交链路变化",
            "affectedFunctionUnits": ["搜索提交"],
            "confidence": "medium",
            "uncertainties": [],
            "cases": [
                {
                    "caseName": "User List Page 页面基础回归",
                    "testSteps": ["观察页面初始化渲染"],
                    "expectedResults": ["页面正常加载", "无报错"],
                }
            ],
        },
    )

    assert report["status"] == "fail"
    assert any(item["kind"] == "case-without-evidence" for item in report["issues"])
    assert any(item["kind"] == "generic-case-language" for item in report["warnings"])
    assert any(item["kind"] == "case-without-clear-action" for item in report["warnings"])


def test_validator_accepts_evidence_backed_action_case():
    report = ClusterAnalysisValidator().validate(
        {"clusterId": "cluster-001"},
        {
            "clusterId": "cluster-001",
            "changeIntent": "form-submit-flow",
            "userVisibleChange": "用户列表搜索提交链路变化",
            "affectedFunctionUnits": ["搜索提交"],
            "codeEvidenceUsed": [{"file": "src/components/shared/SearchForm.tsx"}],
            "docEvidenceUsed": [],
            "confidence": "high",
            "uncertainties": [],
            "cases": [
                {
                    "caseName": "用户列表搜索条件提交后刷新结果",
                    "testSteps": ["进入用户列表", "输入搜索条件并提交"],
                    "expectedResults": ["列表按搜索条件刷新"],
                    "evidence": [{"file": "src/components/shared/SearchForm.tsx"}],
                }
            ],
        },
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["warnings"] == []
