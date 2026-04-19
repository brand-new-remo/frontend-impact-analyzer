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

    def _pick_parser(self, file_path: Path) -> Parser:
        return self.tsx_parser if file_path.suffix.lower() in {".tsx", ".jsx"} else self.ts_parser

    def parse_tree(self, file_path: Path, source: str):
        """Parse source and return (tree, source_bytes).  Reuse the tree for
        both ``parse_imports_only`` and ``parse_file_from_tree``."""
        parser = self._pick_parser(file_path)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree, source_bytes

    def parse_imports_only(self, file_path: Path, source_bytes: bytes, tree) -> FileAstFacts:
        """Lightweight scan: only extracts imports, exports, reexports and
        lazy_imports from top-level AST nodes.  ~5-10x faster than full walk."""
        facts = FileAstFacts(file=str(file_path).replace('\\', '/'))
        for child in tree.root_node.children:
            self._walk_top_level(child, source_bytes, facts)
        for attr in ["imports", "reexports", "exports", "lazy_imports"]:
            setattr(facts, attr, uniq_keep_order(getattr(facts, attr)))
        return facts

    def parse_file_from_tree(self, file_path: Path, source_bytes: bytes, tree) -> FileAstFacts:
        """Full AST walk using a pre-parsed tree (avoids re-parsing)."""
        facts = FileAstFacts(file=str(file_path).replace('\\', '/'))
        self._walk(tree.root_node, source_bytes, facts)
        for attr in [
            "imports", "reexports", "exports", "component_names", "hook_names", "jsx_tags",
            "jsx_props", "route_paths", "route_components", "lazy_imports", "api_calls", "semantic_tags"
        ]:
            setattr(facts, attr, uniq_keep_order(getattr(facts, attr)))
        facts.semantic_tags = uniq_keep_order(self._derive_semantic_tags(facts))
        return facts

    def parse_file(self, file_path: Path, source: str) -> FileAstFacts:
        tree, source_bytes = self.parse_tree(file_path, source)
        return self.parse_file_from_tree(file_path, source_bytes, tree)

    def _text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

    def _walk_top_level(self, node, source: bytes, facts: FileAstFacts):
        """Extract only import/export/reexport/lazy from a single top-level node."""
        node_type = node.type
        txt = self._text(node, source)

        if node_type == "import_statement":
            m = re.search(r"""['\"]([^'\"]+)['\"]""", txt)
            if m:
                source_name = m.group(1)
                facts.imports.append(source_name)
                facts.import_bindings.extend(self._parse_import_bindings(txt, source_name))

        if node_type in {"export_statement", "export_clause"}:
            facts.exports.extend(self._parse_export_names(txt))
            if "from" in txt:
                m = re.search(r"""from\s+['\"]([^'\"]+)['\"]""", txt)
                if m:
                    source_name = m.group(1)
                    facts.reexports.append(source_name)
                    facts.reexport_bindings.extend(self._parse_reexport_bindings(txt, source_name))

        # Catch top-level lazy() declarations
        if node_type in {"lexical_declaration", "variable_declaration", "export_statement"}:
            lazy_match = re.search(r"lazy\s*\(\s*\(\)\s*=>\s*import\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\)", txt)
            if lazy_match:
                facts.lazy_imports.append(lazy_match.group(1))

    def _walk(self, node, source: bytes, facts: FileAstFacts):
        node_type = node.type
        txt = self._text(node, source)

        if node_type == "import_statement":
            m = re.search(r"""['\"]([^'\"]+)['\"]""", txt)
            if m:
                source_name = m.group(1)
                facts.imports.append(source_name)
                facts.import_bindings.extend(self._parse_import_bindings(txt, source_name))

        if node_type in {"export_statement", "export_clause"}:
            facts.exports.extend(self._parse_export_names(txt))
            if "from" in txt:
                m = re.search(r"""from\s+['\"]([^'\"]+)['\"]""", txt)
                if m:
                    source_name = m.group(1)
                    facts.reexports.append(source_name)
                    facts.reexport_bindings.extend(self._parse_reexport_bindings(txt, source_name))

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

        if node_type in {"identifier", "jsx_identifier"}:
            name = txt.strip()
            if name:
                facts.identifier_counts[name] = facts.identifier_counts.get(name, 0) + 1

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

    def _parse_import_bindings(self, statement_text: str, source_name: str):
        bindings = []
        import_body = statement_text.split("from", 1)[0].replace("import", "", 1).strip()
        if not import_body:
            return bindings

        named_match = re.search(r"\{([^}]*)\}", import_body)
        named_body = named_match.group(1) if named_match else ""
        body_without_named = re.sub(r"\{[^}]*\}", "", import_body).strip().strip(",")

        if body_without_named:
            if body_without_named.startswith("* as "):
                bindings.append({
                    "source": source_name,
                    "kind": "namespace",
                    "imported": "*",
                    "local": body_without_named[len("* as "):].strip(),
                })
            else:
                default_local = body_without_named.split(",", 1)[0].strip()
                if default_local:
                    bindings.append({
                        "source": source_name,
                        "kind": "default",
                        "imported": "default",
                        "local": default_local,
                    })

        if named_body:
            for part in named_body.split(","):
                chunk = part.strip()
                if not chunk:
                    continue
                if " as " in chunk:
                    imported, local = [item.strip() for item in chunk.split(" as ", 1)]
                else:
                    imported = local = chunk
                bindings.append({
                    "source": source_name,
                    "kind": "named",
                    "imported": imported,
                    "local": local,
                })
        return bindings

    def _parse_reexport_bindings(self, statement_text: str, source_name: str):
        bindings = []
        if "export * from" in statement_text:
            bindings.append({
                "source": source_name,
                "kind": "wildcard",
                "imported": "*",
                "exported": "*",
            })
            return bindings

        named_match = re.search(r"\{([^}]*)\}", statement_text)
        if not named_match:
            return bindings

        for part in named_match.group(1).split(","):
            chunk = part.strip()
            if not chunk:
                continue
            if " as " in chunk:
                imported, exported = [item.strip() for item in chunk.split(" as ", 1)]
            else:
                imported = exported = chunk
            bindings.append({
                "source": source_name,
                "kind": "named",
                "imported": imported,
                "exported": exported,
            })
        return bindings

    def _parse_export_names(self, statement_text: str):
        names = []

        named_match = re.search(r"export\s*\{([^}]*)\}", statement_text)
        if named_match:
            for part in named_match.group(1).split(","):
                chunk = part.strip()
                if not chunk:
                    continue
                exported_name = chunk.split(" as ", 1)[-1].strip()
                names.append(exported_name)

        direct_match = re.search(r"\bexport\s+(?:const|let|var|function|class)\s+([A-Za-z_]\w*)", statement_text)
        if direct_match:
            names.append(direct_match.group(1))

        return names

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
