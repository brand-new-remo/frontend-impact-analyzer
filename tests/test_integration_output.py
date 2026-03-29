from __future__ import annotations

import json
from pathlib import Path

from front_end_impact_analyzer import FrontendImpactAnalysisEngine


def test_engine_outputs_sorted_case_json_array_against_snapshot():
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"
    diff_text = (root / "fixtures" / "diffs" / "shared_search_form.diff").read_text(encoding="utf-8")
    expected_output = json.loads((root / "fixtures" / "expected" / "shared_search_form_cases.json").read_text(encoding="utf-8"))

    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    assert isinstance(state.output, list)
    assert state.output == expected_output
    assert state.meta["analysisStatus"] == "success"
    assert state.meta["outputContract"] == "case-array-v1"
    assert state.meta["stateSchema"] == "schemas/analysis-state.schema.json"
    assert state.meta["resultSchema"] == "schemas/case-array.schema.json"
    assert state.meta["statusSummary"] == {
        "changedFileCount": 1,
        "pageImpactCount": 1,
        "caseCount": 5,
        "unresolvedFileCount": 0,
        "diagnosticCount": 0,
    }
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
    assert state_schema["type"] == "object"
    assert "meta" in state_schema["required"]
    assert state_schema["properties"]["output"]["$ref"] == "case-array.schema.json"
