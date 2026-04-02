from pathlib import Path
from typing import List, Tuple
import re

from rank_bm25 import BM25Okapi


BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge_base.txt"

# 领域关键词词表（第一版可手动维护，后续再扩）
COMMON_TERMS = [
    # 主诉 / 症状
    "咳嗽", "发热", "高热", "持续高热", "胸痛", "呼吸困难",
    "腹痛", "便血", "呕血", "头晕", "乏力", "意识模糊", "意识异常",
    "胃痛", "胃胀", "反酸", "恶心", "食欲下降", "腹胀", "腹泻", "便秘",
    "咽干", "咽痛", "寒战", "咳血", "心慌", "胸闷",

    # 风险 / 变化
    "高危", "低危", "加重", "突然加重", "明显加重", "持续", "反复",
    "观察", "就医", "线下就医", "及时就医", "风险信号",

    # 报告 / 分级
    "主诉", "持续时间", "伴随症状", "风险信号", "分级",
    "observe", "followup", "urgent_visit",
]


def normalize_text(text: str) -> str:
    """
    基础规范化：
    - 小写
    - 去首尾空格
    - 统一常见全角/半角符号影响
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = text.replace("：", ":").replace("；", ";").replace("，", ",")
    text = re.sub(r"\s+", " ", text)
    return text


def load_knowledge_chunks() -> List[str]:
    """
    按空行切分知识库文本，每个段落块作为一个知识 chunk。
    """
    with KNOWLEDGE_FILE.open("r", encoding="utf-8") as f:
        text = f.read()

    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    return chunks


def tokenize(text: str) -> List[str]:
    """
    面向当前项目的轻量中文“关键词检索分词”。

    原则：
    1. 优先提取领域关键词（症状、风险、分级等）
    2. 再提取英文/数字 token
    3. 去重保序

    这样比“整段连续中文作为一个 token”更适合当前 BM25 场景。
    """
    text = normalize_text(text)
    tokens: List[str] = []

    # 先抓领域关键词
    for term in COMMON_TERMS:
        if term.lower() in text:
            tokens.append(term.lower())

    # 再抓英文、数字、下划线类 token
    extra_tokens = re.findall(r"[a-zA-Z0-9_]+", text)
    tokens.extend(extra_tokens)

    # 可选：补充一些按常见中文分隔符切的小片段
    # 避免完全漏掉非词表中的短片段
    short_chunks = re.split(r"[,;:\s、。！？\n]+", text)
    for piece in short_chunks:
        piece = piece.strip()
        if 1 < len(piece) <= 8:
            # 避免把太长整句塞进去
            tokens.append(piece)

    # 去重保序
    dedup_tokens = list(dict.fromkeys([tok for tok in tokens if tok]))
    return dedup_tokens

def extract_main_complaint_terms(query: str) -> List[str]:
    """
    从 query 中提取主诉相关关键词。
    主要识别：
    - 当前主诉重点：xxx
    - 主诉：xxx

    再用 tokenize 拆成可用于 boost 的词。
    """
    query = normalize_text(query)

    patterns = [
        r"当前主诉重点[:：](.*?)(?:[;；]|$)",
        r"主诉[:：](.*?)(?:[;；]|$)",
    ]

    complaint_texts: List[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, query)
        for m in matches:
            m = m.strip()
            if m:
                complaint_texts.append(m)

    complaint_terms: List[str] = []
    for text in complaint_texts:
        complaint_terms.extend(tokenize(text))

    # 去重保序
    return list(dict.fromkeys([t for t in complaint_terms if t]))


def build_bm25(chunks: List[str]) -> BM25Okapi:
    tokenized_corpus = [tokenize(chunk) for chunk in chunks]
    return BM25Okapi(tokenized_corpus)


def score_boost(query: str, chunk: str) -> int:
    """
    在 BM25 基础上增加规则加权，提升当前问诊项目中的相关性。

    目标：
    1. 主诉命中优先
    2. 主诉 + 伴随症状共同命中更优先
    3. 风险状态和分级命中可加权
    4. 低风险场景更容易命中“观察建议”
    """
    query_norm = normalize_text(query)
    chunk_norm = normalize_text(chunk)

    boost = 0

    # -------------------------
    # 1. 主诉优先
    # -------------------------
    complaint_terms = extract_main_complaint_terms(query_norm)
    for term in complaint_terms:
        if term in chunk_norm:
            boost += 4

    # 如果主诉里同时有多个词都命中，再额外加权
    complaint_hit_count = sum(1 for term in complaint_terms if term in chunk_norm)
    if complaint_hit_count >= 2:
        boost += 3

    # -------------------------
    # 2. 伴随症状与风险词命中
    # -------------------------
    important_terms = [
        "咳嗽", "发热", "持续高热", "胸痛", "呼吸困难",
        "腹痛", "腹泻", "便血", "呕血", "头晕", "乏力",
        "胃痛", "胃胀", "反酸", "恶心", "意识模糊", "意识异常",
    ]
    for term in important_terms:
        if term in query_norm and term in chunk_norm:
            boost += 2

    # -------------------------
    # 3. 风险状态偏置
    # -------------------------
    if "已确认无明显高风险信号" in query_norm:
        if "观察" in chunk_norm or "无高危信号" in chunk_norm or "继续观察" in chunk_norm:
            boost += 3

    if "已确认存在高风险信号" in query_norm:
        if "及时就医" in chunk_norm or "高危" in chunk_norm or "线下就医" in chunk_norm:
            boost += 4

    # -------------------------
    # 4. 分级偏置
    # -------------------------
    if "observe" in query_norm:
        if "观察" in chunk_norm or "症状变化" in chunk_norm or "记录" in chunk_norm:
            boost += 2

    if "followup" in query_norm:
        if "补充信息" in chunk_norm or "继续补充" in chunk_norm or "后续观察" in chunk_norm:
            boost += 2

    if "urgent_visit" in query_norm:
        if "及时就医" in chunk_norm or "高危" in chunk_norm or "尽快线下就医" in chunk_norm:
            boost += 3

    # -------------------------
    # 5. 通用提示词命中
    # -------------------------
    generic_terms = [
        "观察", "加重", "持续", "就医", "风险信号",
        "主诉", "持续时间", "伴随症状", "分级"
    ]
    for term in generic_terms:
        if term in query_norm and term in chunk_norm:
            boost += 1

    return boost


def retrieve_knowledge(query: str, top_k: int = 3, debug: bool = False) -> List[str]:
    """
    使用本地 BM25 从 knowledge_base.txt 中检索 top-k 相关知识块。
    """
    chunks = load_knowledge_chunks()
    bm25 = build_bm25(chunks)

    query_tokens = tokenize(query)
    bm25_scores = bm25.get_scores(query_tokens)

    scored_chunks: List[Tuple[float, str]] = []
    for score, chunk in zip(bm25_scores, chunks):
        final_score = float(score) + score_boost(query, chunk)
        scored_chunks.append((final_score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    top_chunks = [chunk for score, chunk in scored_chunks[:top_k] if score > 0]

    # 如果一个都没命中，退回前几条通用知识
    if not top_chunks:
        top_chunks = chunks[:top_k]

    if debug:
        print("\n===== BM25 QUERY =====")
        print(query)
        print("query_tokens:", query_tokens)
        print("===== END BM25 QUERY =====\n")

        print("\n===== BM25 SCORED CHUNKS =====")
        for i, (score, chunk) in enumerate(scored_chunks[:top_k], 1):
            print(f"[{i}] score={score:.4f}")
            print(chunk)
            print("-" * 40)
        print("===== END BM25 SCORED CHUNKS =====\n")

    return top_chunks