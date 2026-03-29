from __future__ import annotations

import re
from pathlib import Path

from tree_sitter import Language, Parser
from tree_sitter_typescript import language_tsx, language_typescript

from .common import API_NAMES, uniq_keep_order
from .models import FileAstFacts


class TsAstAnalyzer:
    def __init__(self):
        self.ts_parser = Parser(Language(language_typescript()))
        self.tsx_parser = Parser(Language(language_tsx()))

    def parse_file(self, file_path: Path, source: str) -> FileAstFacts:
        parser = self.tsx_parser if file_path.suffix.lower() in {".tsx", ".jsx"} else self.ts_parser
        tree = parser.parse(source.encode("utf-8"))
        facts = FileAstFacts(file=str(file_path).replace('\\', '/'))
        self._walk(tree.root_node, source, facts)
        for attr in [
            "imports", "reexports", "exports", "component_names", "hook_names", "jsx_tags",
            "jsx_props", "route_paths", "route_components", "lazy_imports", "api_calls", "semantic_tags"
        ]:
            setattr(facts, attr, uniq_keep_order(getattr(facts, attr)))
        facts.semantic_tags = uniq_keep_order(self._derive_semantic_tags(facts))
        return facts

    def _text(self, node, source: str) -> str:
        return source[node.start_byte:node.end_byte]

    def _walk(self, node, source: str, facts: FileAstFacts):
        node_type = node.type
        txt = self._text(node, source)

        if node_type == "import_statement":
            m = re.search(r"""['\"]([^'\"]+)['\"]""", txt)
            if m:
                facts.imports.append(m.group(1))

        if node_type in {"export_statement", "export_clause"}:
            for name in re.findall(r"\b([A-Za-z_]\w*)\b", txt):
                if name not in {"export", "default", "from", "as", "const", "function", "class"}:
                    facts.exports.append(name)
            if "from" in txt:
                m = re.search(r"""from\s+['\"]([^'\"]+)['\"]""", txt)
                if m:
                    facts.reexports.append(m.group(1))

        if node_type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = self._text(name_node, source)
                if name.startswith("use"):
                    facts.hook_names.append(name)
                elif name[:1].isupper():
                    facts.component_names.append(name)
                else:
                    facts.exports.append(name)

        if node_type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = self._text(name_node, source)
                if name.startswith("use"):
                    facts.hook_names.append(name)
                elif name[:1].isupper():
                    facts.component_names.append(name)

        if node_type in {"jsx_opening_element", "jsx_self_closing_element"}:
            tag_node = node.child_by_field_name("name")
            if tag_node:
                facts.jsx_tags.append(self._text(tag_node, source))
            for child in node.children:
                if child.type in {"jsx_attribute", "property_identifier"}:
                    facts.jsx_props.append(self._text(child, source))

        if node_type == "pair":
            key_node = node.child_by_field_name("key")
            value_node = node.child_by_field_name("value")
            if key_node and value_node:
                key_text = self._text(key_node, source).strip()
                val_text = self._text(value_node, source).strip()
                if key_text in {"path", '"path"', "'path'"}:
                    facts.route_paths.append(val_text.strip('"').strip("'"))
                if key_text in {"element", '"element"', "'element'"}:
                    m = re.search(r"<([A-Z]\w*)", val_text)
                    if m:
                        facts.route_components.append(m.group(1))
                if key_text in {"component", '"component"', "'component'"}:
                    m = re.search(r"\b([A-Z]\w*)\b", val_text)
                    if m:
                        facts.route_components.append(m.group(1))

        if node_type == "call_expression":
            lazy_match = re.search(r"lazy\s*\(\s*\(\)\s*=>\s*import\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\)", txt)
            if lazy_match:
                facts.lazy_imports.append(lazy_match.group(1))
            callee_match = re.search(r"\b([A-Za-z_]\w*)\s*\(", txt)
            if callee_match and callee_match.group(1) in API_NAMES:
                facts.api_calls.append(txt[:180])

        for child in node.children:
            self._walk(child, source, facts)

    def _derive_semantic_tags(self, facts: FileAstFacts):
        tags = []
        jsx_tags = set(facts.jsx_tags)
        props = " ".join(facts.jsx_props)
        calls = " ".join(facts.api_calls).lower()
        if "Button" in jsx_tags or "onClick" in props:
            tags.append("button")
        if any(x in jsx_tags for x in {"Modal", "Drawer", "Dialog"}) or re.search(r"\bonOk\b|\bonCancel\b|\bopen\b|\bvisible\b", props):
            tags.append("modal")
        if "Form" in jsx_tags or re.search(r"\bonSubmit\b|\brules\b|\bname\b", props):
            tags.append("form")
        if "Table" in jsx_tags or re.search(r"\bcolumns\b|\browSelection\b|\bpagination\b|\bsorter\b|\bfilters\b", props):
            tags.append("table")
        if "Upload" in jsx_tags:
            tags.append("upload")
        if re.search(r"\bdisabled\b|\breadOnly\b", props):
            tags.append("disabled-state")
        if facts.route_paths or facts.route_components or facts.lazy_imports:
            tags.append("route")
        if calls:
            tags.append("api")
            if any(x in calls for x in ["get(", "fetch(", "query", "list"]):
                tags.append("list-query")
            if any(x in calls for x in ["post(", "put(", "patch(", "submit", "save"]):
                tags.append("submit")
            if any(x in calls for x in ["delete(", "remove"]):
                tags.append("delete")
            if any(x in calls for x in ["detail", "getbyid", "info"]):
                tags.append("detail")
        if facts.hook_names:
            tags.append("state")
        return tags
