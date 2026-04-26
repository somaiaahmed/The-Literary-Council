# Council of Perspectives — Multi-Agent AI System

A production-grade multi-agent decision support system built with:
- **FastAPI** — async REST + SSE streaming backend
- **LangGraph** — StateGraph orchestration with parallel agent nodes
- **LangChain + ChatAnthropic** — LLM calls per agent
- **HTML/CSS/JS** — rich frontend with real-time streaming UI

---

## Architecture

```
User Scenario
     │
     ▼
FastAPI /stream (SSE)
     │
     ▼
LangGraph StateGraph
  ├── single_agent_node (compare mode only)
  ├── agent_nvc        ─┐
  ├── agent_kahneman   ─┤  parallel execution
  ├── agent_covey      ─┤
  └── agent_stoic      ─┘
           │
           ▼
     synthesis_node
           │
           ▼
     SSE → Frontend (streams each agent as it finishes)
```

## Agents

| Agent | Book | Reasoning Lens |
|-------|------|---------------|
| The Empathic Mediator | Nonviolent Communication — Rosenberg | Observations → Feelings → Needs → Requests |
| The Cognitive Auditor | Thinking, Fast and Slow — Kahneman | System 1/2, cognitive bias detection |
| The Principled Strategist | The 7 Habits — Covey | Circle of Influence, Win-Win, Habit framework |
| The Stoic Philosopher | Meditations — Marcus Aurelius | Dichotomy of control, virtue, equanimity |

---

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the server
```bash
cd council
uvicorn main:app --reload --port 8000
```

### 3. Open in browser
```
http://localhost:8000
```

### 4. Use
- Enter your Anthropic API key (sk-ant-...)
- Pick or write a scenario
- Toggle "Compare" mode to see single-agent vs multi-agent side by side
- Click "Consult the Council"

Responses stream in real-time via SSE as each agent finishes.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the HTML frontend |
| GET | `/agents` | Returns agent metadata (JSON) |
| POST | `/analyze` | Full result (waits for all agents) |
| POST | `/stream` | SSE streaming (real-time per-agent) |
| GET | `/health` | Health check |

### POST /stream body
```json
{
  "scenario": "My friend accused me of...",
  "api_key": "sk-ant-...",
  "mode": "multi"   // or "compare"
}
```

---

## Project Structure

```
council/
├── main.py              # FastAPI app, routes, SSE endpoint
├── requirements.txt
├── agents/
│   ├── __init__.py
│   └── graph.py         # LangGraph StateGraph, agent definitions, nodes
└── static/
    └── index.html       # Frontend (HTML + CSS + JS, SSE client)
```
