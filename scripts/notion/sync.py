"""
AIAeroPlaneRag — Notion ↔ GitHub 同步工具
=========================================

轻量 CLI，用于在日常开发中把 Notion 控制塔和 GitHub repo 串起来。
不做双向实时同步（避免冲突），只提供幂等的单向命令：

    python scripts/notion/sync.py status
        打印控制塔 IDs、当前 Active Phase、Active Session、P0 任务数。

    python scripts/notion/sync.py push-tasks
        把 Notion Tasks 表里 Status∈{Ready,In Progress} 且没有 GitHub Issue URL
        的任务，在 GitHub 上创建 Issue，并把 Issue URL 写回 Notion。

    python scripts/notion/sync.py log-session --title "2026-04-10 Impl X" \
        --type Implement --handoff "修了 guardrail 的 JSON 解析" \
        --files "src/rag/guardrail.py" --commit https://github.com/.../commit/abc
        追加一条 Session 行。

    python scripts/notion/sync.py restore
        打印"启动简报"：当前 Phase / Active Session / Top P0 Tasks / Open Decisions
        —— 直接喂给 Claude 作为会话第一条消息。

    # ---- 全自动开发链路 (由 GSD 驱动) ----
    python scripts/notion/sync.py pick-task [--priority P0]
        从 Tasks 表里挑一条 Status=Ready 的最高优任务,输出 JSON.

    python scripts/notion/sync.py start-task --id <notion_page_id>
        把该任务置 In Progress.

    python scripts/notion/sync.py complete-task --id <notion_page_id> \
        --handoff "..." --files "a;b" [--commit URL]
        把任务置 Done, 同时 append 一条 Session.

    python scripts/notion/sync.py block-task --id <notion_page_id> --reason "..."
        把任务置 Blocked, 同时建一条 Open Decision (Incident).

    python scripts/notion/sync.py close-issue --url https://github.com/.../issues/42
        GitHub issue 关闭时把对应 Notion task 置 Done (被 GH Action 调用).

    python scripts/notion/sync.py add-decision --name "..." --area Architecture \
        --context "..." --decision "..." --consequences "..." --status Decided
        追加一条 ADR.

依赖: requests, python-dotenv
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
IDS_PATH = Path(__file__).parent / "control_tower_ids.json"

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "kogamishinyajerry-ops")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "AIAeroPlaneRag")

N_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}
G_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


def load_ids() -> dict:
    if not IDS_PATH.exists():
        sys.exit(f"❌ 找不到 {IDS_PATH}；先跑 bootstrap_control_tower.py")
    return json.loads(IDS_PATH.read_text())


def n_query(db_id: str, filt: dict | None = None) -> list[dict]:
    results = []
    payload = {"page_size": 100}
    if filt:
        payload["filter"] = filt
    while True:
        r = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=N_HEADERS, json=payload, timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        results.extend(d.get("results", []))
        if not d.get("has_more"):
            return results
        payload["start_cursor"] = d["next_cursor"]


def n_update(page_id: str, props: dict) -> dict:
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=N_HEADERS, json={"properties": props}, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def n_create(db_id: str, props: dict) -> dict:
    r = requests.post(
        "https://api.notion.com/v1/pages",
        headers=N_HEADERS,
        json={"parent": {"database_id": db_id}, "properties": props},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def plain(prop: dict) -> str:
    if not prop:
        return ""
    t = prop.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in prop["title"])
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop["rich_text"])
    if t == "select":
        return (prop.get("select") or {}).get("name", "")
    if t == "url":
        return prop.get("url") or ""
    if t == "date":
        return (prop.get("date") or {}).get("start", "")
    if t == "number":
        return str(prop.get("number", ""))
    return ""


def rt(text: str) -> list:
    return [{"type": "text", "text": {"content": text}}]


# ---------------- commands ----------------

def cmd_status(ids: dict) -> None:
    print("Control Tower IDs:")
    print(f"  root: {ids['root']}")
    print(f"  OS:   {ids['os']}")
    for k, v in ids["databases"].items():
        print(f"  db.{k:<9}: {v}")
    phases = n_query(ids["databases"]["phases"],
                     {"property": "Status", "select": {"equals": "Active"}})
    print(f"\nActive Phases: {len(phases)}")
    for p in phases:
        print(f"  • {plain(p['properties']['Name'])}")
    tasks = n_query(ids["databases"]["tasks"],
                    {"and": [
                        {"property": "Priority", "select": {"equals": "P0"}},
                        {"property": "Status", "select": {"does_not_equal": "Done"}},
                    ]})
    print(f"\nP0 open tasks: {len(tasks)}")
    for t in tasks[:10]:
        st = plain(t["properties"]["Status"])
        print(f"  [{st:<11}] {plain(t['properties']['Name'])}")


def cmd_push_tasks(ids: dict) -> None:
    """把没有 GitHub Issue 的 Ready/In Progress 任务推到 GitHub."""
    tasks = n_query(ids["databases"]["tasks"],
                    {"and": [
                        {"property": "GitHub Issue", "url": {"is_empty": True}},
                        {"or": [
                            {"property": "Status", "select": {"equals": "Ready"}},
                            {"property": "Status", "select": {"equals": "In Progress"}},
                        ]},
                    ]})
    print(f"候选任务: {len(tasks)}")
    for t in tasks:
        name = plain(t["properties"]["Name"])
        acc = plain(t["properties"].get("Acceptance", {}))
        area = plain(t["properties"].get("Area", {}))
        prio = plain(t["properties"].get("Priority", {}))
        body = (
            f"> Synced from Notion Control Tower (page: {t['id']})\n\n"
            f"**Priority:** {prio}\n**Area:** {area}\n\n"
            f"### Acceptance\n{acc or '_(待补)_'}\n"
        )
        labels = [f"priority/{prio.lower()}", f"area/{area.lower().replace('/', '-')}"] if prio else []
        r = requests.post(
            f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues",
            headers=G_HEADERS,
            json={"title": name, "body": body, "labels": labels},
            timeout=30,
        )
        if r.status_code >= 300:
            print(f"  ❌ {name}: {r.status_code} {r.text[:120]}")
            continue
        url = r.json()["html_url"]
        n_update(t["id"], {"GitHub Issue": {"url": url}})
        print(f"  ✅ {name} → {url}")


def cmd_log_session(ids: dict, args: argparse.Namespace) -> None:
    props = {
        "Name": {"title": rt(args.title)},
        "Date": {"date": {"start": args.date or date.today().isoformat()}},
        "Model": {"select": {"name": args.model}},
        "Type": {"select": {"name": args.type}},
        "Entry Prompt": {"rich_text": rt(args.entry or "")[:1]},
        "Handoff Summary": {"rich_text": rt(args.handoff or "")[:1]},
        "Touched Files": {"rich_text": rt(args.files or "")[:1]},
    }
    if args.commit:
        props["Commit"] = {"url": args.commit}
    res = n_create(ids["databases"]["sessions"], props)
    print(f"✅ session logged: {res['id']}")


def cmd_restore(ids: dict) -> None:
    print("=" * 60)
    print("AIAeroPlaneRag — 会话启动简报")
    print("=" * 60)
    phases = n_query(ids["databases"]["phases"],
                     {"property": "Status", "select": {"equals": "Active"}})
    if phases:
        p = phases[0]["properties"]
        print(f"\n[Current Phase] {plain(p['Name'])}")
        ctx = plain(p.get("Context Pack", {}))
        exit_ = plain(p.get("Exit Criteria", {}))
        if ctx:
            print(f"  Context: {ctx}")
        if exit_:
            print(f"  Exit:    {exit_}")
    sessions = n_query(ids["databases"]["sessions"])
    sessions.sort(key=lambda s: plain(s["properties"].get("Date", {})), reverse=True)
    if sessions:
        s = sessions[0]["properties"]
        print(f"\n[Last Session] {plain(s['Name'])}")
        print(f"  Handoff: {plain(s.get('Handoff Summary', {}))}")
        print(f"  Files:   {plain(s.get('Touched Files', {}))}")
    tasks = n_query(ids["databases"]["tasks"],
                    {"and": [
                        {"property": "Priority", "select": {"equals": "P0"}},
                        {"property": "Status", "select": {"does_not_equal": "Done"}},
                    ]})
    print(f"\n[Top P0 Tasks] ({len(tasks)})")
    for t in tasks[:5]:
        p = t["properties"]
        print(f"  • [{plain(p['Status']):<11}] {plain(p['Name'])}")
        acc = plain(p.get("Acceptance", {}))
        if acc:
            print(f"      ↳ {acc[:100]}")
    decisions = n_query(ids["databases"]["decisions"],
                        {"property": "Status", "select": {"equals": "Open"}})
    print(f"\n[Open Decisions] ({len(decisions)})")
    for d in decisions[:5]:
        print(f"  • {plain(d['properties']['Name'])}")
    print()
    print("=" * 60)
    print("👉 把上面这段粘贴作为下一个 Claude 会话的第一条消息的补充上下文。")


def cmd_pick_task(ids: dict, args: argparse.Namespace) -> None:
    """输出最高优 Ready 任务的 JSON,供自动化 worker 消费."""
    filt = {"and": [
        {"property": "Status", "select": {"equals": "Ready"}},
        {"property": "Priority", "select": {"equals": args.priority}},
    ]}
    tasks = n_query(ids["databases"]["tasks"], filt)
    if not tasks:
        print(json.dumps({"found": False, "priority": args.priority}))
        return
    t = tasks[0]
    p = t["properties"]
    out = {
        "found": True,
        "id": t["id"],
        "name": plain(p["Name"]),
        "priority": plain(p.get("Priority", {})),
        "area": plain(p.get("Area", {})),
        "status": plain(p.get("Status", {})),
        "acceptance": plain(p.get("Acceptance", {})),
        "github_issue": plain(p.get("GitHub Issue", {})),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_start_task(ids: dict, args: argparse.Namespace) -> None:
    n_update(args.id, {"Status": {"select": {"name": "In Progress"}}})
    print(f"✅ task {args.id} → In Progress")


def cmd_complete_task(ids: dict, args: argparse.Namespace) -> None:
    # 1) mark task done
    props: dict = {"Status": {"select": {"name": "Done"}}}
    if args.commit:
        props["Commit/PR"] = {"url": args.commit}
    if args.notes:
        props["Notes"] = {"rich_text": rt(args.notes[:1900])}
    n_update(args.id, props)
    # 2) append session
    task_page = requests.get(
        f"https://api.notion.com/v1/pages/{args.id}",
        headers=N_HEADERS, timeout=30,
    ).json()
    task_name = plain(task_page["properties"]["Name"])
    session_props = {
        "Name": {"title": rt(f"{date.today().isoformat()} Auto — {task_name}"[:100])},
        "Date": {"date": {"start": date.today().isoformat()}},
        "Model": {"select": {"name": "Opus 4.6"}},
        "Type": {"select": {"name": "Implement"}},
        "Entry Prompt": {"rich_text": rt(f"Auto pick-up of task: {task_name}")},
        "Handoff Summary": {"rich_text": rt((args.handoff or "")[:1900])},
        "Touched Files": {"rich_text": rt((args.files or "")[:1900])},
    }
    if args.commit:
        session_props["Commit"] = {"url": args.commit}
    n_create(ids["databases"]["sessions"], session_props)
    print(f"✅ task {args.id} → Done + session logged")


def cmd_block_task(ids: dict, args: argparse.Namespace) -> None:
    n_update(args.id, {"Status": {"select": {"name": "Blocked"}}})
    task_page = requests.get(
        f"https://api.notion.com/v1/pages/{args.id}",
        headers=N_HEADERS, timeout=30,
    ).json()
    task_name = plain(task_page["properties"]["Name"])
    n_create(ids["databases"]["decisions"], {
        "Name": {"title": rt(f"INCIDENT: {task_name}")},
        "Status": {"select": {"name": "Open"}},
        "Area": {"select": {"name": "Process"}},
        "Context": {"rich_text": rt(f"Task {args.id} 自动执行被阻塞")},
        "Decision": {"rich_text": rt("待人工裁决")},
        "Consequences": {"rich_text": rt(args.reason[:1900])},
    })
    print(f"🛑 task {args.id} → Blocked + incident decision logged")


def cmd_close_issue(ids: dict, args: argparse.Namespace) -> None:
    tasks = n_query(ids["databases"]["tasks"],
                    {"property": "GitHub Issue", "url": {"equals": args.url}})
    if not tasks:
        print(f"⚠️  no task matches issue {args.url}")
        return
    for t in tasks:
        n_update(t["id"], {"Status": {"select": {"name": "Done"}}})
        print(f"✅ {plain(t['properties']['Name'])} → Done (via {args.url})")


def cmd_add_decision(ids: dict, args: argparse.Namespace) -> None:
    props = {
        "Name": {"title": rt(args.name[:100])},
        "Status": {"select": {"name": args.status}},
        "Area": {"select": {"name": args.area}},
        "Context": {"rich_text": rt((args.context or "")[:1900])},
        "Decision": {"rich_text": rt((args.decision or "")[:1900])},
        "Consequences": {"rich_text": rt((args.consequences or "")[:1900])},
        "Decided On": {"date": {"start": date.today().isoformat()}},
    }
    res = n_create(ids["databases"]["decisions"], props)
    print(f"✅ decision logged: {res['id']}")


# ---------------- cli ----------------

def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("push-tasks")
    sub.add_parser("restore")

    pt = sub.add_parser("pick-task")
    pt.add_argument("--priority", default="P0",
                    choices=["P0", "P1", "P2"])

    st = sub.add_parser("start-task")
    st.add_argument("--id", required=True)

    ct = sub.add_parser("complete-task")
    ct.add_argument("--id", required=True)
    ct.add_argument("--handoff", default="")
    ct.add_argument("--files", default="")
    ct.add_argument("--commit", default="")
    ct.add_argument("--notes", default="")

    bt = sub.add_parser("block-task")
    bt.add_argument("--id", required=True)
    bt.add_argument("--reason", required=True)

    ci = sub.add_parser("close-issue")
    ci.add_argument("--url", required=True)

    ad = sub.add_parser("add-decision")
    ad.add_argument("--name", required=True)
    ad.add_argument("--area", default="Architecture",
                    choices=["Architecture", "Retrieval", "Eval", "Infra", "Process"])
    ad.add_argument("--context", default="")
    ad.add_argument("--decision", default="")
    ad.add_argument("--consequences", default="")
    ad.add_argument("--status", default="Decided",
                    choices=["Open", "Decided", "Superseded", "Rejected"])

    ls = sub.add_parser("log-session")
    ls.add_argument("--title", required=True)
    ls.add_argument("--type", default="Implement",
                    choices=["Plan", "Implement", "Debug", "Review", "Benchmark", "Docs"])
    ls.add_argument("--model", default="Opus 4.6")
    ls.add_argument("--date")
    ls.add_argument("--entry", default="")
    ls.add_argument("--handoff", default="")
    ls.add_argument("--files", default="")
    ls.add_argument("--commit", default="")

    args = ap.parse_args()
    ids = load_ids()

    if args.cmd == "status":
        cmd_status(ids)
    elif args.cmd == "push-tasks":
        cmd_push_tasks(ids)
    elif args.cmd == "restore":
        cmd_restore(ids)
    elif args.cmd == "log-session":
        cmd_log_session(ids, args)
    elif args.cmd == "pick-task":
        cmd_pick_task(ids, args)
    elif args.cmd == "start-task":
        cmd_start_task(ids, args)
    elif args.cmd == "complete-task":
        cmd_complete_task(ids, args)
    elif args.cmd == "block-task":
        cmd_block_task(ids, args)
    elif args.cmd == "close-issue":
        cmd_close_issue(ids, args)
    elif args.cmd == "add-decision":
        cmd_add_decision(ids, args)


if __name__ == "__main__":
    main()
