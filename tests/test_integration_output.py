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
    assert state.codeImpact["unresolvedFiles"] == []
    assert state.codeImpact["sharedRisks"] == [
        {
            "file": "src/components/shared/SearchForm.tsx",
            "risk": "shared component change may affect multiple pages but should be validated based on actual trace and semantics",
            "confidence": "medium",
        }
    ]
