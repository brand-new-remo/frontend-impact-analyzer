from __future__ import annotations

from analyzer.case_builder import TestCaseBuilder
from analyzer.models import PageImpact


def test_case_builder_returns_sorted_case_array_shape():
    impact = PageImpact(
        changed_file="src/components/shared/SearchForm.tsx",
        page_file="src/pages/users/UserListPage.tsx",
        route_path="/users",
        module_name="users",
        trace=["src/components/shared/SearchForm.tsx", "src/pages/users/UserListPage.tsx"],
        impact_type="indirect",
        confidence="medium",
        impact_reason="shared-component changed, traced to page through 2 hop(s), semantics: button, form",
        semantic_tags=["button", "form", "disabled-state"],
    )

    cases = TestCaseBuilder().build([impact])
    output = [case.to_output_dict() for case in cases]

    assert [item["用例名称"] for item in output] == [
        "User List Page 页面基础回归",
        "User List Page 表单展示校验与提交流程验证",
        "User List Page 按钮入口与点击行为验证",
        "User List Page 禁用态与只读态验证",
    ]
    assert output[0]["页面名"] == "User List Page"
    assert output[0]["用例等级"] == "medium"
    assert output[0]["用例可置信度"] == "medium"
    assert "shared-component changed" in output[0]["来源描述"]
    assert "变更文件: src/components/shared/SearchForm.tsx" in output[0]["来源描述"]


def test_case_builder_adds_specific_api_field_level_cases():
    impact = PageImpact(
        changed_file="src/services/orderApi.ts",
        page_file="src/pages/orders/OrderListPage.tsx",
        route_path="/orders",
        module_name="orders",
        trace=["src/services/orderApi.ts", "src/pages/orders/OrderListPage.tsx"],
        impact_type="direct",
        confidence="high",
        impact_reason="api changed, traced to page through 2 hop(s), semantics: api, list-query, detail, validation, submit",
        semantic_tags=["api", "list-query", "detail", "validation", "submit"],
        api_changes=[
            {"kind": "request-field-change", "change": "added", "field": "pageSize"},
            {"kind": "response-field-change", "change": "added", "field": "detailTitle"},
            {"kind": "enum-change", "change": "added", "field": "ACTIVE"},
            {"kind": "pagination-shape-change", "change": "added", "field": "pageSize"},
            {"kind": "detail-schema-change", "change": "added", "field": "detailTitle"},
            {"kind": "list-schema-change", "change": "added", "field": "itemTitle"},
        ],
    )

    cases = [case.to_output_dict() for case in TestCaseBuilder().build([impact])]
    case_names = [item["用例名称"] for item in cases]

    assert "Order List Page 接口请求字段变更验证" in case_names
    assert "Order List Page 接口响应字段映射验证" in case_names
    assert "Order List Page 枚举值与状态映射验证" in case_names
    assert "Order List Page 分页参数结构验证" in case_names
    assert "Order List Page 详情接口字段结构验证" in case_names
    assert "Order List Page 列表接口字段结构验证" in case_names
