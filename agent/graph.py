import os
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from tavily import TavilyClient
from langgraph.graph import StateGraph, END

# agent/graph.py

from typing import TypedDict, List

class ResearchState(TypedDict):
    topic: str              # what we're researching, e.g. "AI Engineer hiring trends Germany"
    queries: List[str]       # search queries the planner generates
    search_results: List[dict]  # raw results Tavily returns
    summary: str             # final Claude-written summary
    
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

def synthesis_node(state: ResearchState) -> dict:
    topic = state["topic"]
    results = state["search_results"]

    sources_text = ""
    for i, r in enumerate(results, start=1):
        sources_text += f"\n[Source {i}] {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n"

    prompt = f"""You are a research analyst. Based on the sources below, write a clear,
well-organized summary of the current state of: "{topic}"

Focus on concrete facts, trends, and figures where available. Avoid vague language.
Write 3-5 short paragraphs. Mention source numbers like [Source 1] when citing a specific claim.

SOURCES:
{sources_text}
"""

    response = llm.invoke(prompt)
    return {"summary": response.content}

def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("synthesis", synthesis_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()

if __name__ == "__main__":
    app = build_graph()
    initial_state = {"topic": "AI Engineer hiring trends Germany", "queries": [], "search_results": [], "summary": ""}
    final_state = app.invoke(initial_state)

    print("\n--- SUMMARY ---\n")
    print(final_state["summary"])