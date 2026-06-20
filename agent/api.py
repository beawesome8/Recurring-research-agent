# agent/api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent.graph import build_graph
from agent.memory import init_db, add_topic, get_all_topics, get_topic_history, get_last_run

app = FastAPI(title="Research Agent API")
graph_app = build_graph()

init_db()

class TopicRequest(BaseModel):
    topic: str

@app.post("/topics")
def create_topic(req: TopicRequest):
    add_topic(req.topic)
    return {"message": f"Topic '{req.topic}' added.", "topics": get_all_topics()}

@app.get("/topics")
def list_topics():
    return {"topics": get_all_topics()}

@app.post("/topics/{topic}/run")
def trigger_run(topic: str):
    if topic not in get_all_topics():
        raise HTTPException(status_code=404, detail="Topic not found. Add it first via POST /topics.")

    initial_state = {
        "topic": topic, "queries": [], "search_results": [],
        "last_summary": "", "similar_findings": [],
        "summary": "", "has_changes": True
    }
    final_state = graph_app.invoke(initial_state)
    return {"topic": topic, "has_changes": final_state["has_changes"], "summary": final_state["summary"]}

@app.get("/topics/{topic}/history")
def topic_history(topic: str, limit: int = 10):
    history = get_topic_history(topic, limit=limit)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this topic.")
    return {"topic": topic, "history": history}

@app.get("/topics/{topic}/latest")
def topic_latest(topic: str):
    last = get_last_run(topic)
    if not last:
        raise HTTPException(status_code=404, detail="No runs found for this topic yet.")
    return {"topic": topic, **last}