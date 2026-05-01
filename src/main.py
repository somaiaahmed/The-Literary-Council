"""
FastAPI Backend — Multi-Agent Decision Support System (Gemini Version)
"""

import os
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from google import genai

from agents.graph import AGENT_DEFINITIONS

# --------------------------------------------------
# Load ENV
# --------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

# genai.configure(api_key=GEMINI_API_KEY)

# --------------------------------------------------
# FastAPI App
# --------------------------------------------------
app = FastAPI(title="Council of Perspectives", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------------------------------
# Models
# --------------------------------------------------
class AnalyzeRequest(BaseModel):
    scenario: str
    mode: str = "multi"


# --------------------------------------------------
# Helper
# --------------------------------------------------
async def ask_gemini(system_prompt: str, user_prompt: str):
    client = genai.Client(api_key=GEMINI_API_KEY)

    model = 'gemini-2.0-flash-lite'

    prompt = f"""
{system_prompt}

USER SCENARIO:
{user_prompt}
"""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=model,
        contents=prompt
    )
    return response.text


# --------------------------------------------------
# Routes
# --------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(
        content=html_path.read_text(encoding="utf-8")
    )


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):

    if not req.scenario.strip():
        raise HTTPException(status_code=400, detail="Scenario required")

    valid_results = []

    # run agents
    for agent in AGENT_DEFINITIONS:
        content = await ask_gemini(agent["system_prompt"], req.scenario)

        valid_results.append({
            "agent_key": agent["key"],
            "agent_name": agent["name"],
            "book": agent["book"],
            "content": content,
            "color": agent["color"],
            "icon": agent["icon"],
        })

    # synthesis
    compiled = "\n\n".join([
        f"{r['agent_name']} ({r['book']}):\n{r['content']}"
        for r in valid_results
    ])

    synth_prompt = f"""
You are a master synthesizer.

1. CONVERGENCE
2. PRODUCTIVE TENSIONS
3. FINAL RECOMMENDATION

Scenario:
{req.scenario}

Analyses:
{compiled}
"""

    synthesis = await ask_gemini(
        "You are a master synthesizer.",
        synth_prompt
    )

    return {
        "responses": valid_results,
        "synthesis": synthesis
    }

@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini"}