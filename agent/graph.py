import os
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from tavily import TavilyClient
from langgraph.graph import StateGraph, END
from agent.memory import init_db, get_last_run, query_similar_findings, save_run, embed_finding
from datetime import datetime
from agent.notifier import send_telegram_message
# agent/graph.py

from typing import TypedDict, List

class ResearchState(TypedDict):
    topic: str
    queries: List[str]
    search_results: List[dict]
    last_summary: str          # most recent prior summary, or "" if first run
    similar_findings: List[dict]  # semantically related past findings
    summary: str
    has_changes: bool          # whether this run found anything new
    
load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.getenv("ANTHROPIC_API_KEY"))

def planner_node(state: ResearchState) -> dict:
    topic = state["topic"]

    prompt = f"""You are a research planning assistant.
Given the topic: "{topic}"

Generate 2-3 specific, well-formed web search queries that would surface
the most current and relevant information on this topic.

Return ONLY the queries, one per line, no numbering, no extra text."""

    response = llm.invoke(prompt)
    queries = [q.strip() for q in response.content.split("\n") if q.strip()]

    return {"queries": queries}

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
def search_node(state: ResearchState) -> dict:
    queries = state["queries"]
    all_results = []

    for query in queries:
        response = tavily.search(query=query, max_results=3)
        for item in response["results"]:
            all_results.append({
                "query": query,
                "title": item["title"],
                "url": item["url"],
                "content": item["content"],
            })

    return {"search_results": all_results}

def memory_retrieval_node(state: ResearchState) -> dict:
    topic = state["topic"]

    last_run = get_last_run(topic)
    last_summary = last_run["summary"] if last_run else ""

    combined_new_text = " ".join(r["content"] for r in state["search_results"])
    similar = query_similar_findings(topic, combined_new_text, n_results=3) if last_run else []

    return {"last_summary": last_summary, "similar_findings": similar}

def synthesis_node(state: ResearchState) -> dict:
    topic = state["topic"]
    results = state["search_results"]
    last_summary = state["last_summary"]
    similar_findings = state["similar_findings"]

    sources_text = ""
    for i, r in enumerate(results, start=1):
        sources_text += f"\n[Source {i}] {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n"

    if not last_summary:
        prompt = f"""You are a research analyst. Based on the sources below, write a clear,
well-organized summary of the current state of: "{topic}"

Focus on concrete facts, trends, and figures where available. Write 3-5 short paragraphs.
Mention source numbers like [Source 1] when citing a specific claim.

SOURCES:
{sources_text}
"""
    else:
        similar_text = "\n".join(f"- {f['summary']} (from {f['run_date']})" for f in similar_findings)
        prompt = f"""You are a research analyst tracking ongoing changes in: "{topic}"

Here is your previous summary of this topic:
{last_summary}

Here are related findings from earlier research runs:
{similar_text if similar_text else "None"}

Here are today's new search results:
{sources_text}

Compare today's findings against the previous summary and earlier findings.
Write a short report that:
1. States clearly whether there is anything genuinely NEW or CHANGED since last time.
2. If yes, describe only the new/changed information in 2-4 short paragraphs, citing [Source N].
3. If nothing meaningful has changed, say so in one sentence and do not repeat the old summary.

Start your response with either "CHANGES_FOUND: yes" or "CHANGES_FOUND: no" on the first line, then a blank line, then the report.
"""

    response = llm.invoke(prompt)
    content = response.content
    
    has_changes = True
    if content.strip().startswith("CHANGES_FOUND: no"):
        has_changes = False

    return {"summary": content, "has_changes": has_changes}

def save_memory_node(state: ResearchState) -> dict:
    topic = state["topic"]
    summary = state["summary"]
    sources = [{"title": r["title"], "url": r["url"]} for r in state["search_results"]]

    save_run(topic, summary, sources)

    if state["has_changes"]:
        embed_finding(topic, summary, run_date=datetime.now().isoformat())

    return {}

def notify_node(state: ResearchState) -> dict:
    topic = state["topic"]
    summary = state["summary"]

    cleaned = summary.split("CHANGES_FOUND:", 1)[-1]
    if cleaned.startswith(" yes") or cleaned.startswith(" no"):
        cleaned = cleaned.split("\n", 1)[-1].strip()

    message = f"Research update: {topic}\n\n{cleaned[:3500]}"
    result = send_telegram_message(message)

    return {}

def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_node("save_memory", save_memory_node)
    graph.add_node("notify", notify_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "memory_retrieval")
    graph.add_edge("memory_retrieval", "synthesis")
    graph.add_edge("synthesis", "save_memory")

    def route_after_save(state):
        return "notify" if state["has_changes"] else "skip_notify"
    
    graph.add_conditional_edges(
    "save_memory",
    route_after_save,
    {"notify": "notify", "skip_notify": END}
    )
    graph.add_edge("notify", END)

    return graph.compile()
if __name__ == "__main__":
    init_db()
    app = build_graph()
    initial_state = {
        "topic": "AI Engineer hiring trends Germany",
        "queries": [], "search_results": [],
        "last_summary": "", "similar_findings": [],
        "summary": "", "has_changes": True
    }
    final_state = app.invoke(initial_state)
    print("HAS CHANGES:", final_state["has_changes"])
    print("Check your Telegram now.")
    
    