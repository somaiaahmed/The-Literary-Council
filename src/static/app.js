// ─── Scenario Presets ─────────────────────────
const SCENARIOS = [
    "My friend says I've been distant lately and when they brought it up, I reacted defensively and said some hurtful things. Now they're not responding to my messages.",
    "My professor gave me a significantly lower grade than I expected on my thesis. I feel the feedback was vague and the grading was unfair, but I don't want to seem like I'm just complaining.",
    "My partner found out I planned a solo trip without mentioning it to them first. They feel excluded and hurt, but I just wanted some personal space without making it a big conversation."
];

// ─── Agent color map (matches CSS vars) ───────
const AGENT_COLORS = {
    nvc: "#3d5a3e",
    kafka: "#5c4435",
    camus: "#4a5070",
    dostoevsky: "#6b2c10",
};

// ─── Load a preset scenario ───────────────────
function loadScenario(i) {
    const ta = document.getElementById("scenario");
    ta.value = SCENARIOS[i];
    updateCharCount();
    document.querySelectorAll(".pill").forEach((p, idx) =>
        p.classList.toggle("active", idx === i)
    );
}

// ─── Live char counter ─────────────────────────
function updateCharCount() {
    const val = document.getElementById("scenario").value.length;
    document.getElementById("charCount").textContent =
        `${val} character${val !== 1 ? "s" : ""}`;
}

document.addEventListener("DOMContentLoaded", () => {
    const ta = document.getElementById("scenario");
    if (ta) ta.addEventListener("input", updateCharCount);
});

// ─── Markdown-lite formatter ───────────────────
function formatText(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/##\s?(.+)/g, "<h3>$1</h3>")
        .replace(/###\s?(.+)/g, "<h4>$1</h4>")
        .split(/\n\n+/)
        .map(p => p.startsWith("<h") ? p : `<p>${p.replace(/\n/g, "<br>")}</p>`)
        .join("");
}

// ─── Build empty agent output cards ──────────
function initAgentCards(agents) {
    const grid = document.getElementById("agentGrid");
    grid.innerHTML = "";

    for (const a of agents) {
        const card = document.createElement("div");
        card.className = "agent-output-card";
        card.dataset.agent = a.agent_key;
        card.id = `agent-card-${a.agent_key}`;
        card.style.animationDelay = `${agents.indexOf(a) * 80}ms`;

        card.innerHTML = `
            <div class="agent-output-head">
                <div class="agent-status-dot loading" id="dot-${a.agent_key}"></div>
                <span class="agent-head-icon">${a.icon}</span>
                <div>
                    <div class="agent-head-name">${a.agent_name}</div>
                    <div class="agent-head-book">${a.book}</div>
                </div>
            </div>
            <div class="agent-output-body" id="body-${a.agent_key}">
                <div class="agent-thinking">Thinking…</div>
            </div>
        `;
        grid.appendChild(card);
    }
}

// ─── Fill a specific agent card ────────────────
function fillAgentCard(data) {
    const body = document.getElementById(`body-${data.agent_key}`);
    const dot = document.getElementById(`dot-${data.agent_key}`);

    if (body) body.innerHTML = formatText(data.content);
    if (dot) { dot.classList.remove("loading"); dot.classList.add("done"); }
}

// ─── Fill synthesis card ───────────────────────
function fillSynthesis(content) {
    const el = document.getElementById("synthesisContent");
    if (el) el.innerHTML = formatText(content);
}

// ─── Show / hide sections ──────────────────────
function showSection(id) { document.getElementById(id)?.classList.remove("hidden"); }
function hideSection(id) { document.getElementById(id)?.classList.add("hidden"); }

// ─── Main analyze function ────────────────────
async function analyze() {
    const scenario = document.getElementById("scenario").value.trim();
    if (!scenario) return;

    const btn = document.getElementById("analyzeBtn");
    const btnText = document.getElementById("btnText");
    btn.disabled = true;
    btnText.textContent = "Consulting…";

    // Reset UI
    hideSection("agentOutputs");
    hideSection("synthesisSection");
    document.getElementById("results").innerHTML = "";

    try {
        const res = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario, mode: "multi" })
        });

        if (!res.ok) {
            throw new Error(`Server error: ${res.status}`);
        }

        // Check if server returns SSE or plain JSON
        const contentType = res.headers.get("content-type") || "";

        if (contentType.includes("text/event-stream")) {
            await handleSSE(res);
        } else {
            // JSON fallback (current main.py returns JSON)
            const data = await res.json();
            handleJSON(data);
        }

    } catch (err) {
        console.error("Analysis failed:", err);
        document.getElementById("results").innerHTML =
            `<div class="loading">Error: ${err.message}</div>`;
    } finally {
        btn.disabled = false;
        btnText.textContent = "Consult the Council";
    }
}

// ─── Handle plain JSON response ───────────────
// (current main.py /analyze returns JSON, not SSE)
function handleJSON(data) {
    if (!data.responses?.length) return;

    // Build skeleton cards from first response to get agent info
    initAgentCards(data.responses);
    showSection("agentOutputs");
    showSection("synthesisSection");

    // Stagger card fills for effect
    data.responses.forEach((r, i) => {
        setTimeout(() => fillAgentCard(r), i * 200);
    });

    // Fill synthesis after agents
    if (data.synthesis) {
        setTimeout(() => fillSynthesis(data.synthesis), data.responses.length * 200 + 300);
    }
}

// ─── Handle SSE streaming response ────────────
// (upgrade main.py to StreamingResponse to use this path)
async function handleSSE(res) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let agentsInitialized = false;

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newline
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop(); // keep incomplete chunk

        for (const chunk of chunks) {
            const lines = chunk.split("\n");
            let eventType = null;
            let dataStr = "";

            for (const line of lines) {
                if (line.startsWith("event:")) {
                    eventType = line.replace("event:", "").trim();
                } else if (line.startsWith("data:")) {
                    dataStr += line.replace(/^data:\s?/, "");
                }
            }

            if (!dataStr) continue;

            try {
                const data = JSON.parse(dataStr);

                if (eventType === "init") {
                    // Server sends list of agent metadata upfront
                    initAgentCards(data.agents);
                    showSection("agentOutputs");
                    agentsInitialized = true;
                }

                if (eventType === "agent_result") {
                    if (!agentsInitialized) {
                        // Lazy init if no "init" event sent
                        initAgentCards([data]);
                        showSection("agentOutputs");
                        agentsInitialized = true;
                    }
                    fillAgentCard(data);
                }

                if (eventType === "synthesis") {
                    showSection("synthesisSection");
                    fillSynthesis(data.content);
                }

            } catch (e) {
                console.warn("SSE parse error:", e, "raw:", dataStr);
            }
        }
    }
}