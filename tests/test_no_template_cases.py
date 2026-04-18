from __future__ import annotations

from pathlib import Path

from front_end_impact_analyzer import FrontendImpactAnalysisEngine


def test_main_flow_does_not_generate_template_cases():
    root = Path(__file__).resolve().parents[1]
    project_root = root / "fixtures" / "sample_app"
    diff_text = (root / "fixtures" / "diffs" / "shared_search_form.diff").read_text(encoding="utf-8")

    state = FrontendImpactAnalysisEngine(project_root=project_root, diff_text=diff_text).run()

    assert state.output["cases"] == []
    assert state.output["fallbackCases"] == []
    assert state.output["summary"]["caseCount"] == 0
    assert state.processLogs[-1]["step"] == "build_cases"
    assert state.processLogs[-1]["status"] == "skipped"
    assert "cluster-analysis" in state.processLogs[-1]["message"]
