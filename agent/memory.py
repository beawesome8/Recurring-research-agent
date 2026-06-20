import sqlite3
import os
import json
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = os.path.join("data", "chroma")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

embedding_fn = embedding_functions.DefaultEmbeddingFunction()

collection = chroma_client.get_or_create_collection(
    name="research_findings",
    embedding_function=embedding_fn
)

DB_PATH = os.path.join("data", "research.sqlite3")

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            run_date TEXT NOT NULL,
            summary TEXT NOT NULL,
            sources_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_run(topic: str, summary: str, sources: list):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO research_runs (topic, run_date, summary, sources_json) VALUES (?, ?, ?, ?)",
        (topic, datetime.now().isoformat(), summary, json.dumps(sources))
    )
    conn.commit()
    conn.close()

def get_last_run(topic: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT run_date, summary, sources_json FROM research_runs WHERE topic = ? ORDER BY run_date DESC LIMIT 1",
        (topic,)
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"run_date": row[0], "summary": row[1], "sources": json.loads(row[2])}

def embed_finding(topic: str, summary: str, run_date: str):
    collection.add(
        documents=[summary],
        metadatas=[{"topic": topic, "run_date": run_date}],
        ids=[f"{topic}_{run_date}"]
    )

def query_similar_findings(topic: str, query_text: str, n_results: int = 3):
    available = collection.count()
    if available == 0:
        return []
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, available),
            where={"topic": topic}
        )
    except Exception:
        return []
    matches = []
    if results["documents"] and results["documents"][0]:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            matches.append({"summary": doc, "run_date": meta["run_date"]})
    return matches

if __name__ == "__main__":
    init_db()

    save_run(
        topic="test topic",
        summary="Munich pays the highest AI engineer salaries in Germany, averaging 94000 euros.",
        sources=[{"title": "Example", "url": "https://example.com"}]
    )
    embed_finding(
        topic="test topic",
        summary="Munich pays the highest AI engineer salaries in Germany, averaging 94000 euros.",
        run_date=datetime.now().isoformat()
    )

    last_run = get_last_run("test topic")
    print("Last run from SQLite:", last_run)

    similar = query_similar_findings(
        topic="test topic",
        query_text="Which German city has the best pay for AI roles?"
    )
    print("Similar findings from Chroma:", similar)