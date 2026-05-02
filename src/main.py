"""
FastAPI Backend — Literary Council Multi-Agent System
Streams agent results via SSE so the UI updates as each agent completes.
"""

import os
import json
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from google import genai

# Import agent definitions (no system_prompt exposed to frontend)
from agents.graph import AGENT_DEFINITIONS, get_agent_definitions

# ─── Load ENV ─────────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

# ─── App ──────────────────────────────────────
app = FastAPI(title="Literary Council", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Models ───────────────────────────────────
class AnalyzeRequest(BaseModel):
    scenario: str
    mode: str = "multi"


# ─── Gemini helper ────────────────────────────
async def ask_gemini(system_prompt: str, user_prompt: str, model: str = "gemini-2.0-flash-lite") -> str:
    """Call Gemini with a system prompt and user message. Runs in a thread to avoid blocking."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    full_prompt = f"{system_prompt}\n\n---\n\nUSER SCENARIO:\n{user_prompt}"

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=full_prompt,
    )
    return response.text


# ─── SSE helper ───────────────────────────────
def sse_event(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─── Routes ───────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Streams agent results + synthesis via Server-Sent Events (SSE).

    Events emitted:
      - init          → list of agent metadata (for skeleton UI)
      - agent_result  → one agent's completed response
      - synthesis     → final synthesis text
      - done          → stream complete
    """
    if not req.scenario.strip():
        raise HTTPException(status_code=400, detail="Scenario required")

    scenario = req.scenario.strip()

    async def event_stream():
        # ── 1. Send agent metadata so UI can build skeleton cards immediately
        agent_meta = get_agent_definitions()  # strips system_prompt
        yield sse_event("init", {"agents": agent_meta})

        # ── 2. Run all agents concurrently
        async def run_agent(agent: dict) -> dict:
            content = await ask_gemini(agent["system_prompt"], scenario)
            return {
                "agent_key":  agent["key"],
                "agent_name": agent["name"],
                "book":       agent["book"],
                "content":    content,
                "color":      agent["color"],
                "icon":       agent["icon"],
            }

        tasks = [asyncio.create_task(run_agent(a)) for a in AGENT_DEFINITIONS]

        results = []
        # Yield each agent result as it finishes (as_completed pattern)
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            yield sse_event("agent_result", result)

        # ── 3. Synthesize all responses
        compiled = "\n\n".join(
            f"{r['agent_name']} ({r['book']}):\n{r['content']}"
            for r in results
        )

        synthesis_system = "You are a master synthesizer who distills multiple philosophical perspectives into clear, actionable wisdom."

        synthesis_prompt = f"""Given this scenario and the analyses below, produce:

**1. CONVERGENCE**
What do all perspectives agree on?

**2. PRODUCTIVE TENSIONS**
Where do they meaningfully disagree? Why does that tension matter?

**3. FINAL RECOMMENDATION**
A concrete, wise suggestion that integrates the best of each view.

---

Scenario:
{scenario}

Analyses:
{compiled}
"""

        synthesis = await ask_gemini(synthesis_system, synthesis_prompt, model="gemini-2.0-flash")
        yield sse_event("synthesis", {"content": synthesis})
        yield sse_event("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables Nginx buffering for SSE
        },
    )


@app.get("/agents")
async def list_agents():
    """Return public agent metadata (no system prompts)."""
    return {"agents": get_agent_definitions()}


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-2.0-flash-lite"}