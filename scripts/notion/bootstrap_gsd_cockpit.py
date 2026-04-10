"""
GSD Cockpit Bootstrap
=====================

在 AIAeroPlaneRag 控制塔下新增一个 "GSD Development Cockpit" 子页面,
用于承载 Getting-Shit-Done 风格的每日执行视图:

    - Today's Focus (前 3 条 P0 Ready 任务)
    - Autopilot Log  (过去 7 天的自动执行 Session)
    - Open Decisions (需要人工裁决)
    - Runbook & 快捷链接

以及一个 "Automation Runbook" 页面, 记录全自动链路的所有约定.

运行:
    python scripts/notion/bootstrap_gsd_cockpit.py

前置条件:
    1. Notion Integration 能访问控制塔 (必须先在 Notion UI 里把根页面 Share
       给 Claude Dev Workflow Integration).
    2. scripts/notion/control_tower_ids.json 已存在 (bootstrap_control_tower 执行过).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

IDS_PATH = Path(__file__).parent / "control_tower_ids.json"
if not IDS_PATH.exists():
    sys.exit(f"❌ 找不到 {IDS_PATH}")

IDS = json.loads(IDS_PATH.read_text())

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def rt(s: str) -> list:
    return [{"type": "text", "text": {"content": s}}]


def blk(t: str, body: dict) -> dict:
    return {"object": "block", "type": t, t: body}


def h2(s): return blk("heading_2", {"rich_text": rt(s)})
def h3(s): return blk("heading_3", {"rich_text": rt(s)})
def p(s): return blk("paragraph", {"rich_text": rt(s)})
def b(s): return blk("bulleted_list_item", {"rich_text": rt(s)})
def code(s, lang="plain text"):
    """Notion code 块限 2000 字; 超长自动拆分成多个 paragraph."""
    if len(s) <= 1990:
        return blk("code", {"rich_text": rt(s), "language": lang})
    # 超长时先建 code 块(截断), 余下段落继续
    return blk("code", {"rich_text": rt(s[:1990]), "language": lang})

def code_blocks(s: str, lang: str = "plain text") -> list:
    """把超长字符串切成多个 ≤1990 字的 code 块列表."""
    blocks = []
    for i in range(0, len(s), 1990):
        blocks.append(blk("code", {"rich_text": rt(s[i:i+1990]), "language": lang}))
    return blocks
def divider(): return blk("divider", {})
def callout(s, emoji="🚀"):
    return blk("callout", {"rich_text": rt(s), "icon": {"type": "emoji", "emoji": emoji}})
def link_to_page(page_id: str) -> dict:
    return {"object": "block", "type": "link_to_page",
            "link_to_page": {"type": "page_id", "page_id": page_id}}

def db_link(label: str, db_id: str) -> dict:
    """数据库引用: Notion URL 形式的 paragraph."""
    clean = db_id.replace("-", "")
    url = f"https://www.notion.so/{clean}"
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                {"type": "text", "text": {"content": f"↗ 打开 {label}",
                                          "link": {"url": url}},
                 "annotations": {"bold": True, "color": "blue"}}
            ]}}


def create_page(parent_id: str, title: str, children: list, icon: str) -> str:
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS,
                      json={"parent": {"page_id": parent_id},
                            "properties": {"title": {"title": rt(title)}},
                            "icon": {"type": "emoji", "emoji": icon},
                            "children": children[:100]}, timeout=30)
    if r.status_code >= 300:
        print("❌", r.status_code, r.text)
        r.raise_for_status()
    return r.json()["id"]


# -------- GSD Cockpit --------

def build_cockpit() -> list:
    dbs = IDS["databases"]
    return [
        callout(
            "GSD Development Cockpit — AIAeroPlaneRag 的每日执行驾驶舱. "
            "一次只推进一件事, 其它全部写进 Backlog. 由 Notion 控制面驱动, Repo 是真相源.",
            "🚀",
        ),
        h2("今日焦点 — Top P0 Ready Tasks"),
        p("点击下方链接打开 Tasks 库; 在 Notion 里新建 filter view: Priority=P0 AND Status∈{Ready,In Progress}, 排序按 Priority."),
        db_link("Tasks DB", dbs["tasks"]),
        h2("Autopilot 日志 — 最近 Sessions"),
        p("自动化链路跑完后会往这张表追加行; 建议新建 filter view: Date ≥ this week, 按 Date 倒序查看."),
        db_link("Sessions DB", dbs["sessions"]),
        h2("Open Decisions — 等待人工裁决"),
        p("自动化遇到无法决定的情况会在这里建 Incident 行, 状态 Open. 每天扫一眼, 只要这里空了说明 autopilot 是顺畅的."),
        db_link("Decisions DB", dbs["decisions"]),
        h2("快捷入口"),
        b("AeroPower RAG OS (Home Surfaces)"),
        link_to_page(IDS["os"]),
        b("Automation Operations"),
        link_to_page(IDS["automation_ops"]),
        b("Isolation Governance Rules"),
        link_to_page(IDS["governance"]),
        b("Automation Scope Registry"),
        link_to_page(IDS["scope_registry"]),
        divider(),
        h2("GSD 三大纪律"),
        b("1. 当前 In Progress 任务最多 1 条; 超过必须先 block-task 其余的."),
        b("2. 一次会话只解一个任务, 失败立刻 block-task 写 Incident, 不硬扛."),
        b("3. 所有决策 (包括放弃某条路径) 都写进 Decisions 表; 否则下次会话会重复踩坑."),
    ]


# -------- Automation Runbook --------

AUTOPILOT_PROMPT = """你现在是 AIAeroPlaneRag 的自动开发 agent. 按以下顺序执行, 不要跳步:

# Step 0 — Preflight
cd ~/AIAeroPlaneRag
python scripts/notion/sync.py status
# 如果报错, 立刻退出并在 Decisions 表建 Incident (手动 curl 或下次会话处理).

# Step 1 — Pick
TASK_JSON=$(python scripts/notion/sync.py pick-task --priority P0)
echo "$TASK_JSON"
# 解析 JSON; 如果 found=false, 依次 fallback 到 P1, 再 P2. 全为 false 则退出, 打印 "no work".
TASK_ID=$(echo "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("id",""))')
TASK_NAME=$(echo "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("name",""))')
TASK_AREA=$(echo "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("area",""))')
TASK_ACC=$(echo "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("acceptance",""))')
[ -z "$TASK_ID" ] && exit 0

# Step 2 — Start
python scripts/notion/sync.py start-task --id "$TASK_ID"
git fetch origin
git checkout -b "auto/$(date +%Y%m%d-%H%M)-${TASK_NAME:0:20}" || git checkout "auto/$(date +%Y%m%d-%H%M)"

# Step 3 — Implement
# 严格按 TASK_ACC 里的验收标准推进.
# 只改动与该 Area 直接相关的文件.
# 禁止触碰 AI-Harness v1/v2 相关路径 (本仓库不应有, 但兜底禁止).
# 每次改完跑 pytest tests/ -q; 失败 → 修; 连续失败 2 次 → 进 Step 5b.

# Step 4 — Commit & Push
git add -A
git commit -m "feat($TASK_AREA): $TASK_NAME

Auto-driven by Notion Control Tower task $TASK_ID.
Acceptance: $TASK_ACC"
git push -u origin HEAD
COMMIT_URL="https://github.com/kogamishinyajerry-ops/AIAeroPlaneRag/commit/$(git rev-parse HEAD)"

# Step 5a — Success: complete task
FILES=$(git diff --name-only HEAD~1 HEAD | tr '\\n' ';')
python scripts/notion/sync.py complete-task \\
  --id "$TASK_ID" \\
  --commit "$COMMIT_URL" \\
  --handoff "Auto-implemented $TASK_NAME, tests pass, pushed to branch." \\
  --files "$FILES"
exit 0

# Step 5b — Failure: block task
python scripts/notion/sync.py block-task \\
  --id "$TASK_ID" \\
  --reason "Auto-run failed: <具体原因>. 需要人工 debug."
exit 1

# 硬约束:
# - 禁止修改 .env / secrets / tokens.
# - 禁止读写 AI-Harness v1 / v2 的任何资源.
# - 如果任务描述不清晰 → 直接 block-task, 不猜.
# - 单次会话最多改 15 个文件; 超过 → block-task 要求拆分.
"""


def build_runbook() -> list:
    return [
        callout("Automation Runbook — Autopilot Claude agent 在无人监督时执行的严格脚本.", "📘"),
        h2("触发方式"),
        b("Cowork Scheduled Task: AIAeroPlaneRag autopilot (默认每 4 小时)"),
        b("手动: python scripts/notion/sync.py restore 然后本地执行下面的 Prompt"),
        b("GitHub Actions: nightly push-tasks (Ready → Issue 同步)"),
        h2("Autopilot Prompt (复制给 Claude, 完全自包含)"),
        *code_blocks(AUTOPILOT_PROMPT, "bash"),
        h2("不变量"),
        b("Repo 是真相源, Notion 是控制面."),
        b("同一时刻 In Progress 任务 ≤ 1."),
        b("任何 Commit 都必须对应一个 Task (通过 Notion task id 可追溯)."),
        b("任何决策/放弃/回滚 → Decisions 表."),
        b("禁区: AI-Harness v1/v2, .env, secrets."),
        h2("人工介入信号 (Open Decisions 非空)"),
        b("收到 Incident 行 → 停止下一次 Autopilot 跑, 先读 Context/Consequences."),
        b("裁决后把 Decision 置 Decided 或 Rejected; 相应 Task 重新置 Ready 或保持 Blocked."),
    ]


def main() -> None:
    print("➡️  创建 GSD Cockpit ...")
    cockpit_id = create_page(IDS["root"], "GSD Development Cockpit",
                             build_cockpit(), "🚀")
    print(f"  ✅ cockpit: {cockpit_id}")

    print("➡️  创建 Automation Runbook ...")
    runbook_id = create_page(IDS["root"], "Automation Runbook",
                             build_runbook(), "📘")
    print(f"  ✅ runbook: {runbook_id}")

    IDS["gsd_cockpit"] = cockpit_id
    IDS["automation_runbook"] = runbook_id
    IDS_PATH.write_text(json.dumps(IDS, indent=2, ensure_ascii=False))
    print(f"➡️  已更新 {IDS_PATH}")
    print("\n🎉 完成.")


if __name__ == "__main__":
    main()
