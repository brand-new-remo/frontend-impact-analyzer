from __future__ import annotations

import re
from typing import List

from .common import confidence_to_priority, title_from_file, uniq_keep_order
from .models import PageImpact, TestCase


class TestCaseBuilder:
    def build(self, impacts: List[PageImpact]) -> List[TestCase]:
        cases: List[TestCase] = []
        for impact in impacts:
            cases.extend(self._build_cases_for_impact(impact))
        return self._dedupe(cases)

    def _build_cases_for_impact(self, impact: PageImpact) -> List[TestCase]:
        semantics = set(impact.semantic_tags)
        page_name = title_from_file(impact.page_file)
        groups = [self._base_case(impact, page_name)]
        operations = self._infer_operations(impact, page_name)
        mapping = [
            ("button", self._button_case),
            ("modal", self._modal_case),
            ("form", self._form_case),
            ("validation", self._form_case),
            ("table", self._table_case),
            ("columns", self._table_case),
            ("api", self._api_case),
            ("list-query", self._query_case),
            ("detail", self._detail_case),
            ("delete", self._delete_case),
            ("permission", self._permission_case),
            ("navigation", self._navigation_case),
            ("upload", self._upload_case),
            ("disabled-state", self._disabled_case),
            ("route", self._navigation_case),
        ]
        for tag, builder in mapping:
            if tag in semantics:
                groups.append(builder(impact, page_name))
        api_kinds = {item["kind"] for item in impact.api_changes}
        api_mapping = [
            ("request-field-change", self._api_request_field_case),
            ("response-field-change", self._api_response_field_case),
            ("enum-change", self._enum_case),
            ("pagination-shape-change", self._pagination_shape_case),
            ("detail-schema-change", self._detail_schema_case),
            ("list-schema-change", self._list_schema_case),
        ]
        for kind, builder in api_mapping:
            if kind in api_kinds:
                groups.append(builder(impact, page_name))
        for operation in operations:
            groups.append(self._business_operation_case(impact, page_name, operation))
        if "permission" in semantics:
            for operation in operations or ["access"]:
                groups.append(self._role_variant_case(impact, page_name, operation))
        return groups

    def _mk(self, impact: PageImpact, page_name: str, case_name: str, steps, expected, sort_priority: int) -> TestCase:
        source_parts = [self._business_reason(impact)]
        if impact.route_path:
            source_parts.append(f"关联路由: {impact.route_path}")
        if impact.changed_file:
            source_parts.append(f"变更文件: {impact.changed_file}")
        return TestCase(
            page_name=page_name,
            case_name=case_name,
            test_steps=steps,
            expected_results=expected,
            case_level=confidence_to_priority(impact.confidence),
            confidence=impact.confidence,
            source_description="；".join(source_parts),
            sort_priority=sort_priority,
        )

    def _base_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 页面基础回归", [f"进入页面 {page_name}", "观察页面初始化渲染"], ["页面可正常加载", "页面无报错、无白屏、无异常提示"], 10)
    def _button_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 按钮入口与点击行为验证", [f"进入页面 {page_name}", "定位相关按钮", "点击按钮触发操作"], ["按钮展示符合预期", "按钮可点击性符合预期", "点击后行为符合需求"], 30)
    def _modal_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 弹窗打开关闭与提交验证", [f"进入页面 {page_name}", "触发弹窗打开", "执行确认与取消操作"], ["弹窗可正常打开", "弹窗内容展示正确", "确认与取消行为符合预期"], 25)
    def _form_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 表单展示校验与提交流程验证", [f"进入页面 {page_name}", "填写表单", "触发表单校验", "提交表单"], ["表单字段展示正确", "必填/格式校验符合预期", "提交成功或失败提示符合预期"], 20)
    def _table_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 列表列展示与表格交互验证", [f"进入页面 {page_name}", "检查列表列展示", "验证列表选择/操作列行为"], ["表格列展示正确", "操作列交互正常", "选择与点击行为符合预期"], 22)
    def _api_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 接口调用与页面反馈验证", [f"进入页面 {page_name}", "触发页面主要数据请求或提交请求", "观察页面反馈"], ["请求参数符合预期", "成功返回后的页面渲染正确", "异常返回时提示与容错符合预期"], 15)
    def _query_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 查询筛选分页排序验证", [f"进入页面 {page_name}", "执行查询/筛选/分页/排序操作"], ["查询条件生效", "分页行为正确", "筛选排序结果符合预期"], 18)
    def _detail_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 详情展示与回显验证", [f"进入页面 {page_name}", "进入详情或编辑态", "检查字段展示与回显"], ["详情展示正确", "编辑态回显正确", "字段映射符合预期"], 24)
    def _delete_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 删除流程与结果反馈验证", [f"进入页面 {page_name}", "触发删除操作", "确认删除"], ["删除确认交互正确", "删除成功后数据状态正确", "删除失败时提示正确"], 28)
    def _permission_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 权限可见性与可操作性验证", [f"分别使用不同权限账号进入页面 {page_name}", "检查页面入口、按钮、字段可见性与可操作性"], ["不同角色下页面可见性符合预期", "按钮与操作权限符合预期"], 12)
    def _navigation_case(self, impact, page_name):
        desc = f" 路由 {impact.route_path}" if impact.route_path else ""
        return self._mk(impact, page_name, f"{page_name}{desc} 进入跳转与返回验证", [f"进入页面 {page_name}", "执行页面跳转", "刷新页面并执行返回"], ["页面入口可正常访问", "跳转链路正确", "刷新与返回行为符合预期"], 14)
    def _upload_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 上传流程验证", [f"进入页面 {page_name}", "执行文件上传"], ["上传前校验正确", "上传成功与失败反馈正确"], 26)
    def _disabled_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 禁用态与只读态验证", [f"进入页面 {page_name}", "观察控件禁用态或只读态", "尝试触发操作"], ["禁用态展示正确", "不可操作时拦截正确", "可操作条件下行为恢复正常"], 32)
    def _api_request_field_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 接口请求字段变更验证", [f"进入页面 {page_name}", "触发请求或提交流程", "检查请求字段和参数结构"], ["新增/删除/重命名的请求字段符合预期", "请求参数结构与后端约定一致"], 13)
    def _api_response_field_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 接口响应字段映射验证", [f"进入页面 {page_name}", "触发数据加载", "检查页面字段展示和映射结果"], ["响应字段变化后页面展示正确", "缺失或新增字段时页面容错符合预期"], 16)
    def _enum_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 枚举值与状态映射验证", [f"进入页面 {page_name}", "触发包含状态/类型枚举的操作或展示", "检查枚举值对应文案、状态和交互"], ["新增/删除/调整的枚举值映射正确", "异常或未知枚举值处理符合预期"], 19)
    def _pagination_shape_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 分页参数结构验证", [f"进入页面 {page_name}", "执行分页或翻页操作", "检查请求参数与返回结果"], ["分页参数名和结构正确", "分页结果、总数和翻页行为符合预期"], 17)
    def _detail_schema_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 详情接口字段结构验证", [f"进入页面 {page_name}", "进入详情或编辑态", "检查详情字段展示与回显"], ["详情接口字段变化后页面展示正确", "字段缺失、重命名或新增时回显符合预期"], 21)
    def _list_schema_case(self, impact, page_name):
        return self._mk(impact, page_name, f"{page_name} 列表接口字段结构验证", [f"进入页面 {page_name}", "触发列表加载", "检查列表项、列和筛选结果"], ["列表接口字段变化后展示正确", "新增/删除字段对列表和筛选无异常影响"], 23)

    def _business_operation_case(self, impact, page_name, operation: str):
        if operation == "list":
            return self._mk(impact, page_name, f"{page_name} 列表浏览与关键操作验证", [f"进入页面 {page_name}", "执行列表加载、筛选和主要行操作"], ["列表加载正确", "关键操作入口可用", "列表主流程符合预期"], 11)
        if operation == "detail":
            return self._mk(impact, page_name, f"{page_name} 详情查看主流程验证", [f"进入页面 {page_name}", "进入详情场景并检查关键信息"], ["详情主信息展示正确", "详情相关交互和回显符合预期"], 12)
        if operation == "create":
            return self._mk(impact, page_name, f"{page_name} 新增主流程验证", [f"进入页面 {page_name}", "触发新增入口", "填写必要信息并提交"], ["新增入口可用", "新增提交成功或失败反馈正确", "新增结果在页面中可见"], 13)
        if operation == "edit":
            return self._mk(impact, page_name, f"{page_name} 编辑主流程验证", [f"进入页面 {page_name}", "进入编辑场景", "修改数据并提交"], ["编辑前回显正确", "编辑提交反馈正确", "编辑后的结果展示正确"], 14)
        if operation == "delete":
            return self._mk(impact, page_name, f"{page_name} 删除主流程验证", [f"进入页面 {page_name}", "选择目标数据并执行删除"], ["删除确认流程正确", "删除结果反馈正确", "删除后的数据状态正确"], 15)
        return self._mk(impact, page_name, f"{page_name} 业务主流程验证", [f"进入页面 {page_name}", "执行业务主路径"], ["业务主路径可正常完成"], 18)

    def _role_variant_case(self, impact, page_name, operation: str):
        label = {
            "list": "列表查看",
            "detail": "详情查看",
            "create": "新增",
            "edit": "编辑",
            "delete": "删除",
            "access": "访问",
        }.get(operation, "业务操作")
        return self._mk(
            impact,
            page_name,
            f"{page_name} {label}的角色权限差异验证",
            [f"分别使用不同角色账号进入页面 {page_name}", f"验证{label}入口、按钮和提交能力"],
            [f"不同角色下{label}权限符合预期", "越权场景被正确拦截"],
            16,
        )

    def _infer_operations(self, impact: PageImpact, page_name: str) -> List[str]:
        semantics = set(impact.semantic_tags)
        text = " ".join([
            page_name.lower(),
            impact.page_file.lower(),
            (impact.route_path or "").lower(),
            impact.changed_file.lower(),
        ])
        operations: List[str] = []
        if "table" in semantics or "list-query" in semantics or re.search(r"\blist\b|\bindex\b|\btable\b", text):
            operations.append("list")
        if "detail" in semantics or re.search(r"\bdetail\b|\bview\b|\binfo\b", text):
            operations.append("detail")
        if re.search(r"\bcreate\b|\bnew\b|\badd\b", text):
            operations.append("create")
        if re.search(r"\bedit\b|\bupdate\b", text):
            operations.append("edit")
        if "delete" in semantics or re.search(r"\bdelete\b|\bremove\b", text):
            operations.append("delete")
        if "form" in semantics and "submit" in semantics and ("detail" in semantics or re.search(r"\bdetail\b|\bedit\b|\bupdate\b", text)) and not any(op in operations for op in {"create", "edit"}):
            operations.append("edit")
        return uniq_keep_order(operations)

    def _business_reason(self, impact: PageImpact) -> str:
        parts = [impact.impact_reason]
        operations = self._infer_operations(impact, title_from_file(impact.page_file))
        if operations:
            op_labels = {
                "list": "列表",
                "detail": "详情",
                "create": "新增",
                "edit": "编辑",
                "delete": "删除",
            }
            parts.append("业务动作: " + "/".join(op_labels.get(item, item) for item in operations))
        if impact.matched_symbols:
            parts.append("命中符号: " + ", ".join(impact.matched_symbols))
        if impact.api_changes:
            change_labels = uniq_keep_order([self._api_change_label(item["kind"]) for item in impact.api_changes])
            parts.append("接口风险: " + "、".join(change_labels))
        if impact.module_name and impact.module_name != "unknown":
            parts.append(f"模块: {impact.module_name}")
        return "；".join(parts)

    def _api_change_label(self, kind: str) -> str:
        mapping = {
            "request-field-change": "请求字段",
            "response-field-change": "响应字段",
            "enum-change": "枚举值",
            "pagination-shape-change": "分页参数",
            "detail-schema-change": "详情结构",
            "list-schema-change": "列表结构",
        }
        return mapping.get(kind, kind)

    def _dedupe(self, cases: List[TestCase]) -> List[TestCase]:
        out: List[TestCase] = []
        seen = set()
        for c in cases:
            key = (c.page_name, c.case_name)
            if key not in seen:
                seen.add(key)
                out.append(c)
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            out,
            key=lambda c: (
                c.page_name,
                c.sort_priority,
                priority_rank.get(c.case_level, 99),
                priority_rank.get(c.confidence, 99),
                c.case_name,
            ),
        )
