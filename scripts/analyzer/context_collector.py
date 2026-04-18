from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .common import normalize_path, rel_path, safe_read_text, uniq_keep_order


DOC_EXTS = {".md", ".txt", ".json", ".yaml", ".yml"}


class DocumentIndexer:
    def __init__(self, project_root: Path, config: Dict):
        self.project_root = project_root
        self.config = config

    def build(self) -> Dict:
        documents = []
        profile_file = self._path(self.config["paths"].get("projectProfileFile", ""))
        if profile_file.exists() and profile_file.is_file() and profile_file.suffix.lower() in DOC_EXTS:
            text = safe_read_text(profile_file)
            documents.append({
                "docId": self._doc_id("project-profile", profile_file),
                "kind": "project-profile",
                "path": rel_path(profile_file, self.project_root),
                "title": self._title(profile_file, text),
                "headings": self._headings(text),
                "keywords": self._keywords(profile_file, text),
                "charCount": len(text),
            })
        for kind, key in [
            ("repo-wiki", "repoWikiDir"),
            ("requirement", "requirementsDir"),
            ("spec", "specsDir"),
        ]:
            root = self._path(self.config["paths"].get(key, ""))
            if not root.exists() or not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in DOC_EXTS:
                    text = safe_read_text(path)
                    documents.append({
                        "docId": self._doc_id(kind, path),
                        "kind": kind,
                        "path": rel_path(path, self.project_root),
                        "title": self._title(path, text),
                        "headings": self._headings(text),
                        "keywords": self._keywords(path, text),
                        "charCount": len(text),
                    })
        return {
            "documentCount": len(documents),
            "documents": documents,
        }

    def retrieve(self, document_index: Dict, cluster: Dict, limit: int = 6) -> List[Dict]:
        keywords = self._cluster_keywords(cluster)
        scored = []
        for doc in document_index.get("documents", []):
            path = self.project_root / doc["path"]
            text = safe_read_text(path)
            snippets = self._snippets(text, keywords)
            matched = uniq_keep_order([kw for kw in keywords if kw and kw.lower() in (doc["path"] + " " + doc["title"] + " " + text[:12000]).lower()])
            score = len(matched) * 3 + len(snippets)
            if score <= 0:
                continue
            scored.append({
                "docId": doc["docId"],
                "kind": doc["kind"],
                "path": doc["path"],
                "title": doc["title"],
                "matchedKeywords": matched[:20],
                "candidateSnippets": snippets[:3],
                "score": score,
            })
        scored.sort(key=lambda item: (-item["score"], item["kind"], item["path"]))
        return scored[:limit]

    def _path(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else self.project_root / path

    def _doc_id(self, kind: str, path: Path) -> str:
        rel = rel_path(path, self.project_root)
        value = re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-").lower()
        return f"{kind}-{value}"

    def _title(self, path: Path, text: str) -> str:
        for line in text.splitlines():
            if line.strip().startswith("#"):
                return line.strip("# ").strip()
        return path.stem.replace("-", " ").replace("_", " ").title()

    def _headings(self, text: str) -> List[str]:
        headings = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped.strip("# ").strip())
        return headings[:30]

    def _keywords(self, path: Path, text: str) -> List[str]:
        tokens = []
        tokens.extend(_tokens(path.stem))
        tokens.extend(_tokens(text[:8000]))
        return uniq_keep_order(tokens)[:120]

    def _cluster_keywords(self, cluster: Dict) -> List[str]:
        parts: List[str] = []
        for file_path in cluster.get("changedFiles", []) + cluster.get("candidatePages", []):
            parts.extend(Path(file_path).parts)
            parts.append(Path(file_path).stem)
        parts.extend(cluster.get("changedSymbols", []))
        parts.extend(cluster.get("semanticTags", []))
        parts.extend(cluster.get("candidateRoutes", []))
        parts.append(cluster.get("title", ""))
        return uniq_keep_order([token for part in parts for token in _tokens(str(part)) if len(token) > 1])[:80]

    def _snippets(self, text: str, keywords: List[str]) -> List[Dict]:
        paragraphs = _paragraphs(text)
        hits = []
        for idx, paragraph in enumerate(paragraphs):
            lower = paragraph.lower()
            matched = [kw for kw in keywords if kw.lower() in lower]
            if not matched:
                continue
            hits.append({
                "index": idx,
                "matchedKeywords": uniq_keep_order(matched)[:12],
                "snippet": paragraph[:1200],
            })
        hits.sort(key=lambda item: -len(item["matchedKeywords"]))
        return hits


class ClusterContextCollector:
    def __init__(self, project_root: Path, config: Dict, imports: Dict[str, List[str]], reverse_imports: Dict[str, List[str]], ast_facts: Dict[str, Dict], document_index: Dict):
        self.project_root = project_root
        self.config = config
        self.imports = imports
        self.reverse_imports = reverse_imports
        self.ast_facts = ast_facts
        self.document_index = document_index
        self.doc_indexer = DocumentIndexer(project_root, config)

    def collect(self, cluster: Dict, diff_index: Dict) -> Dict:
        max_files = int(self.config["analysis"].get("maxFilesPerClusterContext", 8))
        max_doc_snippets = int(self.config["analysis"].get("maxDocumentSnippetsPerCluster", 6))
        files = self._context_files(cluster)[:max_files]
        diff_by_file = {item["path"]: item for item in diff_index.get("files", [])}
        code_evidence = [self._code_evidence(path, cluster, diff_by_file.get(path)) for path in files]
        document_candidates = self.doc_indexer.retrieve(self.document_index, cluster, max_doc_snippets)

        return {
            "clusterId": cluster["clusterId"],
            "clusterSummary": {
                "title": cluster.get("title", ""),
                "changedFiles": cluster.get("changedFiles", []),
                "changedSymbols": cluster.get("changedSymbols", []),
                "candidatePages": cluster.get("candidatePages", []),
                "candidateRoutes": cluster.get("candidateRoutes", []),
                "semanticTags": cluster.get("semanticTags", []),
                "confidence": cluster.get("confidence", "low"),
                "reason": cluster.get("reason", ""),
            },
            "diffEvidence": [diff_by_file[file_path] for file_path in cluster.get("changedFiles", []) if file_path in diff_by_file],
            "codeEvidence": code_evidence,
            "documentCandidates": document_candidates,
            "analysisPrompt": (
                "Analyze only this cluster. Determine the precise user-visible change, affected function units, "
                "evidence, confidence, uncertainties, and QA cases. Use documentCandidates when relevant; "
                "open original documents if snippets are insufficient. Do not broaden scope beyond evidence."
            ),
        }

    def _context_files(self, cluster: Dict) -> List[str]:
        files: List[str] = []
        files.extend(cluster.get("changedFiles", []))
        files.extend(cluster.get("candidatePages", []))
        for file_path in list(files):
            files.extend(self.imports.get(file_path, [])[:3])
            files.extend(self.reverse_imports.get(file_path, [])[:2])
        return uniq_keep_order(files)

    def _code_evidence(self, file_path: str, cluster: Dict, diff_item: Dict | None) -> Dict:
        path = self.project_root / file_path
        content = safe_read_text(path)
        snippet = self._focused_snippet(content, cluster)
        return {
            "file": normalize_path(file_path),
            "kind": self._evidence_kind(file_path, cluster),
            "whyIncluded": self._why_included(file_path, cluster),
            "symbols": self.ast_facts.get(file_path, {}).get("exports", []) + self.ast_facts.get(file_path, {}).get("component_names", []),
            "semanticTags": self.ast_facts.get(file_path, {}).get("semantic_tags", []),
            "diffPreview": (diff_item or {}).get("changedLinePreview", {}),
            "hunks": (diff_item or {}).get("hunks", []),
            "snippet": snippet,
        }

    def _focused_snippet(self, content: str, cluster: Dict) -> str:
        max_chars = int(self.config["analysis"].get("maxSnippetChars", 5000))
        if len(content) <= max_chars:
            return content

        keywords = uniq_keep_order(cluster.get("changedSymbols", []) + cluster.get("semanticTags", []))
        lines = content.splitlines()
        selected: List[str] = []
        hit_indexes = []
        for idx, line in enumerate(lines):
            if any(keyword and keyword in line for keyword in keywords):
                hit_indexes.append(idx)
        for idx in hit_indexes[:8]:
            start = max(0, idx - 8)
            end = min(len(lines), idx + 20)
            selected.append("\n".join(lines[start:end]))
        snippet = "\n\n...\n\n".join(selected) if selected else content[:max_chars]
        return snippet[:max_chars]

    def _evidence_kind(self, file_path: str, cluster: Dict) -> str:
        if file_path in cluster.get("changedFiles", []):
            return "changed-file"
        if file_path in cluster.get("candidatePages", []):
            return "candidate-page"
        return "neighbor-dependency"

    def _why_included(self, file_path: str, cluster: Dict) -> str:
        if file_path in cluster.get("changedFiles", []):
            return "This file is directly changed in the diff for this cluster."
        if file_path in cluster.get("candidatePages", []):
            return "This page is a traced candidate impact page for changed files in this cluster."
        for seed in cluster.get("seeds", []):
            for trace in seed.get("traces", []):
                if file_path in trace:
                    return "This file appears in an import trace from a changed file to a candidate page."
        return "This file is a direct neighboring dependency of a changed file or candidate page."


def _tokens(text: str) -> List[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    ascii_tokens = re.findall(r"[A-Za-z0-9_]{2,}", spaced.lower())
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    return uniq_keep_order(ascii_tokens + cjk_tokens)


def _paragraphs(text: str) -> List[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if len(blocks) > 1:
        return blocks
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ["\n".join(lines[idx:idx + 8]) for idx in range(0, len(lines), 8)]
