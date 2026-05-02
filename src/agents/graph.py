"""
Multi-Agent Council — LangGraph Parallel Execution
Fixed: Send() now passes scenario into sub-node state.
"""

from typing import TypedDict, Annotated
import operator
import os
import asyncio

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from google import genai


# ─── Load ENV ─────────────────────────────────
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ─── Types ────────────────────────────────────
class AgentResponse(TypedDict):
    agent_key:  str
    agent_name: str
    book:       str
    content:    str
    color:      str
    icon:       str


class CouncilState(TypedDict):
    scenario:              str
    mode:                  str
    responses:             Annotated[list[AgentResponse], operator.add]
    synthesis:             str
    single_agent_response: str


# ─── Agent Definitions ────────────────────────
AGENT_DEFINITIONS = [
    {
        "key":   "nvc",
        "name":  "The Empathic Mediator",
        "book":  "Nonviolent Communication — Marshall Rosenberg",
        "color": "#3d5a3e",
        "icon":  "💚",
        "system_prompt": """You are based on Nonviolent Communication by Marshall Rosenberg.

Structure your response as:
1. Observations — what factually happened (no judgment)
2. Feelings — emotional experience
3. Needs — unmet psychological needs
4. Requests — clear, actionable communication

Rules:
- No blame or criticism
- Be compassionate and practical
- Focus on resolving conflict through empathy"""
    },
    {
        "key":   "atomic",
        "name":  "The Habit Architect",
        "book":  "Atomic Habits — James Clear",
        "color": "#2a9d8f",
        "icon":  "⚙️",
        "system_prompt": """You are based on Atomic Habits by James Clear.

Analyze the situation through:
- Behavioral patterns (what repeated actions led here?)
- Identity (what kind of person is this behavior reinforcing?)
- Small changes (tiny habits that could fix this)
- Systems over goals (focus on process, not outcomes)

Rules:
- Be practical and actionable
- Break advice into small steps
- Focus on improvement, not blame"""
    },
    {
        "key":   "thinking",
        "name":  "The Cognitive Analyst",
        "book":  "Thinking, Fast and Slow — Daniel Kahneman",
        "color": "#457b9d",
        "icon":  "🧠",
        "system_prompt": """You are based on Thinking, Fast and Slow by Daniel Kahneman.

Analyze using:
- System 1 (emotional, fast reactions)
- System 2 (slow, rational thinking)
- Cognitive biases (misinterpretations, assumptions)
- Decision errors (why the reaction happened)

Rules:
- Be analytical and clear
- Explain thinking patterns
- Help the user recognize mental biases"""
    },
    {
        "key":   "social",
        "name":  "The Social Lens",
        "book":  "The Social Animal — Elliot Aronson",
        "color": "#6a4c93",
        "icon":  "👥",
        "system_prompt": """You are based on social psychology principles from The Social Animal.

Interpret through:
- Social perception (how others interpret behavior)
- Attribution theory (intent vs assumption)
- Group dynamics and relationships
- Miscommunication patterns

Rules:
- Focus on interpersonal dynamics
- Explain both perspectives (you vs the other person)
- Be balanced and insightful"""
    }
]

# ─── Gemini helper ────────────────────────────
async def call_gemini(system_prompt: str, scenario: str, model: str = "gemini-2.0-flash-lite") -> str:
    m = genai.GenerativeModel(model)
    prompt = f"{system_prompt}\n\n---\n\nScenario:\n{scenario}"
    response = await asyncio.to_thread(m.generate_content, prompt)
    return response.text


# ─── Sub-node: run a single agent ─────────────
# IMPORTANT: Send() passes a dict that becomes this node's full state.
# We must include "scenario" explicitly in the Send payload (see fanout_agents).
async def run_agent_node(state: dict) -> dict:
    agent    = state["agent"]
    scenario = state["scenario"]  # ← was missing in original

    content = await call_gemini(agent["system_prompt"], scenario)

    return {
        "responses": [{
            "agent_key":  agent["key"],
            "agent_name": agent["name"],
            "book":       agent["book"],
            "content":    content,
            "color":      agent["color"],
            "icon":       agent["icon"],
        }]
    }


# ─── Router: fan out to all agents in parallel ─
def fanout_agents(state: CouncilState):
    """
    Send must include both 'agent' and 'scenario' because the sub-node
    receives an isolated state dict, not the full CouncilState.
    """
    return [
        Send("run_agent", {"agent": agent, "scenario": state["scenario"]})
        for agent in AGENT_DEFINITIONS
    ]


# ─── Node: optional single-agent baseline ─────
async def single_agent_node(state: CouncilState) -> dict:
    if state["mode"] != "compare":
        return {"single_agent_response": ""}

    content = await call_gemini(
        "You are a helpful, balanced AI assistant. Give thoughtful advice.",
        state["scenario"],
    )
    return {"single_agent_response": content}


# ─── Node: synthesize all responses ───────────
async def synthesis_node(state: CouncilState) -> dict:
    compiled = "\n\n".join(
        f"{r['agent_name']} ({r['book']}):\n{r['content']}"
        for r in state["responses"]
    )

    prompt = f"""You are the Council Synthesizer.

Produce:

**1. CONVERGENCE** — what all perspectives agree on
**2. PRODUCTIVE TENSIONS** — meaningful disagreements and why they matter
**3. FINAL RECOMMENDATION** — concrete, integrated wisdom

Scenario:
{state['scenario']}

Analyses:
{compiled}
"""

    # Use a more capable model for synthesis
    content = await call_gemini("You are a master synthesizer.", prompt, model="gemini-2.0-flash")
    return {"synthesis": content}


# ─── Build Graph ──────────────────────────────
def build_graph():
    builder = StateGraph(CouncilState)

    builder.add_node("single",    single_agent_node)
    builder.add_node("run_agent", run_agent_node)
    builder.add_node("synthesis", synthesis_node)

    builder.set_entry_point("single")

    # Fan out from single → all agents in parallel
    builder.add_conditional_edges("single", fanout_agents)

    # All agents converge → synthesis
    builder.add_edge("run_agent", "synthesis")
    builder.add_edge("synthesis", END)

    return builder.compile()


# ─── Public API ───────────────────────────────
async def run_council(scenario: str, mode: str = "multi") -> dict:
    graph = build_graph()
    return await graph.ainvoke({
        "scenario":              scenario,
        "mode":                  mode,
        "responses":             [],
        "synthesis":             "",
        "single_agent_response": "",
    })


def get_agent_definitions() -> list[dict]:
    """Return agent metadata without system_prompt (safe for frontend)."""
    return [
        {k: v for k, v in a.items() if k != "system_prompt"}
        for a in AGENT_DEFINITIONS
    ]