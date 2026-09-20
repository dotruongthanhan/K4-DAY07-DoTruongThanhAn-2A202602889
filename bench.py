#!/usr/bin/env python3
"""
bench.py - Benchmark evaluation script for Lab 07 (K4-L3B)

Workflow:
1. Load 5 benchmark queries from benchmark_queries.yaml.
2. Ingest all .md files in data/ecommerce/, parsing frontmatter metadata.
3. Chunk content using the chosen strategy (fixed, sentence, recursive, heading).
4. Store chunks into EmbeddingStore (each chunk is a Document with doc_id & full metadata).
5. Run benchmark queries, performing A/B test (with vs without filter) when applicable.
6. Evaluate at 2 levels:
   - Document level (Is gold_doc_id in top-3?)
   - Content level (Does retrieved context contain gold_contains?)
7. Output detailed results and save to ket_qua_benchmark.txt.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.agent import KnowledgeBaseAgent
from src.chunking import FixedSizeChunker, RecursiveChunker, SentenceChunker
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)
from src.models import Document
from src.store import EmbeddingStore


class HeadingChunker:
    """Custom chunker splitting text by markdown headings (H1-H3), falling back to recursive for large sections."""

    def __init__(self, chunk_size: int = 400) -> None:
        self.chunk_size = chunk_size
        self._fallback = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        sections = re.split(r"(?m)(?=^#{1,3}\s+)", text.strip())
        chunks: list[str] = []
        for sec in sections:
            sec = sec.strip()
            if not sec:
                continue
            if len(sec) <= self.chunk_size:
                chunks.append(sec)
            else:
                chunks.extend(self._fallback.chunk(sec))
        return chunks


def load_yaml_queries(file_path: Path) -> list[dict[str, Any]]:
    """Simple parser for benchmark_queries.yaml without requiring PyYAML."""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    queries = []
    current_q: dict[str, Any] | None = None
    in_filter = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- id:"):
            if current_q:
                queries.append(current_q)
            current_q = {"id": stripped.split(":", 1)[1].strip()}
            in_filter = False
        elif current_q is not None:
            if stripped.startswith("metadata_filter:"):
                in_filter = True
                current_q["metadata_filter"] = {}
            elif in_filter and line.startswith("      "):
                k, v = stripped.split(":", 1)
                current_q["metadata_filter"][k.strip()] = v.strip().strip("\"'")
            else:
                in_filter = False
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    val = v.strip().strip("\"'")
                    if val.lower() == "true":
                        val_parsed: Any = True
                    elif val.lower() == "false":
                        val_parsed = False
                    else:
                        val_parsed = val
                    current_q[k.strip()] = val_parsed

    if current_q:
        queries.append(current_q)

    return queries


def load_corpus(data_dir: Path, chunker: Any) -> list[Document]:
    """Load all markdown files, parse frontmatter, and create chunked Document objects."""
    chunk_docs: list[Document] = []

    for file_path in sorted(data_dir.glob("*.md")):
        text = file_path.read_text(encoding="utf-8")
        parts = text.split("---")
        if len(parts) >= 3:
            fm_text = parts[1]
            body = "---".join(parts[2:]).strip()
            fm: dict[str, Any] = {}
            for line in fm_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.split("#")[0].strip().strip("\"'")
        else:
            fm = {}
            body = text.strip()

        doc_stem = file_path.stem
        fm["doc_id"] = doc_stem
        fm["source_file"] = file_path.name

        chunks = chunker.chunk(body)
        for i, ch in enumerate(chunks):
            chunk_doc = Document(
                id=f"{doc_stem}#{i}",
                content=ch,
                metadata={**fm, "chunk_index": i},
            )
            chunk_docs.append(chunk_doc)

    return chunk_docs


def get_embedder() -> tuple[Any, str]:
    """Initialize embedder according to .env settings with graceful fallback."""
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "mock").strip().lower()

    if provider == "gemini":
        try:
            return GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL)), "gemini"
        except Exception as e:
            print(f"[Warning] Failed to initialize Gemini embedder: {e}. Falling back to mock.")
    elif provider == "openai":
        try:
            return OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL)), "openai"
        except Exception as e:
            print(f"[Warning] Failed to initialize OpenAI embedder: {e}. Falling back to mock.")
    elif provider == "local":
        try:
            return LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL)), "local"
        except Exception as e:
            print(f"[Warning] Failed to initialize Local embedder: {e}. Falling back to mock.")

    return _mock_embed, "mock"


def run_benchmark(strategy: str = "recursive", data_dir_str: str = "data/ecommerce") -> str:
    data_dir = Path(data_dir_str)
    yaml_path = Path("benchmark_queries.yaml")
    if not yaml_path.exists():
        yaml_path = data_dir / "benchmark_queries.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(f"Cannot find benchmark_queries.yaml in . or {data_dir}")

    # Choose chunker
    strat_lower = strategy.lower()
    if strat_lower == "fixed":
        chunker = FixedSizeChunker(chunk_size=300, overlap=50)
        chunker_name = "FixedSizeChunker(size=300, overlap=50)"
    elif strat_lower == "sentence":
        chunker = SentenceChunker(max_sentences_per_chunk=3)
        chunker_name = "SentenceChunker(max_sentences=3)"
    elif strat_lower == "heading":
        chunker = HeadingChunker(chunk_size=400)
        chunker_name = "CustomHeadingChunker(size=400)"
    else:
        chunker = RecursiveChunker(chunk_size=300)
        chunker_name = "RecursiveChunker(size=300)"

    # Prepare store
    embedder, embedder_name = get_embedder()
    store = EmbeddingStore(collection_name="benchmark_store", embedding_fn=embedder)

    docs = load_corpus(data_dir, chunker)
    store.add_documents(docs)

    def simple_llm(prompt: str) -> str:
        # Simple extraction-based agent simulation
        for line in prompt.splitlines():
            if line.strip().startswith("[1]") or line.strip().startswith("[2]") or line.strip().startswith("[3]"):
                return line.strip()[:200]
        return "Trả lời dựa trên ngữ cảnh được cung cấp."

    agent = KnowledgeBaseAgent(store=store, llm_fn=simple_llm)

    queries = load_yaml_queries(yaml_path)

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"KẾT QUẢ ĐÁNH GIÁ BENCHMARK - LAB 07 (K4-L3B)")
    lines.append(f"Chiến lược Chunking: {chunker_name}")
    lines.append(f"Mô hình Embedding:   {embedder_name}")
    lines.append(f"Tổng số chunks nạp:  {len(docs)} chunks từ {len(list(data_dir.glob('*.md')))} tài liệu")
    lines.append("=" * 80)
    lines.append("")

    total_score = 0
    max_score = len(queries) * 2

    for idx, q in enumerate(queries, 1):
        qid = q.get("id", f"q{idx}")
        query_text = q.get("query", "")
        gold_answer = q.get("gold_answer", "")
        gold_doc_id = q.get("gold_doc_id", "")
        gold_contains = q.get("gold_contains", "")
        metadata_filter = q.get("metadata_filter")
        is_ab = q.get("ab_test", False)

        lines.append(f"--- Câu hỏi {qid} [{q.get('platform', '')}] ---")
        lines.append(f"Query:       {query_text}")
        lines.append(f"Gold Doc:    {gold_doc_id}")
        lines.append(f"Gold Answer: {gold_answer}")

        # If A/B test is required, run unfiltered first
        if is_ab and metadata_filter:
            unfiltered_res = store.search(query_text, top_k=3)
            lines.append("  [A/B Test - Lần 1: KHÔNG DÙNG FILTER]")
            for rank, r in enumerate(unfiltered_res, 1):
                m_doc = r.get("metadata", {}).get("doc_id", "N/A")
                m_aud = r.get("metadata", {}).get("audience", "N/A")
                score = r.get("score", 0.0)
                lines.append(f"    Top-{rank}: score={score:.4f} | doc={m_doc} | audience={m_aud}")

            lines.append("  [A/B Test - Lần 2: CÓ DÙNG FILTER]")

        # Run primary query (with filter if defined)
        if metadata_filter:
            results = store.search_with_filter(query_text, top_k=3, metadata_filter=metadata_filter)
        else:
            results = store.search(query_text, top_k=3)

        agent_ans = agent.answer(query_text, top_k=3)

        gold_doc_ids = [d.strip() for d in str(gold_doc_id).split(",")]
        if q.get("requires_clarification"):
            lines.append(f"  [QUY TẮC ĐẶC BIỆT]: Thiếu thông tin platform -> Model KHÔNG ĐƯỢC tự ý thừa nhận/suy đoán, mà PHẢI HỎI LẠI:")
            lines.append(f"                      \"{q.get('clarification_question', '')}\"")

        # Evaluate
        found_in_top1 = False
        found_in_top3 = False
        content_found = False

        for rank, r in enumerate(results, 1):
            r_doc_id = r.get("metadata", {}).get("doc_id", "")
            r_content = r.get("content", "")
            r_score = r.get("score", 0.0)

            is_gold_doc = (r_doc_id in gold_doc_ids)
            has_gold_content = bool(gold_contains and gold_contains.lower() in r_content.lower())

            if is_gold_doc:
                if rank == 1:
                    found_in_top1 = True
                found_in_top3 = True

            if has_gold_content:
                content_found = True

            mark = "[GOLD]" if is_gold_doc else "      "
            match_txt = "[CHỨA ĐÁP ÁN]" if has_gold_content else ""
            lines.append(f"  Top-{rank}: {mark} score={r_score:.4f} | doc_id={r_doc_id:32} {match_txt}")
            preview = r_content.replace("\n", " ")[:120]
            lines.append(f"          preview: {preview}...")

        # Scoring
        if found_in_top1 and content_found:
            pts = 2
            note = "2/2 đ (Gold ở Top-1 và Chunk chứa thông tin chính xác)"
        elif found_in_top3 and content_found:
            pts = 1
            note = "1/2 đ (Gold ở Top-2/Top-3 và Chunk chứa thông tin)"
        elif found_in_top3:
            pts = 1
            note = "1/2 đ (Top-3 trúng file nhưng chunk chưa chứa trực tiếp chuỗi đáp án)"
        else:
            pts = 0
            note = "0/2 đ (Không tìm thấy tài liệu liên quan trong Top-3)"

        total_score += pts
        lines.append(f"  -> Đánh giá điểm: {note}")
        lines.append(f"  -> Agent trả lời: {agent_ans[:160]}...")
        lines.append("")

    lines.append("=" * 80)
    lines.append(f"TỔNG KẾT ĐIỂM CHẤT LƯỢNG TRUY XUẤT: {total_score} / {max_score} điểm")
    lines.append("=" * 80)

    report_str = "\n".join(lines)
    Path("ket_qua_benchmark.txt").write_text(report_str, encoding="utf-8")
    return report_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy benchmark retrieval cho Lab 07")
    parser.add_argument(
        "--strategy",
        choices=["fixed", "sentence", "recursive", "heading"],
        default="recursive",
        help="Chiến lược chunking cần thử nghiệm (fixed, sentence, recursive, heading)",
    )
    parser.add_argument(
        "--data-dir",
        default="data/ecommerce",
        help="Thư mục chứa dữ liệu .md",
    )
    args = parser.parse_args()

    report = run_benchmark(strategy=args.strategy, data_dir_str=args.data_dir)
    print(report)


if __name__ == "__main__":
    main()

