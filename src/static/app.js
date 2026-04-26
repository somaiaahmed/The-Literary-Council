const SCENARIOS = [
    "My friend says I’ve been distant and I reacted badly...",
    "My professor gave me a low grade and I feel it's unfair...",
    "My partner is upset I planned a solo trip without telling them..."
];

function loadScenario(i) {
    document.getElementById("scenario").value = SCENARIOS[i];

    document.querySelectorAll(".pill").forEach((p, idx) =>
        p.classList.toggle("active", idx === i)
    );
}

function formatText(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .split(/\n\n+/)
        .map(p => `<p>${p}</p>`)
        .join("");
}

async function analyze() {
    const scenario = document.getElementById("scenario").value.trim();
    const results = document.getElementById("results");

    if (!scenario) return;

    results.innerHTML = "Thinking...";

    const res = await fetch("/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, mode: "multi" })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";

    let agents = [];
    let synthesis = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by double newline
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();

        for (const chunk of chunks) {

            const lines = chunk.split("\n");

            let eventType = null;
            let dataStr = "";

            for (const line of lines) {
                if (line.startsWith("event:")) {
                    eventType = line.replace("event:", "").trim();
                }
                if (line.startsWith("data:")) {
                    dataStr += line.replace("data:", "").trim();
                }
            }

            if (!dataStr) continue;

            try {
                const data = JSON.parse(dataStr);

                if (eventType === "agent_result") {
                    agents.push(data);
                }

                if (eventType === "synthesis") {
                    synthesis = data.content;
                }

                render(agents, synthesis);

            } catch (e) {
                console.log("JSON parse failed:", dataStr);
            }
        }
    }
}