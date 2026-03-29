from __future__ import annotations

from pathlib import Path

from analyzer.project_scanner import ProjectScanner


def test_project_scanner_resolves_aliases_routes_and_pages():
    project_root = Path(__file__).resolve().parents[1] / "fixtures" / "sample_app"

    imports, reverse_imports, pages, routes, ast_facts, aliases, barrel_files = ProjectScanner(project_root).scan()

    assert aliases["@/*"] == ["src/*"]
    assert "src/pages/users/UserListPage.tsx" in pages
    assert "src/pages/users/UserDetailPage.tsx" in pages
    assert imports["src/routes/index.tsx"] == [
        "src/pages/users/UserListPage.tsx",
        "src/pages/users/UserDetailPage.tsx",
    ]
    assert reverse_imports["src/components/shared/SearchForm.tsx"] == ["src/pages/users/UserListPage.tsx"]
    assert any(route.route_path == "/users" and route.linked_page == "src/pages/users/UserListPage.tsx" for route in routes)
    assert any(route.route_path == "/users/detail" for route in routes)
    assert ast_facts["src/components/shared/SearchForm.tsx"]["semantic_tags"] == ["button", "form", "disabled-state"]
    assert barrel_files == []
