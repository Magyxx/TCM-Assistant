import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge_base.txt"
VECTOR_DB_DIR = BASE_DIR / "faiss_index"


def load_knowledge_text() -> str:
    with KNOWLEDGE_FILE.open("r", encoding="utf-8") as f:
        return f.read()


def build_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )


def main() -> None:
    text = load_knowledge_text()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", "，"]
    )

    chunks = splitter.split_text(text)
    docs = [Document(page_content=chunk) for chunk in chunks if chunk.strip()]

    embeddings = build_embeddings()
    vector_store = FAISS.from_documents(docs, embeddings)

    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(VECTOR_DB_DIR))

    print(f"知识条目切分后数量: {len(docs)}")
    print(f"向量库已保存到: {VECTOR_DB_DIR}")


if __name__ == "__main__":
    main()