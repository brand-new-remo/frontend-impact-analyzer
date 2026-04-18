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
    assert changed_files[0].noise_classification["kind"] == "format-only"
    assert changed_files[0].noise_classification["shouldAnalyze"] is False


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


def test_diff_parser_classifies_comment_and_import_only_noise():
    diff_text = """
chore: comments and imports

diff --git a/src/pages/users/UserListPage.tsx b/src/pages/users/UserListPage.tsx
index 1234567..89abcde 100644
--- a/src/pages/users/UserListPage.tsx
+++ b/src/pages/users/UserListPage.tsx
@@ -1,2 +1,2 @@
-// old note
+// new note
diff --git a/src/pages/users/UserDetailPage.tsx b/src/pages/users/UserDetailPage.tsx
index 1234567..89abcde 100644
--- a/src/pages/users/UserDetailPage.tsx
+++ b/src/pages/users/UserDetailPage.tsx
@@ -1,2 +1,2 @@
-import { B, A } from './x'
+import { A, B } from './x'
"""

    _, changed_files = GitDiffParser(diff_text).parse()

    by_path = {item.path: item for item in changed_files}
    assert by_path["src/pages/users/UserListPage.tsx"].noise_classification["kind"] == "comment-only"
    assert by_path["src/pages/users/UserListPage.tsx"].noise_classification["shouldAnalyze"] is False
    assert by_path["src/pages/users/UserDetailPage.tsx"].noise_classification["kind"] == "import-only"
    assert by_path["src/pages/users/UserDetailPage.tsx"].noise_classification["shouldAnalyze"] is False


def test_diff_parser_classifies_test_generated_and_lockfile_noise():
    diff_text = """
chore: generated noise

diff --git a/src/__tests__/UserList.test.tsx b/src/__tests__/UserList.test.tsx
index 1234567..89abcde 100644
--- a/src/__tests__/UserList.test.tsx
+++ b/src/__tests__/UserList.test.tsx
@@ -1,1 +1,1 @@
-expect(a).toBe(1)
+expect(a).toBe(2)
diff --git a/src/generated/client.ts b/src/generated/client.ts
index 1234567..89abcde 100644
--- a/src/generated/client.ts
+++ b/src/generated/client.ts
@@ -1,1 +1,1 @@
-export const version = '1'
+export const version = '2'
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
index 1234567..89abcde 100644
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -1,1 +1,1 @@
-foo: 1
+foo: 2
"""

    _, changed_files = GitDiffParser(diff_text).parse()

    by_path = {item.path: item for item in changed_files}
    assert by_path["src/__tests__/UserList.test.tsx"].noise_classification["kind"] == "test-only"
    assert by_path["src/__tests__/UserList.test.tsx"].noise_classification["shouldAnalyze"] is False
    assert by_path["src/generated/client.ts"].noise_classification["kind"] == "generated-file"
    assert by_path["src/generated/client.ts"].noise_classification["shouldAnalyze"] is False
    assert by_path["pnpm-lock.yaml"].noise_classification["kind"] == "lockfile"
    assert by_path["pnpm-lock.yaml"].noise_classification["shouldAnalyze"] is False
