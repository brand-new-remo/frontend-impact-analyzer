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
