from __future__ import annotations

from pathlib import Path

from analyzer.ast_analyzer import TsAstAnalyzer


def test_ast_analyzer_extracts_routes_imports_and_semantics():
    source = """
import UserListPage from "@/pages/users/UserListPage";
import { lazy } from "react";

const LazyDetailPage = lazy(() => import("@/pages/users/UserDetailPage"));

export const routes = [
  {
    path: "/users",
    element: <UserListPage />,
    children: [{ path: "detail", element: <LazyDetailPage /> }],
  },
];
"""

    facts = TsAstAnalyzer().parse_file(Path("demo.tsx"), source)

    assert facts.imports == ["@/pages/users/UserListPage", "react"]
    assert facts.lazy_imports == ["@/pages/users/UserDetailPage"]
    assert facts.route_paths == ["/users", "detail"]
    assert facts.route_components == ["UserListPage", "LazyDetailPage"]
    assert facts.semantic_tags == ["route"]
    assert facts.import_bindings == [
        {"source": "@/pages/users/UserListPage", "kind": "default", "imported": "default", "local": "UserListPage"},
        {"source": "react", "kind": "named", "imported": "lazy", "local": "lazy"},
    ]
