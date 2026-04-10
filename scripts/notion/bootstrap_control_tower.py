"""
AIAeroPlaneRag — Notion 控制塔 Bootstrap
========================================

一次性脚本：在 Notion 工作区里创建 AIAeroPlaneRag 的控制中枢子树。

设计原则（借鉴 AI-Harness v2）：
  1. Repo 是代码 / 契约 / canonical 文档的唯一真相源
  2. Notion 只承载 phases / tasks / sessions / decisions / docs index / prompts
  3. 每次会话：先读状态 → 执行 → 回写摘要
  4. 与 AI-Harness v1/v2 完全隔离：独立父页面、独立数据库、独立 schema

运行方式：
    cd ~/AIAeroPlaneRag
    python scripts/notion/bootstrap_control_tower.py

需要环境变量（已配在 .env）：
    NOTION_API_KEY
    NOTION_VERSION  (可选, 默认 2022-06-28)

输出：
    scripts/notion/control_tower_ids.json  —— 所有创建出来的 page_id / db_id
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")

if not NOTION_API_KEY:
    sys.exit("❌ NOTION_API_KEY 未设置")

BASE = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

# v1 根页面作为临时挂载点（v2 文档已将 v1 标记为 reference-only）。
# 用户将在创建后手动把新顶层页面移动到 workspace 根。
TEMP_PARENT_PAGE_ID = "bfa9836d-535b-486f-8297-c5b2f9ed487c"

IDS_OUT = Path(__file__).parent / "control_tower_ids.json"


def _post(path: str, payload: dict) -> dict:
    r = requests.post(f"{BASE}{path}", headers=HEADERS, json=payload, timeout=30)
    if r.status_code >= 300:
        print("❌", path, r.status_code, r.text)
        r.raise_for_status()
    return r.json()


def _patch(path: str, payload: dict) -> dict:
    r = requests.patch(f"{BASE}{path}", headers=HEADERS, json=payload, timeout=30)
    if r.status_code >= 300:
        print("❌ PATCH", path, r.status_code, r.text)
        r.raise_for_status()
    return r.json()


# ------------------------- helpers -------------------------

def rich(text: str) -> list:
    return [{"type": "text", "text": {"content": text}}]


def h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": rich(text)}}


def h3(text: str) -> dict:
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": rich(text)}}


def para(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": rich(text)}}


def bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rich(text)}}


def callout(text: str, emoji: str = "🧭") -> dict:
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": rich(text),
                        "icon": {"type": "emoji", "emoji": emoji}}}


def code(text: str, language: str = "plain text") -> dict:
    return {"object": "block", "type": "code",
            "code": {"rich_text": rich(text), "language": language}}


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def create_page(parent_id: str, title: str, children: list | None = None,
                icon: str | None = None) -> str:
    payload: dict[str, Any] = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": rich(title)}},
    }
    if icon:
        payload["icon"] = {"type": "emoji", "emoji": icon}
    if children:
        payload["children"] = children[:100]
    result = _post("/pages", payload)
    pid = result["id"]
    # overflow children
    if children and len(children) > 100:
        for i in range(100, len(children), 100):
            _patch(f"/blocks/{pid}/children",
                   {"children": children[i:i + 100]})
            time.sleep(0.2)
    return pid


def create_db(parent_page_id: str, title: str, properties: dict,
              icon: str | None = None) -> str:
    payload: dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": rich(title),
        "properties": properties,
        "is_inline": True,
    }
    if icon:
        payload["icon"] = {"type": "emoji", "emoji": icon}
    result = _post("/databases", payload)
    return result["id"]


def add_row(db_id: str, props: dict) -> str:
    result = _post("/pages",
                   {"parent": {"database_id": db_id}, "properties": props})
    return result["id"]


# ------------------------- schemas -------------------------

PHASES_SCHEMA = {
    "Name": {"title": {}},
    "Status": {"select": {"options": [
        {"name": "Planned", "color": "gray"},
        {"name": "Active", "color": "green"},
        {"name": "Blocked", "color": "red"},
        {"name": "Done", "color": "blue"},
    ]}},
    "Priority": {"select": {"options": [
        {"name": "P0", "color": "red"},
        {"name": "P1", "color": "orange"},
        {"name": "P2", "color": "yellow"},
        {"name": "Phase3+", "color": "purple"},
    ]}},
    "Context Pack": {"rich_text": {}},
    "Exit Criteria": {"rich_text": {}},
    "Owner": {"rich_text": {}},
    "Started": {"date": {}},
    "Target": {"date": {}},
}

TASKS_SCHEMA = {
    "Name": {"title": {}},
    "Status": {"select": {"options": [
        {"name": "Backlog", "color": "gray"},
        {"name": "Ready", "color": "default"},
        {"name": "In Progress", "color": "yellow"},
        {"name": "Review", "color": "orange"},
        {"name": "Done", "color": "green"},
        {"name": "Blocked", "color": "red"},
    ]}},
    "Priority": {"select": {"options": [
        {"name": "P0", "color": "red"},
        {"name": "P1", "color": "orange"},
        {"name": "P2", "color": "yellow"},
    ]}},
    "Area": {"select": {"options": [
        {"name": "Retrieval", "color": "blue"},
        {"name": "Guardrail", "color": "red"},
        {"name": "Multi-Agent", "color": "purple"},
        {"name": "API/Infra", "color": "gray"},
        {"name": "Eval/Bench", "color": "green"},
        {"name": "UI/E2E", "color": "pink"},
        {"name": "Graph/Neo4j", "color": "yellow"},
        {"name": "Docs/Process", "color": "default"},
    ]}},
    "Acceptance": {"rich_text": {}},
    "GitHub Issue": {"url": {}},
    "Commit/PR": {"url": {}},
    "Notes": {"rich_text": {}},
}

SESSIONS_SCHEMA = {
    "Name": {"title": {}},
    "Date": {"date": {}},
    "Model": {"select": {"options": [
        {"name": "Opus 4.6", "color": "purple"},
        {"name": "Sonnet 4.6", "color": "blue"},
        {"name": "Haiku 4.5", "color": "green"},
        {"name": "Other", "color": "gray"},
    ]}},
    "Type": {"select": {"options": [
        {"name": "Plan", "color": "yellow"},
        {"name": "Implement", "color": "green"},
        {"name": "Debug", "color": "red"},
        {"name": "Review", "color": "orange"},
        {"name": "Benchmark", "color": "blue"},
        {"name": "Docs", "color": "gray"},
    ]}},
    "Entry Prompt": {"rich_text": {}},
    "Handoff Summary": {"rich_text": {}},
    "Touched Files": {"rich_text": {}},
    "Commit": {"url": {}},
}

DECISIONS_SCHEMA = {
    "Name": {"title": {}},
    "Status": {"select": {"options": [
        {"name": "Open", "color": "yellow"},
        {"name": "Decided", "color": "green"},
        {"name": "Superseded", "color": "gray"},
        {"name": "Rejected", "color": "red"},
    ]}},
    "Area": {"select": {"options": [
        {"name": "Architecture", "color": "purple"},
        {"name": "Retrieval", "color": "blue"},
        {"name": "Eval", "color": "green"},
        {"name": "Infra", "color": "gray"},
        {"name": "Process", "color": "default"},
    ]}},
    "Context": {"rich_text": {}},
    "Decision": {"rich_text": {}},
    "Consequences": {"rich_text": {}},
    "Decided On": {"date": {}},
}

DOCS_SCHEMA = {
    "Name": {"title": {}},
    "Type": {"select": {"options": [
        {"name": "Canonical", "color": "red"},
        {"name": "Plan", "color": "orange"},
        {"name": "Eval", "color": "green"},
        {"name": "Research", "color": "blue"},
        {"name": "Ops", "color": "gray"},
    ]}},
    "Repo Path": {"rich_text": {}},
    "GitHub URL": {"url": {}},
    "Summary": {"rich_text": {}},
    "Last Synced": {"date": {}},
}

PROMPTS_SCHEMA = {
    "Name": {"title": {}},
    "Scenario": {"select": {"options": [
        {"name": "Startup/Restore", "color": "red"},
        {"name": "Plan Phase", "color": "orange"},
        {"name": "Implement Task", "color": "green"},
        {"name": "Review/Audit", "color": "blue"},
        {"name": "Debug Incident", "color": "yellow"},
        {"name": "Benchmark", "color": "purple"},
        {"name": "Docs Writing", "color": "gray"},
    ]}},
    "Status": {"select": {"options": [
        {"name": "Draft", "color": "gray"},
        {"name": "Active", "color": "green"},
        {"name": "Archived", "color": "default"},
    ]}},
    "Body": {"rich_text": {}},
    "Use Count": {"number": {"format": "number"}},
    "Last Used": {"date": {}},
}


# ------------------------- main bootstrap -------------------------

FIXED_STARTUP_PROMPT = """请从 Notion 开发中枢 AIAeroPlaneRag Control Tower 恢复当前上下文，按以下顺序执行：
1. 读取 Current Phase 里 Status=Active 的那一行，拿到 Context Pack、Exit Criteria。
2. 读取 Active Session（最新一行 Status=In Progress 或最新 Date），拿到上次 Handoff Summary 和 Touched Files。
3. 读取 Next Tasks 里 Priority=P0 且 Status∈{Ready,In Progress} 的前 3 条，拿到 Name 和 Acceptance。
4. 读取 Open Decisions 里 Status=Open 的全部行，评估是否阻塞当前任务。
5. 读取 Pinned Canonical Docs 里 Type=Canonical 的条目作为背景知识索引（不要复制全文）。
6. 输出一段不超过 200 字的"当前上下文简报"，然后询问我今天要推进哪个任务。
7. 执行完成后，把本次会话写回 Sessions 表（Name / Date / Model / Type / Entry Prompt / Handoff Summary / Touched Files / Commit），并把相关 Task 更新到新的 Status。

硬约束：
- 永远不要把 canonical 源码或长日志写进 Notion，只写摘要和 GitHub 链接。
- 任何写操作之前，先对照 Automation Scope Registry 确认目标表在允许的写入边界内。
- 不要触碰 AI-Harness 控制塔 v1 / v2 的任何数据库或页面。
"""


def build_root_children() -> list:
    return [
        callout(
            "AIAeroPlaneRag 控制塔 — 航空发动机适航法规 RAG 项目的 Notion 管控中枢。"
            "借鉴 AI-Harness v2 的 repo-first 思路，与 v1/v2 完全隔离。",
            emoji="🛫",
        ),
        divider(),
        h2("0. 定位"),
        bullet("这是 AIAeroPlaneRag 独立的父页面，不复用 AI-Harness v1/v2 的任何数据库。"),
        bullet("Repo (github.com/kogamishinyajerry-ops/AIAeroPlaneRag) 继续作为代码、契约、canonical docs 的真相源。"),
        bullet("Notion 只承载 phases / tasks / sessions / decisions / doc index / prompts。"),
        h2("1. 核心原则（继承自 AI-Harness v2）"),
        bullet("Notion 负责 Control Plane，不是代码真相源。"),
        bullet("每次 Claude 会话：先读状态 → 执行 → 回写摘要。"),
        bullet("长日志、原始产物、源码、diff 不进入 Notion 主存储。"),
        bullet("决策、阶段、任务、会话都必须可追溯，全部 append-only。"),
        h2("2. 隔离边界"),
        bullet("本子树不读写 AI-Harness v1 / v2 的任何数据库。"),
        bullet("新的 schema、relations、views 都在 AIAeroPlaneRag 子树内。"),
        bullet("GitHub 写入范围仅限 kogamishinyajerry-ops/AIAeroPlaneRag。"),
        h2("3. 安全入口"),
        bullet("开工/收工前，先打开 Automation Operations。"),
        bullet("任何写入动作先对照 Automation Scope Registry。"),
        bullet("只有写入边界清晰后，才进入 AeroPower RAG OS 执行会话恢复和状态更新。"),
        h2("4. 入口"),
        bullet("下方子页是 AeroPower RAG OS — 每日会话从这里进入。"),
        bullet("Current Phase → Active Session → Next Tasks → Open Decisions → Pinned Canonical Docs → Prompts Library。"),
        divider(),
        callout(
            "⚠️ 临时位置：本页当前位于 AI-Harness 控制塔 v1 之下（v1 已被 v2 标记为 reference-only）。"
            "请手动把本页拖到 workspace 根层，或移动到任意不属于 v1/v2 的顶层位置。",
            emoji="🚧",
        ),
    ]


def build_os_children(db_ids: dict[str, str]) -> list:
    return [
        h2("Overview"),
        bullet("Repo 是代码、契约、canonical 文档的真相源。"),
        bullet("Notion 是 phases / tasks / sessions / decisions / docs 的运行中枢。"),
        bullet("启动上下文来自结构化记录，而不是重复复制长 prompt。"),
        h2("Fixed Startup Prompt（复制这段作为每次会话的第一条消息）"),
        code(FIXED_STARTUP_PROMPT, "plain text"),
        h2("Operating Rules"),
        bullet("不要把 canonical 文档全文复制进 Notion；只存摘要和 GitHub 链接。"),
        bullet("每个 Phase 拥有 300-500 字的 Context Pack。"),
        bullet("每次 Session 只继承：phase context + 上次 handoff + 当前 task acceptance + pinned docs 索引。"),
        bullet("历史 Session append-only，不因 canonical 文档更新而重写。"),
        h2("Home Surfaces"),
        para("以下 6 个数据库是 AeroPower RAG OS 的主表面。每次会话严格按顺序读取。"),
        para(f"Phases DB: {db_ids['phases']}"),
        para(f"Sessions DB: {db_ids['sessions']}"),
        para(f"Tasks DB: {db_ids['tasks']}"),
        para(f"Decisions DB: {db_ids['decisions']}"),
        para(f"Docs DB: {db_ids['docs']}"),
        para(f"Prompts DB: {db_ids['prompts']}"),
        h2("Governance & Operations"),
        bullet("任何写工作流从 Automation Operations 启动。"),
        bullet("每次写 Notion 前先对照 Automation Scope Registry 校验目标表。"),
        bullet("把 AI-Harness v1/v2 视为完全隔离的参考系，不读不写。"),
    ]


def build_automation_ops_children() -> list:
    return [
        h2("Automation Operations"),
        para("本页是所有自动化写入的安全入口。每次要让 Claude 写 Notion / GitHub 之前，在这里确认：写什么、写到哪、回滚路径。"),
        h2("Pre-Write Checklist"),
        bullet("目标数据库是否在 Automation Scope Registry 的 ALLOW 列表内？"),
        bullet("目标 GitHub repo 是否等于 kogamishinyajerry-ops/AIAeroPlaneRag？"),
        bullet("本次会话的 Entry Prompt 是否已写入 Sessions 表？"),
        bullet("完成后是否有 Handoff Summary 回写计划？"),
        h2("Post-Write Checklist"),
        bullet("Sessions 表是否已追加新行（含 Commit 链接）？"),
        bullet("相关 Task 状态是否已更新？"),
        bullet("如果触发了决策，是否已在 Decisions 表建了行？"),
        h2("Recovery Script"),
        para("若 Notion 状态与 repo 发生分歧：以 repo 为准，把分歧记录到一条新的 Decision，状态 Open，等待人工裁决。"),
    ]


def build_governance_children() -> list:
    return [
        h2("Isolation Governance Rules"),
        bullet("AIAeroPlaneRag 控制塔 子树 与 AI-Harness v1/v2 完全隔离。"),
        bullet("禁止读取 AI-Harness v1/v2 数据库作为 AIAeroPlaneRag 任务的上下文。"),
        bullet("禁止跨子树 relation，所有 database relation 必须指向本子树内的数据库。"),
        bullet("GitHub 写入权限仅限 kogamishinyajerry-ops/AIAeroPlaneRag；其它 repo 一律只读。"),
        bullet("每个 Claude 会话启动时必须先读取本页，再执行 Fixed Startup Prompt。"),
        h2("Violation Handling"),
        bullet("发现违规写入：立即在 Decisions 建立 Incident 记录，停止当前会话。"),
        bullet("由人工决定回滚或继续。"),
    ]


def build_scope_registry_children(db_ids: dict[str, str]) -> list:
    allowed = [
        ("Phases", db_ids["phases"]),
        ("Sessions", db_ids["sessions"]),
        ("Tasks", db_ids["tasks"]),
        ("Decisions", db_ids["decisions"]),
        ("Docs", db_ids["docs"]),
        ("Prompts", db_ids["prompts"]),
    ]
    children = [
        h2("Automation Scope Registry"),
        para("Claude 或任何自动化只能对下列数据库/仓库进行写入。新增写入目标前必须先更新本页并在 Decisions 表建 ADR。"),
        h3("ALLOW — Notion"),
    ]
    for name, db_id in allowed:
        children.append(bullet(f"{name}  ({db_id})"))
    children += [
        h3("ALLOW — GitHub"),
        bullet("kogamishinyajerry-ops/AIAeroPlaneRag  (issues / PR / commits)"),
        h3("DENY"),
        bullet("AI-Harness 控制塔 v1 下的任何数据库或页面"),
        bullet("AI-Harness 控制塔 v2 下的任何数据库或页面"),
        bullet("其它 GitHub repo"),
    ]
    return children


# ------------------------- seed data -------------------------

def seed_phases(db_id: str) -> dict[str, str]:
    rows = [
        {
            "name": "v0.2 硬化 (当前)",
            "status": "Active",
            "priority": "P0",
            "context": "v0.1.0 已发布，当前重点是 Guardrail JSON 解析稳定性、意图检测基准验证、BM25 跨语言召回验证、/health 完整性。Repo 分支 codex/v0.1.0-initial-release。",
            "exit": "Guardrail JSON 解析失败率<5%；意图准确率≥80%；BM25 中→英 recall@3≥0.6；/health 通过。",
        },
        {
            "name": "v0.3 扩展",
            "status": "Planned",
            "priority": "P1",
            "context": "黄金集扩展≥20；性能基准自动化 P95<2000ms；UI E2E 5 条关键路径。",
            "exit": "CI 回归绿；benchmarks 自动化产物进 repo。",
        },
        {
            "name": "v0.4 图谱真实接入",
            "status": "Planned",
            "priority": "P2",
            "context": "Neo4j 从 mock 换成真实；7 维置信度量化。",
            "exit": "graph_store.py 接真实 Neo4j；回归集不退化。",
        },
        {
            "name": "Phase 3 图谱虚拟化",
            "status": "Planned",
            "priority": "Phase3+",
            "context": "视口裁剪 + LOD 三级标签。",
            "exit": "前端可流畅展示 10k 节点图。",
        },
    ]
    ids = {}
    for r in rows:
        props = {
            "Name": {"title": rich(r["name"])},
            "Status": {"select": {"name": r["status"]}},
            "Priority": {"select": {"name": r["priority"]}},
            "Context Pack": {"rich_text": rich(r["context"])},
            "Exit Criteria": {"rich_text": rich(r["exit"])},
        }
        ids[r["name"]] = add_row(db_id, props)
    return ids


def seed_tasks(db_id: str) -> None:
    tasks = [
        ("Guardrail JSON 解析失败率 < 5%", "P0", "Guardrail", "In Progress",
         "失败率指标跑 100 次采样，失败<5 次；失败样本写回 decisions."),
        ("意图检测准确率 >= 80% 基准验证", "P0", "Eval/Bench", "Ready",
         "evaluation/intent_accuracy_bench.py 跑完 30 题，准确率≥80%."),
        ("BM25 中→英 recall@3 >= 0.6", "P0", "Retrieval", "Ready",
         "cross_lingual_bench 25 题，recall@3 ≥ 0.6 并在 benchmarks 目录出报告."),
        ("API /health 完整性修复", "P0", "API/Infra", "Ready",
         "/health 返回 vector、llm、ollama、chroma 四项 status，E2E 绿."),
        ("黄金集扩展至 >= 20 题", "P1", "Eval/Bench", "Backlog",
         "evaluation/golden_set_sample.json 至少 20 题，覆盖 CCAR/FAR/CS-E."),
        ("性能基准自动化 P95 < 2000ms", "P1", "Eval/Bench", "Backlog",
         "benchmarks pytest 运行，P95<2000ms，失败阈值入 CI."),
        ("UI E2E 5 条关键路径覆盖", "P1", "UI/E2E", "Backlog",
         "Playwright 5 条 spec，CI 全绿."),
        ("Neo4j 真实接入替换 mock", "P2", "Graph/Neo4j", "Backlog",
         "graph_store.py 接 bolt://；docker-compose 启动通过."),
        ("置信度评分 7 维度量化", "P2", "Guardrail", "Backlog",
         "confidence_score 返回 7 维度 + 汇总 + 解释."),
        ("89 个未追踪文件 commit 入库", "P0", "Docs/Process", "Ready",
         "多代理系统 27 模块、民航术语、路由 全部提交到 codex/v0.1.0-initial-release."),
    ]
    for name, prio, area, status, acc in tasks:
        add_row(db_id, {
            "Name": {"title": rich(name)},
            "Priority": {"select": {"name": prio}},
            "Area": {"select": {"name": area}},
            "Status": {"select": {"name": status}},
            "Acceptance": {"rich_text": rich(acc)},
        })


def seed_decisions(db_id: str) -> None:
    decisions = [
        ("使用 ChromaDB + Ollama nomic-embed-text (768d) 作为向量栈",
         "Decided", "Architecture",
         "v0.1 初版需要本地可跑的 RAG 栈，Ollama 本地嵌入稳定，ChromaDB 部署简单。",
         "锁定 ChromaDB 作为向量库，Ollama nomic-embed-text 作为 embedding。",
         "本地依赖 Ollama 可用；未来切换需重建向量集合。"),
        ("BM25 使用 bigram + 同义词扩展",
         "Decided", "Retrieval",
         "中英跨语言召回在 unigram 上偏低。",
         "BM25 采用 bigram 切分 + 民航术语词典 150+ 同义词扩展。",
         "recall@3 从 <60% 升到 100%（25 题集合）。"),
        ("Neo4j 真实接入延后到 v0.4",
         "Decided", "Infra",
         "v0.2 硬化阶段更关注 Guardrail 和评测稳定性，图谱接入涉及 Docker/鉴权，风险大。",
         "graph_store.py 继续 mock 到 v0.4。",
         "现阶段图谱洞察为占位数据；v0.4 需投入 3-5 天完成切换。"),
    ]
    for name, status, area, ctx, dec, cons in decisions:
        add_row(db_id, {
            "Name": {"title": rich(name)},
            "Status": {"select": {"name": status}},
            "Area": {"select": {"name": area}},
            "Context": {"rich_text": rich(ctx)},
            "Decision": {"rich_text": rich(dec)},
            "Consequences": {"rich_text": rich(cons)},
        })


def seed_docs(db_id: str) -> None:
    docs = [
        ("CLAUDE.md", "Canonical", "CLAUDE.md",
         "项目根上下文，包含目标/架构/命令/进度/关键文件/风险。每次会话第一手参考。"),
        ("DEVELOPMENT_PLAN.md", "Plan", "docs/DEVELOPMENT_PLAN.md",
         "4 阶段开发计划，滞后于代码，需与 Notion Phases 对齐后再更新。"),
        ("golden_set_sample.json", "Eval", "evaluation/golden_set_sample.json",
         "黄金集测试用例，当前 <20，扩展任务在 Tasks 表 P1。"),
        ("src/main.py", "Canonical", "src/main.py",
         "FastAPI 主应用 84KB。重构计划在 Decisions 表。"),
        ("src/rag/vector_engine.py", "Canonical", "src/rag/vector_engine.py",
         "向量检索引擎，ChromaDB + Ollama 嵌入。"),
        ("src/rag/guardrail.py", "Canonical", "src/rag/guardrail.py",
         "事实核查护栏，JSON 解析脆弱是当前 P0 问题。"),
    ]
    repo_base = "https://github.com/kogamishinyajerry-ops/AIAeroPlaneRag/blob/codex/v0.1.0-initial-release"
    for name, typ, path, summary in docs:
        add_row(db_id, {
            "Name": {"title": rich(name)},
            "Type": {"select": {"name": typ}},
            "Repo Path": {"rich_text": rich(path)},
            "GitHub URL": {"url": f"{repo_base}/{path}"},
            "Summary": {"rich_text": rich(summary)},
        })


def seed_prompts(db_id: str) -> None:
    prompts = [
        ("Fixed Startup — 每次会话第一条", "Startup/Restore", "Active",
         FIXED_STARTUP_PROMPT),
        ("Plan Next Phase — 规划下一阶段",
         "Plan Phase", "Active",
         "我现在要规划 AIAeroPlaneRag 的下一个 Phase。请先从 Notion 读取 Current Phase、Open Decisions、Tasks 里 Status=Done 的近 10 条，"
         "然后提出一个 300-500 字的 Context Pack 草稿 + Exit Criteria，列出候选 P0/P1 任务。"
         "不要直接写入 Notion，先让我确认。"),
        ("Implement Task — 执行单任务",
         "Implement Task", "Active",
         "我要执行 Task: <TASK_NAME>。请按以下顺序：1) 从 Notion 读取该 Task 的 Acceptance; "
         "2) 读取同 Area 的近 5 条 Sessions 的 Handoff Summary; 3) 读取相关 canonical docs (只读索引); "
         "4) 给出实现计划并列出要修改的文件; 5) 等我确认后开始写代码; 6) 完成后回写 Session + 更新 Task Status + 贴 commit 链接。"),
        ("Debug Incident — 事故调试",
         "Debug Incident", "Active",
         "出现事故：<DESCRIBE>。请：1) 在 Decisions 建 Incident 行 (Status=Open); 2) 读取最近 5 条 Sessions 找相关改动; "
         "3) 给出复现步骤、根因假设、修复方案; 4) 修复完成后补 postmortem 到 Decision 的 Consequences 字段。"),
        ("Benchmark Run — 跑基准",
         "Benchmark", "Active",
         "跑 benchmarks：<WHICH>。请：1) 确认 benchmarks 脚本路径; 2) 运行并捕获指标; "
         "3) 写入 Sessions (Type=Benchmark); 4) 若超过阈值，在 Decisions 建行; 5) 贴结果链接到相关 Task。"),
        ("Docs Writing — 文档更新",
         "Docs Writing", "Active",
         "更新文档：<DOC>。请：1) 读取 Docs 表定位 Repo Path; 2) 不要把长文档复制进 Notion，只在 Docs 表更新 Summary + Last Synced; "
         "3) 实际内容改动走 repo PR。"),
    ]
    for name, scenario, status, body in prompts:
        add_row(db_id, {
            "Name": {"title": rich(name)},
            "Scenario": {"select": {"name": scenario}},
            "Status": {"select": {"name": status}},
            "Body": {"rich_text": rich(body[:1900])},
            "Use Count": {"number": 0},
        })


def seed_initial_session(db_id: str) -> None:
    add_row(db_id, {
        "Name": {"title": rich("2026-04-10 Control Tower Bootstrap")},
        "Date": {"date": {"start": "2026-04-10"}},
        "Model": {"select": {"name": "Opus 4.6"}},
        "Type": {"select": {"name": "Docs"}},
        "Entry Prompt": {"rich_text": rich(
            "在 Notion 里搭建 AIAeroPlaneRag 的管控中枢，借鉴 AI-Harness v2 思路，不干涉 v1/v2。")},
        "Handoff Summary": {"rich_text": rich(
            "创建 AIAeroPlaneRag 控制塔父页 + 5 个子页 (AeroPower RAG OS / Automation Operations / "
            "Isolation Governance Rules / Automation Scope Registry / History)，6 个核心数据库 "
            "(Phases/Tasks/Sessions/Decisions/Docs/Prompts) 并填入种子数据。"
            "下一步：让用户手动把父页移到 workspace 根，并核实 GitHub repo。")},
        "Touched Files": {"rich_text": rich(
            "scripts/notion/bootstrap_control_tower.py; scripts/notion/control_tower_ids.json; "
            "docs/NOTION_CONTROL_TOWER.md; .env")},
    })


# ------------------------- run -------------------------

def main() -> None:
    print("➡️  在 Notion 里创建 AIAeroPlaneRag 控制塔 ...")

    # 1) root page
    root_id = create_page(
        TEMP_PARENT_PAGE_ID,
        "AIAeroPlaneRag 控制塔 (移动到 workspace 根)",
        children=build_root_children(),
        icon="🛫",
    )
    print(f"  ✅ root page: {root_id}")

    # 2) AeroPower RAG OS page (placeholder, we fill children after dbs)
    os_id = create_page(root_id, "AeroPower RAG OS", icon="🧭")
    print(f"  ✅ OS page: {os_id}")

    # 3) databases inside OS page
    db_ids = {
        "phases": create_db(os_id, "Phases", PHASES_SCHEMA, "🗺️"),
        "sessions": create_db(os_id, "Sessions", SESSIONS_SCHEMA, "📓"),
        "tasks": create_db(os_id, "Tasks", TASKS_SCHEMA, "✅"),
        "decisions": create_db(os_id, "Decisions", DECISIONS_SCHEMA, "⚖️"),
        "docs": create_db(os_id, "Pinned Canonical Docs", DOCS_SCHEMA, "📚"),
        "prompts": create_db(os_id, "Prompts Library", PROMPTS_SCHEMA, "💬"),
    }
    for k, v in db_ids.items():
        print(f"  ✅ db {k}: {v}")

    # 4) append OS page governance content
    _patch(f"/blocks/{os_id}/children",
           {"children": build_os_children(db_ids)})

    # 5) governance subpages
    auto_id = create_page(root_id, "Automation Operations",
                          children=build_automation_ops_children(), icon="🛡️")
    gov_id = create_page(root_id, "Isolation Governance Rules",
                         children=build_governance_children(), icon="🚧")
    scope_id = create_page(root_id, "Automation Scope Registry",
                           children=build_scope_registry_children(db_ids),
                           icon="📋")
    hist_id = create_page(root_id, "History - Bootstrap Log",
                          children=[para("2026-04-10: Bootstrap via scripts/notion/bootstrap_control_tower.py.")],
                          icon="🗂️")
    print(f"  ✅ auto ops: {auto_id}")
    print(f"  ✅ governance: {gov_id}")
    print(f"  ✅ scope registry: {scope_id}")
    print(f"  ✅ history: {hist_id}")

    # 6) seed data
    print("➡️  写入种子数据 ...")
    seed_phases(db_ids["phases"])
    seed_tasks(db_ids["tasks"])
    seed_decisions(db_ids["decisions"])
    seed_docs(db_ids["docs"])
    seed_prompts(db_ids["prompts"])
    seed_initial_session(db_ids["sessions"])
    print("  ✅ seeds done")

    # 7) save ids
    out = {
        "root": root_id,
        "os": os_id,
        "automation_ops": auto_id,
        "governance": gov_id,
        "scope_registry": scope_id,
        "history": hist_id,
        "databases": db_ids,
        "temp_parent_page": TEMP_PARENT_PAGE_ID,
        "created_at": "2026-04-10",
    }
    IDS_OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"➡️  写出 {IDS_OUT}")
    print()
    print("🎉 完成。请打开 Notion 并手动把根页面拖到 workspace 顶层。")
    print(f"   根页面 ID: {root_id}")


if __name__ == "__main__":
    main()
