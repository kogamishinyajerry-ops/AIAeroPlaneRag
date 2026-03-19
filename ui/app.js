/* ============================================
   AeroPower-RAG — Live Backend Integration
   Palantir-grade Traceability UI
   ============================================ */

// ==================== CONFIG ====================
const API_BASE_URL = "http://localhost:8000";

// ==================== DOM ====================
const chatContainer = document.getElementById("chatContainer");
const userInput = document.getElementById("userInput");
const drawerOverlay = document.getElementById("drawerOverlay");
const citationDrawer = document.getElementById("citationDrawer");
const drawerContent = document.getElementById("drawerContent");

let currentCitations = [];

// ==================== NAVIGATION ====================
document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", (e) => {
        e.preventDefault();
        const panel = item.dataset.panel;
        document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
        item.classList.add("active");
        document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
        const target = document.getElementById("panel" + panel.charAt(0).toUpperCase() + panel.slice(1));
        if (target) target.classList.add("active");

        const titles = { chat: "智能问答 · 适航规范检索", graph: "知识图谱 · 本体关系探索", docs: "文档库 · 数据源管理" };
        document.querySelector(".topbar-title").textContent = titles[panel] || "";
        if (panel === "graph") loadGraphFromNeo4j();
    });
});

document.getElementById("menuBtn").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
});

// ==================== CHAT — LIVE BACKEND ====================
function sendQuickPrompt(btn) {
    userInput.value = btn.textContent;
    sendMessage();
}

function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    const welcome = document.querySelector(".welcome-card");
    if (welcome) welcome.remove();

    appendMessage("user", text);
    userInput.value = "";
    autoResize();

    const loadingId = showLoading();

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: text, top_k: 5, use_guardrail: true })
        });

        removeLoading(loadingId);

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        handleResponse(data);
    } catch (err) {
        removeLoading(loadingId);
        appendMessage("assistant", `<div style="color:#ef4444;">⚠️ 后端连接失败: ${err.message}<br><small>请确认 FastAPI 正在 localhost:8000 运行</small></div>`);
    }
}

function appendMessage(role, content) {
    const msg = document.createElement("div");
    msg.className = `message ${role}`;
    const avatarText = role === "user" ? "👤" : "✦";
    msg.innerHTML = `
        <div class="msg-avatar">${avatarText}</div>
        <div class="msg-body">${content}</div>
    `;
    chatContainer.appendChild(msg);
    scrollToBottom();
}

function handleResponse(data) {
    currentCitations = data.citations || [];

    // Inject clickable citation refs into the answer text
    let answer = data.answer || "";
    // Replace [1], [2], etc. with clickable spans
    answer = answer.replace(/\[(\d+)\]/g, (match, num) => {
        return `<span class="citation-ref" onclick="openCitation(${num})">${num}</span>`;
    });

    // Add graph insight pills if present
    let graphHtml = "";
    if (data.graphInsights && data.graphInsights.length > 0) {
        graphHtml = '<div style="margin-top:12px">';
        data.graphInsights.slice(0, 5).forEach(g => {
            graphHtml += `<span class="graph-pill">🔗 ${g.regulation || '?'} → ${g.relationship || 'CONSTRAINS'} → ${g.component || '?'}</span> `;
        });
        graphHtml += '</div>';
    }

    const guardrail = data.guardrail || { status: "UNKNOWN", reasoning: "" };
    const guardrailClass = guardrail.status === "PASS" ? "pass" : "fail";
    const guardrailIcon = guardrail.status === "PASS" ? "🛡️" : "⚠️";
    const guardrailLabel = guardrail.status === "PASS" ? "Guardrail 验证通过" : `Guardrail: ${guardrail.status}`;

    const msg = document.createElement("div");
    msg.className = "message assistant";
    msg.innerHTML = `
        <div class="msg-avatar">✦</div>
        <div class="msg-body">
            <div class="answer-text">${answer}</div>
            ${graphHtml}
            <div class="msg-guardrail ${guardrailClass}">
                ${guardrailIcon} ${guardrailLabel} — ${guardrail.reasoning || ''}
            </div>
        </div>
    `;
    chatContainer.appendChild(msg);
    scrollToBottom();
}

function showLoading() {
    const id = "loading-" + Date.now();
    const msg = document.createElement("div");
    msg.className = "message assistant";
    msg.id = id;
    msg.innerHTML = `
        <div class="msg-avatar">✦</div>
        <div class="msg-body">
            <div class="loading-dots"><span></span><span></span><span></span></div>
            <div style="font-size:12px;color:#9ca3af;margin-top:8px;">正在检索向量库 + 遍历知识图谱 + GLM 生成中...</div>
        </div>
    `;
    chatContainer.appendChild(msg);
    scrollToBottom();
    return id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: "smooth" });
}

// ==================== CITATION DRAWER ====================
function openCitation(num) {
    const citation = currentCitations.find(c => c.num === num);
    if (!citation) return;

    drawerContent.innerHTML = "";

    const block = document.createElement("div");
    block.className = "citation-block";
    block.innerHTML = `
        <div class="citation-block-header">
            <span class="citation-num">${citation.num}</span>
            <span class="citation-source">${citation.source}</span>
        </div>
        <div class="citation-path">${citation.chapter} > ${citation.section}</div>
        <div class="citation-text">
            ${citation.snippet.replace(citation.highlight, `<span class="highlight">${citation.highlight}</span>`)}
        </div>
    `;
    drawerContent.appendChild(block);

    drawerOverlay.classList.add("open");
    citationDrawer.classList.add("open");
}

function closeDrawer() {
    drawerOverlay.classList.remove("open");
    citationDrawer.classList.remove("open");
}

// ==================== TEXTAREA AUTO RESIZE ====================
userInput.addEventListener("input", autoResize);
function autoResize() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
}

// ==================== GRAPH VISUALIZATION — LIVE NEO4J ====================
async function loadGraphFromNeo4j() {
    const viz = document.getElementById("graphViz");
    viz.innerHTML = '<div style="text-align:center;padding:40px;color:#9ca3af;">加载知识图谱中...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/graph/nodes`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderLiveGraph(data.nodes, data.edges);
    } catch (err) {
        viz.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;">加载图谱失败: ${err.message}</div>`;
    }
}

function renderLiveGraph(nodes, edges) {
    const viz = document.getElementById("graphViz");
    viz.innerHTML = "";

    if (!nodes.length) {
        viz.innerHTML = '<div style="text-align:center;padding:40px;color:#9ca3af;">图谱为空</div>';
        return;
    }

    const width = viz.clientWidth || 500;
    const height = viz.clientHeight || 400;

    // Force-directed layout simulation (simple)
    const positions = {};
    const typeGroups = {};
    nodes.forEach((n, i) => {
        const type = n.type || "unknown";
        if (!typeGroups[type]) typeGroups[type] = [];
        typeGroups[type].push(n);
    });

    // Arrange nodes by type in clusters
    const types = Object.keys(typeGroups);
    types.forEach((type, ti) => {
        const group = typeGroups[type];
        const cx = (width / (types.length + 1)) * (ti + 1);
        group.forEach((n, ni) => {
            const angle = (2 * Math.PI * ni) / group.length;
            const radius = Math.min(80, 30 + group.length * 10);
            positions[n.id] = {
                x: cx + radius * Math.cos(angle) - 40,
                y: 40 + (height - 80) * (ni / Math.max(group.length - 1, 1))
            };
        });
    });

    // Draw edges
    edges.forEach(edge => {
        const from = positions[edge.source];
        const to = positions[edge.target];
        if (!from || !to) return;

        const line = document.createElement("div");
        line.className = "graph-edge";
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;

        line.style.left = (from.x + 40) + "px";
        line.style.top = (from.y + 14) + "px";
        line.style.width = length + "px";
        line.style.transform = `rotate(${angle}deg)`;
        line.title = `${edge.type}: ${edge.description || ''}`;
        viz.appendChild(line);
    });

    // Draw nodes
    nodes.forEach(node => {
        const pos = positions[node.id];
        if (!pos) return;

        const el = document.createElement("div");
        el.className = `graph-node ${node.type}`;
        el.textContent = node.label || node.id;
        el.style.left = pos.x + "px";
        el.style.top = pos.y + "px";
        el.title = node.description || node.label;
        viz.appendChild(el);
    });
}

// ==================== HEALTH CHECK ON LOAD ====================
document.addEventListener("DOMContentLoaded", async () => {
    userInput.focus();

    // Check backend health
    try {
        const resp = await fetch(`${API_BASE_URL}/api/v1/health`);
        if (resp.ok) {
            const health = await resp.json();
            const dot = document.querySelector(".status-dot");
            const text = document.querySelector(".status-text");
            dot.style.background = "#22c55e";
            dot.style.boxShadow = "0 0 6px #22c55e";
            const parts = [];
            if (health.vector_db === "connected") parts.push("向量库");
            if (health.graph_db === "connected") parts.push("图谱库");
            if (health.llm === "connected") parts.push("GLM");
            text.textContent = parts.length ? `已连接: ${parts.join(" · ")}` : "系统就绪";
        }
    } catch (e) {
        const dot = document.querySelector(".status-dot");
        const text = document.querySelector(".status-text");
        dot.style.background = "#ef4444";
        text.textContent = "后端离线";
    }
});
