from __future__ import annotations

import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.rag.bm25_retriever import BM25Okapi
from app.rag.hybrid_retriever import HybridRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BM25 retrieval path for P0.2.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    retriever = HybridRetriever(mode="bm25_only")
    evidence = retriever.retrieve(args.query, top_k=args.top_k)

    print(f"query: {args.query}")
    print(f"real_bm25_available: {str(BM25Okapi is not None).lower()}")
    print(f"top_k: {args.top_k}")

    for item in evidence:
        preview = item.content.replace("\n", " ")[:120]
        print("\n[chunk]")
        print(f"retriever_type: {item.retriever_type}")
        print(f"chunk_id: {item.chunk_id}")
        print(f"score: {item.score}")
        print(f"source: {item.source}")
        print(f"content_preview: {preview}")


if __name__ == "__main__":
    main()
