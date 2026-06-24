from __future__ import annotations

import re
import math
import os
from pathlib import Path
from typing import List, Tuple

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - exercised in minimal local envs
    BM25Okapi = None

from app.rag.base import BaseRetriever, EvidenceChunk
from app.rag.chunk_schema import KnowledgeChunk
from app.rag.document_store import LocalTextDocumentStore
from app.rag.knowledge_builder import DEFAULT_CHUNKS_PATH, build_p10m2_knowledge, load_knowledge_chunks
from app.rag.models import EvidenceChunk as P8EvidenceChunk
from app.schemas.evidence import EvidenceChunk as P9EvidenceChunk


COMMON_TERMS = [
    "咳嗽", "发热", "高热", "持续高热", "胸痛", "呼吸困难",
    "腹痛", "便血", "呕血", "头晕", "乏力", "意识模糊", "意识异常",
    "胃痛", "胃胀", "反酸", "恶心", "食欲下降", "腹胀", "腹泻", "便秘",
    "咽干", "咽痛", "寒战", "咳血", "心慌", "胸闷",
    "高危", "低危", "加重", "突然加重", "明显加重", "持续", "反复",
    "观察", "就医", "线下就医", "及时就医", "风险信号",
    "主诉", "持续时间", "伴随症状", "风险信号", "分级",
    "observe", "followup", "urgent_visit",
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = text.replace("：", ":").replace("；", ";").replace("，", ",")
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str) -> List[str]:
    text = normalize_text(text)
    tokens: List[str] = []

    for term in COMMON_TERMS:
        if term.lower() in text:
            tokens.append(term.lower())

    tokens.extend(re.findall(r"[a-zA-Z0-9_]+", text))

    short_chunks = re.split(r"[,;:\s、。！？\n]+", text)
    for piece in short_chunks:
        piece = piece.strip()
        if 1 < len(piece) <= 8:
            tokens.append(piece)

    return list(dict.fromkeys([tok for tok in tokens if tok]))


def extract_main_complaint_terms(query: str) -> List[str]:
    query = normalize_text(query)
    patterns = [
        r"当前主诉重点[:：](.*?)(?:[;；]|$)",
        r"主诉[:：](.*?)(?:[;；]|$)",
    ]

    complaint_terms: List[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, query):
            complaint_terms.extend(tokenize(match.strip()))

    return list(dict.fromkeys([term for term in complaint_terms if term]))


def score_boost(query: str, chunk: str) -> int:
    query_norm = normalize_text(query)
    chunk_norm = normalize_text(chunk)
    boost = 0

    complaint_terms = extract_main_complaint_terms(query_norm)
    for term in complaint_terms:
        if term in chunk_norm:
            boost += 4

    if sum(1 for term in complaint_terms if term in chunk_norm) >= 2:
        boost += 3

    important_terms = [
        "咳嗽", "发热", "持续高热", "胸痛", "呼吸困难",
        "腹痛", "腹泻", "便血", "呕血", "头晕", "乏力",
        "胃痛", "胃胀", "反酸", "恶心", "意识模糊", "意识异常",
    ]
    for term in important_terms:
        if term in query_norm and term in chunk_norm:
            boost += 2

    if "已确认无明显高风险信号" in query_norm:
        if "观察" in chunk_norm or "无高危信号" in chunk_norm or "继续观察" in chunk_norm:
            boost += 3

    if "已确认存在高风险信号" in query_norm:
        if "及时就医" in chunk_norm or "高危" in chunk_norm or "线下就医" in chunk_norm:
            boost += 4

    if "observe" in query_norm and ("观察" in chunk_norm or "症状变化" in chunk_norm or "记录" in chunk_norm):
        boost += 2
    if "followup" in query_norm and ("补充信息" in chunk_norm or "继续补充" in chunk_norm or "后续观察" in chunk_norm):
        boost += 2
    if "urgent_visit" in query_norm and ("及时就医" in chunk_norm or "高危" in chunk_norm or "尽快线下就医" in chunk_norm):
        boost += 3

    for term in ["观察", "加重", "持续", "就医", "风险信号", "主诉", "持续时间", "伴随症状", "分级"]:
        if term in query_norm and term in chunk_norm:
            boost += 1

    return boost


def _source_id_from_path(source: str) -> str:
    try:
        return Path(source).name or "local_knowledge_source"
    except Exception:
        return "local_knowledge_source"


class BM25Retriever(BaseRetriever):
    def __init__(self, document_store: LocalTextDocumentStore | None = None, debug: bool = False) -> None:
        self.document_store = document_store or LocalTextDocumentStore()
        self.debug = debug

    def retrieve(self, query: str, top_k: int = 3) -> List[EvidenceChunk]:
        chunks = self.document_store.load_chunks()
        if not chunks:
            return []

        tokenized_corpus = [tokenize(chunk.content) for chunk in chunks]
        query_tokens = tokenize(query)
        if BM25Okapi is not None:
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_scores = bm25.get_scores(query_tokens)
            retriever_type = "bm25"
        else:
            query_token_set = set(query_tokens)
            bm25_scores = [
                len(query_token_set & set(doc_tokens)) / max(1, len(query_token_set))
                for doc_tokens in tokenized_corpus
            ]
            retriever_type = "bm25_lexical_fallback"

        scored_chunks: List[Tuple[float, EvidenceChunk]] = []
        for score, chunk in zip(bm25_scores, chunks):
            final_score = float(score) + score_boost(query, chunk.content)
            scored_chunks.append(
                (
                    final_score,
                    EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    source=chunk.source,
                    score=final_score,
                    retriever_type=retriever_type,
                ),
            )
            )

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        evidence = [chunk for score, chunk in scored_chunks[:top_k] if score > 0]

        if not evidence:
            evidence = [
                EvidenceChunk(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    source=chunk.source,
                    score=0.0,
                    retriever_type="bm25_fallback",
                )
                for chunk in chunks[:top_k]
            ]

        if self.debug:
            print("\n===== HYBRID BM25 QUERY =====")
            print(query)
            print("query_tokens:", query_tokens)
            print("===== END HYBRID BM25 QUERY =====\n")

        return evidence

    def retrieve_p8(self, query: str, top_k: int = 3) -> List[P8EvidenceChunk]:
        evidence = self.retrieve(query, top_k=top_k)
        chunks: List[P8EvidenceChunk] = []
        for item in evidence:
            chunks.append(
                P8EvidenceChunk(
                    chunk_id=item.chunk_id,
                    source_id=_source_id_from_path(item.source),
                    title="TCM Assistant local knowledge base",
                    content=item.content,
                    score=float(item.score),
                    source_type="local_text",
                    trust_level="project_curated",
                    risk_level=None,
                    metadata={
                        "retriever_type": item.retriever_type,
                        "source_path": item.source,
                        "rank_bm25_available": BM25Okapi is not None,
                    },
                )
            )
        return chunks

    def retrieve_p9(self, query: str, top_k: int = 3) -> List[P9EvidenceChunk]:
        evidence = self.retrieve(query, top_k=top_k)
        return [
            P9EvidenceChunk(
                chunk_id=item.chunk_id,
                title="TCM Assistant local knowledge base",
                source=item.source,
                content=item.content,
                score=float(item.score),
                metadata={"retriever_type": item.retriever_type},
            )
            for item in evidence
        ]


def _p10m2_chunks_path() -> Path:
    return Path(os.getenv("RAG_CHUNKS_PATH") or DEFAULT_CHUNKS_PATH)


def p10m2_tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens: list[str] = []
    tokens.extend(re.findall(r"[A-Za-z0-9_]+", normalized))
    tokens.extend(re.findall(r"[\u4e00-\u9fff]{2,8}", normalized))
    for term in [
        "chief complaint",
        "duration",
        "sleep",
        "appetite",
        "stool",
        "urination",
        "chest pain",
        "breathing difficulty",
        "blood in stool",
        "vomiting blood",
        "high fever",
        "severe abdominal pain",
        "confusion",
        "diagnosis",
        "prescription",
        "offline care",
        "risk status",
        "胃胀",
        "腹胀",
        "便溏",
        "便血",
        "胸痛",
        "呼吸困难",
        "高热",
        "呕血",
        "剧烈腹痛",
        "意识异常",
    ]:
        if term.lower() in normalized:
            tokens.append(term.lower())
    return list(dict.fromkeys(token for token in tokens if token))


class P10M2BM25Retriever:
    def __init__(self, chunks_path: Path | None = None, *, auto_build: bool = True) -> None:
        self.chunks_path = chunks_path or _p10m2_chunks_path()
        self.auto_build = auto_build
        self._chunks: list[KnowledgeChunk] | None = None

    def load_chunks(self) -> list[KnowledgeChunk]:
        if self._chunks is None:
            chunks = load_knowledge_chunks(self.chunks_path)
            if not chunks and self.auto_build:
                build_p10m2_knowledge()
                chunks = load_knowledge_chunks(self.chunks_path)
            self._chunks = chunks
        return list(self._chunks)

    def score_chunks(self, query: str) -> list[tuple[KnowledgeChunk, float]]:
        chunks = self.load_chunks()
        if not chunks:
            return []
        corpus_tokens = [p10m2_tokenize(f"{chunk.title} {chunk.content} {' '.join(chunk.entities)}") for chunk in chunks]
        query_tokens = p10m2_tokenize(query)
        if not query_tokens:
            return [(chunk, 0.0) for chunk in chunks]

        if BM25Okapi is not None:
            bm25 = BM25Okapi(corpus_tokens)
            scores = [float(score) for score in bm25.get_scores(query_tokens)]
        else:
            total_docs = max(1, len(corpus_tokens))
            doc_freq: dict[str, int] = {}
            for tokens in corpus_tokens:
                for token in set(tokens):
                    doc_freq[token] = doc_freq.get(token, 0) + 1
            scores = []
            for tokens in corpus_tokens:
                token_counts = {token: tokens.count(token) for token in set(tokens)}
                score = 0.0
                for token in query_tokens:
                    if token not in token_counts:
                        continue
                    idf = math.log((total_docs + 1) / (doc_freq.get(token, 0) + 0.5)) + 1.0
                    score += token_counts[token] * idf
                scores.append(score)

        boosted: list[tuple[KnowledgeChunk, float]] = []
        lowered_query = query.lower()
        for chunk, score in zip(chunks, scores):
            haystack = f"{chunk.title} {chunk.content} {' '.join(chunk.entities)}".lower()
            entity_overlap = sum(1 for entity in chunk.entities if entity.lower() in lowered_query)
            lexical_overlap = len(set(query_tokens) & set(p10m2_tokenize(haystack)))
            final_score = max(0.0, float(score)) + entity_overlap * 1.5 + lexical_overlap * 0.2
            boosted.append((chunk, final_score))
        return boosted

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[KnowledgeChunk, float]]:
        scored = self.score_chunks(query)
        scored.sort(key=lambda item: item[1], reverse=True)
        positive = [item for item in scored if item[1] > 0]
        return (positive or scored)[:top_k]
