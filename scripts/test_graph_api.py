"""Test graph API on port 9999."""
import requests
import json

BASE = "http://127.0.0.1:9999"

print("=" * 60)
print(" Testing Graph API")
print("=" * 60)

# Health check
try:
    resp = requests.get(f"{BASE}/").json()
    print(f"\n[API] Service: {resp.get('service')} v{resp.get('version')} - {resp.get('status')}")
except Exception as e:
    print(f"\n[ERROR] API not reachable: {e}")
    exit(1)

# Graph nodes endpoint
print("\n[TEST] /api/v1/graph/nodes")
try:
    resp = requests.get(f"{BASE}/api/v1/graph/nodes").json()
    nodes = resp.get("nodes", [])
    edges = resp.get("edges", [])
    mode = resp.get("mode", "unknown")
    stats = resp.get("stats", {})

    print(f"  Mode: {mode}")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")
    print(f"  Stats: {stats}")

    if nodes:
        print(f"\n  Sample nodes:")
        for node in nodes[:5]:
            print(f"    - {node.get('id')} ({node.get('type')}): {node.get('label', '')[:30]}")

    if edges:
        print(f"\n  Sample edges:")
        for edge in edges[:3]:
            print(f"    - {edge.get('source')} -> {edge.get('target')} ({edge.get('type')})")
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

# Graph subgraph endpoint
print("\n[TEST] /api/v1/graph/subgraph?query=限寿件")
try:
    resp = requests.get(f"{BASE}/api/v1/graph/subgraph", params={"query": "限寿件"}).json()
    nodes = resp.get("nodes", [])
    edges = resp.get("edges", [])

    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")

    if nodes:
        print(f"\n  Sample nodes:")
        for node in nodes[:5]:
            print(f"    - {node.get('id')} ({node.get('type')}): {node.get('label', '')[:30]}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print(f"API running at: {BASE}")
print("=" * 60)
