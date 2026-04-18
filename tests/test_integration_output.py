from __future__ import annotations

import json
from pathlib import Path

from front_end_impact_analyzer import FrontendImpactAnalysisEngine


def test_engine_outputs_sorted_case_json_array_against_snapshot():
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"
    diff_text = (root / "fixtures" / "diffs" / "shared_search_form.diff").read_text(encoding="utf-8")
    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    assert isinstance(state.output, dict)
    assert state.output["cases"] == []
    assert state.output["fallbackCases"] == []
    assert state.meta["analysisStatus"] == "partial_success"
    assert state.meta["outputContract"] == "analysis-package-v2"
    assert state.meta["stateSchema"] == "schemas/analysis-state.schema.json"
    assert state.meta["resultSchema"] == "schemas/analysis-result.schema.json"
    assert state.meta["statusSummary"] == {
        "changedFileCount": 1,
        "pageImpactCount": 1,
        "caseCount": 0,
        "unresolvedFileCount": 0,
        "diagnosticCount": 0,
    }
    assert state.workflow["preflight"]["status"] == "blocked"
    assert state.output["summary"]["caseCount"] == 0
    assert state.output["summary"]["fallbackCaseCount"] == 0
    assert state.output["summary"]["missingAnalysisClusterCount"] == 1
    assert state.output["summary"]["clusterCount"] == 1
    assert state.output["coverage"]["totalChangedFiles"] == 1
    assert state.output["clusters"][0]["clusterId"] == "cluster-001"
    assert state.output["clusters"][0]["candidatePages"] == ["src/pages/users/UserListPage.tsx"]
    assert state.workflow["changeClusters"]["clusterCount"] == 1
    assert state.workflow["clusterContexts"][0]["clusterId"] == "cluster-001"
    assert state.codeImpact["unresolvedFiles"] == []
    assert state.codeImpact["sharedRisks"] == [
        {
            "file": "src/components/shared/SearchForm.tsx",
            "risk": "shared component change may affect multiple pages but should be validated based on actual trace and semantics",
            "confidence": "medium",
        }
    ]


def test_schema_files_exist_and_are_valid_json():
    root = Path(__file__).resolve().parents[1]
    result_schema = json.loads((root / "schemas" / "case-array.schema.json").read_text(encoding="utf-8"))
    analysis_result_schema = json.loads((root / "schemas" / "analysis-result.schema.json").read_text(encoding="utf-8"))
    cluster_analysis_schema = json.loads((root / "schemas" / "cluster-analysis.schema.json").read_text(encoding="utf-8"))
    state_schema = json.loads((root / "schemas" / "analysis-state.schema.json").read_text(encoding="utf-8"))

    assert result_schema["type"] == "array"
    assert result_schema["items"]["required"] == [
        "页面名",
        "用例名称",
        "测试步骤",
        "预期结果",
        "用例等级",
        "用例可置信度",
        "来源描述",
    ]
    assert analysis_result_schema["type"] == "object"
    assert "cases" in analysis_result_schema["required"]
    assert "fallbackCases" in analysis_result_schema["required"]
    assert cluster_analysis_schema["type"] == "object"
    assert "clusterId" in cluster_analysis_schema["required"]
    assert state_schema["type"] == "object"
    assert "meta" in state_schema["required"]
    assert state_schema["properties"]["output"]["$ref"] == "analysis-result.schema.json"
