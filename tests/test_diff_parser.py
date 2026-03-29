from __future__ import annotations

from analyzer.diff_parser import GitDiffParser


def test_diff_parser_extracts_changed_files_symbols_and_semantics():
    diff_text = """
feat(users): adjust search form

diff --git a/src/components/shared/SearchForm.tsx b/src/components/shared/SearchForm.tsx
index 1234567..89abcde 100644
--- a/src/components/shared/SearchForm.tsx
+++ b/src/components/shared/SearchForm.tsx
@@ -1,3 +1,5 @@
+const handleSubmit = () => {}
+<Form onSubmit={handleSubmit}>
+  <Button disabled onClick={handleSubmit}>Search</Button>
 """

    commit_types, changed_files = GitDiffParser(diff_text).parse()

    assert commit_types == ["feat"]
    assert len(changed_files) == 1

    changed_file = changed_files[0]
    assert changed_file.path == "src/components/shared/SearchForm.tsx"
    assert changed_file.added_lines == 3
    assert changed_file.removed_lines == 0
    assert changed_file.symbols == ["handleSubmit", "Form", "Button"]
    assert changed_file.semantic_tags == ["submit", "form", "button", "list-query", "disabled-state"]


def test_diff_parser_marks_format_only_changes():
    diff_text = """
style(formatters): reformat formatter

diff --git a/src/utils/formatters.ts b/src/utils/formatters.ts
index 1234567..89abcde 100644
--- a/src/utils/formatters.ts
+++ b/src/utils/formatters.ts
@@ -1,1 +1,1 @@
-export function formatDate(value: string) { return value; }
+export function formatDate( value: string ){return value}
"""

    _, changed_files = GitDiffParser(diff_text).parse()

    assert len(changed_files) == 1
    assert changed_files[0].is_format_only is True
    assert changed_files[0].symbols == []
    assert changed_files[0].semantic_tags == []


def test_diff_parser_detects_api_field_level_changes():
    diff_text = """
feat(api): adjust list and detail contracts

diff --git a/src/services/orderApi.ts b/src/services/orderApi.ts
index 1234567..89abcde 100644
--- a/src/services/orderApi.ts
+++ b/src/services/orderApi.ts
@@ -1,8 +1,10 @@
-  params: { pageNum, status }
+  params: { pageSize, statusCode }
-  response: { data: { detailName } }
+  response: { data: { detailTitle } }
-  list: { columns: itemName }
+  list: { columns: itemTitle }
-  enum status: ["ENABLED", "DISABLED"]
+  enum status: ["ACTIVE", "DISABLED"]
"""

    _, changed_files = GitDiffParser(diff_text).parse()

    assert len(changed_files) == 1
    changed_file = changed_files[0]
    assert changed_file.is_format_only is False
    assert {"api", "list-query", "detail", "validation", "submit"} <= set(changed_file.semantic_tags)
    assert {"kind": "response-field-change", "change": "rename", "field": "detailTitle", "from": "detailName"} in changed_file.api_changes
    assert {"kind": "request-field-change", "change": "added", "field": "pageSize"} in changed_file.api_changes
    assert {"kind": "request-field-change", "change": "removed", "field": "pageNum"} in changed_file.api_changes
    assert {"kind": "pagination-shape-change", "change": "added", "field": "pageSize"} in changed_file.api_changes
    assert {"kind": "detail-schema-change", "change": "added", "field": "detailTitle"} in changed_file.api_changes
    assert {"kind": "list-schema-change", "change": "added", "field": "itemTitle"} in changed_file.api_changes
    assert {"kind": "enum-change", "change": "added", "field": "ACTIVE"} in changed_file.api_changes
