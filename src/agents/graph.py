"""
Multi-Agent Council — Gemini + LangGraph Clean Parallel Version
"""

from typing import TypedDict, Annotated, List
import operator
import os
import asyncio
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END, START
from langgraph.types import Send

import google.generativeai as genai


# ─────────────────────────────────────────────
# Load Gemini
# ─────────────────────────────────────────────
load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)


# ─────────────────────────────────────────────
# State
# ─────────────────────────────────────────────
class AgentResponse(TypedDict):
    agent_key: str
    agent_name: str
    book: str
    content: str
    color: str
    icon: str


class CouncilState(TypedDict):
    scenario: str
    mode: str
    responses: Annotated[list[AgentResponse], operator.add]
    synthesis: str
    single_agent_response: str


# ─────────────────────────────────────────────
# Agents Definition (your philosophy engines)
# ─────────────────────────────────────────────
AGENT_DEFINITIONS = [
    {
        "key": "nvc",
        "name": "The Empathic Mediator",
        "book": "Nonviolent Communication — Rosenberg",
        "color": "#3d5a3e",
        "icon": "💚",
        "system_prompt": """You are Nonviolent Communication (Marshall Rosenberg).

Structure:
1. Observations (facts only)
2. Feelings
3. Needs
4. Requests

No blame. Only needs. Be deeply empathetic."""
    },
    {
        "key": "kafka",
        "name": "The Existential Mirror",
        "book": "Metamorphosis — Franz Kafka",
        "color": "#2b2b2b",
        "icon": "🪳",
        "system_prompt": """You embody Kafka's worldview (The Metamorphosis).

Interpret the scenario through:
- Alienation
- Absurdity
- Powerlessness
- Internal guilt vs external judgment

Be symbolic, psychological, slightly unsettling but insightful."""
    },
    {
        "key": "camus",
        "name": "The Absurd Philosopher",
        "book": "The Stranger — Albert Camus",
        "color": "#b8860b",
        "icon": "🌅",
        "system_prompt": """You embody Camus (The Stranger).

Analyze through:
- Absurdity of meaning
- Emotional detachment
- Radical honesty
- Acceptance of chaos without false meaning

Be calm, detached, philosophical."""
    },
    {
        "key": "dostoevsky",
        "name": "The Moral Tormentor",
        "book": "The Idiot — Dostoevsky",
        "color": "#7a2e10",
        "icon": "⚖️",
        "system_prompt": """You embody Dostoevsky (The Idiot).

Focus on:
- Moral contradiction
- Emotional suffering
- Compassion vs judgment
- Inner guilt and purity

Be emotionally deep, psychologically intense."""
    },
]


# ─────────────────────────────────────────────
# Gemini helper
# ─────────────────────────────────────────────
async def call_gemini(system_prompt: str, scenario: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
{system_prompt}

---

Scenario:
{scenario}
"""

    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text


# ─────────────────────────────────────────────
# Parallel Agent Node (IMPORTANT FIX)
# ─────────────────────────────────────────────
async def agent_node(state: CouncilState, agent: dict) -> dict:
    content = await call_gemini(agent["system_prompt"], state["scenario"])

    return {
        "responses": [{
            "agent_key": agent["key"],
            "agent_name": agent["name"],
            "book": agent["book"],
            "content": content,
            "color": agent["color"],
            "icon": agent["icon"],
        }]
    }


# ─────────────────────────────────────────────
# Router (TRUE PARALLELISM)
# ─────────────────────────────────────────────
def fanout_agents(state: CouncilState):
    return [
        Send("run_agent", {"agent": agent})
        for agent in AGENT_DEFINITIONS
    ]


# ─────────────────────────────────────────────
# Generic runner node
# ─────────────────────────────────────────────
async def run_agent_node(state: dict) -> dict:
    agent = state["agent"]
    content = await call_gemini(agent["system_prompt"], state["scenario"])

    return {
        "responses": [{
            "agent_key": agent["key"],
            "agent_name": agent["name"],
            "book": agent["book"],
            "content": content,
            "color": agent["color"],
            "icon": agent["icon"],
        }]
    }


# ─────────────────────────────────────────────
# Synthesis node
# ─────────────────────────────────────────────
async def synthesis_node(state: CouncilState) -> dict:

    model = genai.GenerativeModel("gemini-1.5-pro")

    compiled = "\n\n".join([
        f"{r['agent_name']} ({r['book']}):\n{r['content']}"
        for r in state["responses"]
    ])

    prompt = f"""
You are the Council Synthesizer.

Produce:

1. CONVERGENCE
2. TENSIONS
3. FINAL RECOMMENDATION

Be wise and concise.

Scenario:
{state['scenario']}

Analyses:
{compiled}
"""

    response = await asyncio.to_thread(model.generate_content, prompt)

    return {
        "synthesis": response.text
    }


# ─────────────────────────────────────────────
# Optional single agent baseline
# ─────────────────────────────────────────────
async def single_agent_node(state: CouncilState) -> dict:

    if state["mode"] != "compare":
        return {"single_agent_response": ""}

    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
You are a helpful AI assistant.

Give balanced advice.

Scenario:
{state['scenario']}
"""

    response = await asyncio.to_thread(model.generate_content, prompt)

    return {
        "single_agent_response": response.text
    }


# ─────────────────────────────────────────────
# Build Graph (FIXED PARALLEL DESIGN)
# ─────────────────────────────────────────────
def build_graph():

    builder = StateGraph(CouncilState)

    # nodes
    builder.add_node("run_agent", run_agent_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("single", single_agent_node)

    # entry
    builder.set_entry_point("single")

    # parallel fan-out (THIS IS THE FIX)
    builder.add_conditional_edges(
        "single",
        fanout_agents
    )

    # after agents → synthesis
    builder.add_edge("run_agent", "synthesis")

    # end
    builder.add_edge("synthesis", END)

    return builder.compile()


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────
async def run_council(scenario: str, mode: str = "multi"):

    graph = build_graph()

    result = await graph.ainvoke({
        "scenario": scenario,
        "mode": mode,
        "responses": [],
        "synthesis": "",
        "single_agent_response": ""
    })

    return result


def get_agent_definitions():
    return [
        {k: v for k, v in a.items() if k != "system_prompt"}
        for a in AGENT_DEFINITIONS
    ]