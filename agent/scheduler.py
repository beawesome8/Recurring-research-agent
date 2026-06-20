# agent/scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from agent.graph import build_graph
from agent.memory import init_db

TOPICS = [
    "AI Engineer hiring trends Germany",
]

from agent.memory import init_db, get_all_topics

from apscheduler.schedulers.blocking import BlockingScheduler
from agent.graph import build_graph
from agent.memory import init_db, get_all_topics

def run_pipeline_for_all_topics():
    app = build_graph()
    topics = get_all_topics()
    if not topics:
        print("No topics registered yet.")
        return
    for topic in topics:
        print(f"\n=== Running pipeline for: {topic} ===")
        initial_state = {
            "topic": topic, "queries": [], "search_results": [],
            "last_summary": "", "similar_findings": [],
            "summary": "", "has_changes": True
        }
        final_state = app.invoke(initial_state)
        print(f"=== Done. has_changes: {final_state['has_changes']} ===\n")

if __name__ == "__main__":
    init_db()
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline_for_all_topics, "interval", hours=6)

    print("Scheduler started. Running once immediately, then every 6 hours.")
    run_pipeline_for_all_topics()

    scheduler.start()