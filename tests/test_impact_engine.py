from __future__ import annotations

from pathlib import Path

from analyzer.diff_parser import GitDiffParser
from analyzer.impact_engine import ImpactAnalyzer
from analyzer.project_scanner import ProjectScanner
from analyzer.source_classifier import SourceClassifier


def test_impact_engine_traces_shared_component_to_page():
    project_root = Path(__file__).resolve().parents[1] / "fixtures" / "sample_app"
    diff_text = (Path(__file__).resolve().parents[1] / "fixtures" / "diffs" / "shared_search_form.diff").read_text(encoding="utf-8")

    _, changed_files = GitDiffParser(diff_text).parse()
    changed_file = changed_files[0]

    classifier = SourceClassifier()
    changed_file.file_type = classifier.classify(changed_file.path)
    changed_file.module_guess = classifier.guess_module(changed_file.path)

    imports, reverse_imports, pages, routes, ast_facts, _, _, _, _ = ProjectScanner(project_root).scan()
    analyzer = ImpactAnalyzer(imports=imports, reverse_imports=reverse_imports, pages=pages, routes=routes, ast_facts=ast_facts)

    impacts, unresolved = analyzer.analyze_file(changed_file)

    assert unresolved is None
    assert len(impacts) == 1
    impact = impacts[0]
    assert impact.page_file == "src/pages/users/UserListPage.tsx"
    assert impact.route_path == "/users"
    assert impact.impact_type == "indirect"
    assert impact.confidence == "medium"
    assert impact.trace == [
        "src/components/shared/SearchForm.tsx",
        "src/pages/users/UserListPage.tsx",
    ]
    assert impact.semantic_tags == ["submit", "form", "button", "disabled-state"]
