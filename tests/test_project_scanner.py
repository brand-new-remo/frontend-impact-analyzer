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


def test_project_scanner_supports_tsconfig_extends_and_multi_target_aliases():
    project_root = Path(__file__).resolve().parents[1] / "fixtures" / "extends_app"

    imports, _, pages, routes, _, aliases, _ = ProjectScanner(project_root).scan()

    assert aliases["@shared/*"] == ["src/shared/*"]
    assert aliases["@views/*"] == ["src/does-not-exist/*", "src/pages/*"]
    assert "src/pages/account/AccountPage.tsx" in pages
    assert imports["src/routes/index.tsx"] == ["src/pages/account/AccountPage.tsx"]
    assert any(route.route_path == "/account" and route.linked_page == "src/pages/account/AccountPage.tsx" for route in routes)


def test_project_scanner_supports_multi_hop_barrels_and_recursive_nested_routes():
    project_root = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_app"

    _, _, pages, routes, _, _, barrel_files = ProjectScanner(project_root).scan()

    assert "src/pages/reports/ReportsPage.tsx" in pages
    assert "src/pages/admin/AdminHomePage.tsx" in pages
    assert "src/pages/admin/UserDetailPage.tsx" in pages
    assert "src/pages/admin/AdvancedSettingsPage.tsx" in pages

    assert "src/pages/index.ts" in barrel_files
    assert "src/pages/reports/index.ts" in barrel_files

    assert any(route.route_path == "/reports" and route.linked_page == "src/pages/reports/ReportsPage.tsx" for route in routes)
    assert any(route.route_path == "/admin" and route.linked_page == "src/pages/admin/AdminHomePage.tsx" for route in routes)
    assert any(route.route_path == "/admin/users" and route.linked_page is None for route in routes)
    assert any(route.route_path == "/admin/users/detail" and route.linked_page == "src/pages/admin/UserDetailPage.tsx" for route in routes)
    assert any(route.route_path == "/admin/settings/advanced" and route.linked_page == "src/pages/admin/AdvancedSettingsPage.tsx" for route in routes)
