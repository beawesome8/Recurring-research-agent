# Recurring Research Agent with Memory

A LangGraph agent that researches a topic on a schedule, remembers what it found last time, and reports only what's actually new or changed, instead of repeating the same summary every run.

Built as a hands-on project to apply agentic AI patterns (multi-node graphs, conditional routing, dual memory systems) to a real, daily-use tool: tracking the German AI Engineering job market.

## Why this exists

Most "research agent" tutorials answer one question and stop. The useful version of this agent is the one that runs unattended, knows what it told you last week, and only interrupts you when something is genuinely worth knowing. That's the problem this project solves, and the diff-detection mechanism is the core engineering challenge it's built around.

## What it actually does

On each run, the agent plans search queries for a topic, executes them, retrieves what it found on the previous run (exact match) and anything semantically related from earlier runs (fuzzy match), compares the new findings against that memory, and produces a report that either says "here's what changed" or "nothing new since last time." If something changed, it sends a Telegram alert. Either way, the run is logged to a persistent history.

### Example: the diff in action

On one real run, the agent caught a genuine market signal a static summary would have missed:

> **CHANGES_FOUND: yes**
> A Bertelsmann Stiftung study titled *"KI-Jobs in Deutschland: Stagnation statt Boom"* ("AI Jobs in Germany: Stagnation Instead of Boom") appeared for the first time in this run's results, introducing institutional-level skepticism about the pace of AI hiring growth, set against three consecutive prior runs all reinforcing a "structural shortage, sustained growth" narrative. The agent also flagged that average salary figures from ERI SalaryExpert had drifted downward across three consecutive pulls (€92,409 → €91,752 → €91,745), a pattern only visible because the agent retained and compared its own historical findings.

That's the difference between a chatbot answering a question and an agent tracking a domain over time.

## Architecture

| Node | Responsibility |
|---|---|
| `planner` | Turns a topic into 2-3 targeted search queries via Claude |
| `search` | Executes queries through the Tavily search API |
| `memory_retrieval` | Pulls the last exact summary (SQLite) and semantically similar past findings (Chroma) |
| `synthesis` | Compares new findings against memory; outputs a diff report and a `CHANGES_FOUND` flag |
| `save_memory` | Persists the run to SQLite always; embeds to Chroma only if something changed |
| `notify` | Sends a Telegram alert, reached only via a conditional edge when `has_changes` is true |

### Memory design

Two stores, deliberately serving different purposes rather than reaching for a vector database by default:

- **SQLite** is the structured, exact-match audit trail: every run, every date, every summary, queryable precisely.
- **Chroma** is semantic memory: it answers "has something *like* this come up before," even with completely different wording, which is what makes the diff logic actually work rather than relying on brittle keyword matching.

The vector store is only written to on runs where something genuinely changed, keeping it from accumulating near-duplicate "nothing new" entries that would degrade future semantic search quality over time.

## Stack

- **Agent orchestration:** LangGraph (stateful multi-node graph, conditional routing)
- **LLM:** Claude (Anthropic API)
- **Search:** Tavily API
- **Structured memory:** SQLite
- **Semantic memory:** Chroma (vector store)
- **Scheduling:** APScheduler
- **API layer:** FastAPI, with auto-generated OpenAPI docs
- **Notifications:** Telegram Bot API
- **Deployment:** Docker

## API

The agent is exposed as a service, not just a script:

| Endpoint | Method | Purpose |
|---|---|---|
| `/topics` | `POST` | Register a new topic to track |
| `/topics` | `GET` | List all tracked topics |
| `/topics/{topic}/run` | `POST` | Manually trigger a full pipeline run |
| `/topics/{topic}/history` | `GET` | Retrieve past runs for a topic |
| `/topics/{topic}/latest` | `GET` | Get the most recent summary |

Interactive docs available at `/docs` once running.

## API costs

This runs on pay-as-you-go APIs, no fixed infrastructure cost, but it's worth knowing what a real run actually costs rather than treating "uses an LLM" as a black box.

| Service | Pricing | Cost per run |
|---|---|---|
| Claude Sonnet 4.6 (synthesis + planning) | $3 / $15 per million input/output tokens | ~$0.02 |
| Tavily search | 1,000 free searches/month, then $0.008/search | $0 (within free tier at this cadence) |

A single run makes two LLM calls (query planning, then diff synthesis against ~9 search results) and 2-3 search queries. At a 6-hour schedule, that's roughly 120 runs/month, about **$2.40/month in Claude API spend**, and around 360 Tavily searches/month, comfortably inside the free tier. Tracking multiple topics scales linearly: each additional topic on the same schedule adds roughly the same per-run cost again.

The cheapest lever available if cost ever mattered at scale: swap `claude-sonnet-4-6` for `claude-haiku-4-5` ($1/$5 per million tokens) for the planner node specifically, since query generation is a much simpler task than the diff synthesis and doesn't need the larger model's reasoning depth. 

## Running it

```bash
# Local
pip install -r requirements.txt
uvicorn agent.api:app --reload

# Or via Docker
docker build -t research-agent .
docker run -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" research-agent
```

Requires a `.env` file with `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`.

## What I learned building this

The interesting engineering problems here weren't the happy path, they were the edges. Getting the LLM to emit a parseable `CHANGES_FOUND: yes/no` signal reliably, rather than trying to infer intent from free-form text, was a small prompting decision with an outsized effect on system reliability. Deciding that "nothing changed" runs should still hit SQLite but skip Chroma was a deliberate tradeoff between a complete audit trail and a semantic index that doesn't degrade with noise. And several real debugging sessions, a stale module-level state mismatch traced with `repr()`-level output, Docker network timeouts on large dependency downloads, an `.env` parsing difference between Python's `dotenv` and Docker's stricter `--env-file` parser, were the kind of issues that don't show up in tutorials but are exactly what production systems actually require handling.

## Roadmap

- [ ] Swap the default local embedding model for an Anthropic/OpenAI embedding model
- [ ] Expose agent tools via MCP instead of hardcoded function calls
- [ ] Add structured run-level observability (latency, token usage per run)
- [ ] Track multiple concurrent topics with independent schedules