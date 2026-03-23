"""Test API with Neo4j connected."""
import requests
import json

BASE_URL = "http://127.0.0.1:8001"

print("=" * 70)
print(" Testing API with Neo4j Connected")
print("=" * 70)

# 1. Health check
print("\n[1] Health Check")
print("-" * 70)
try:
    health = requests.get(f"{BASE_URL}/api/v1/health", timeout=10).json()
    print(json.dumps(health, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")

# 2. Test graph query - get subgraph
print("\n[2] Graph Subgraph Query (喘振)")
print("-" * 70)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/graph/subgraph",
        params={"entity_name": "喘振"},
        timeout=10
    ).json()
    print(f"Nodes: {len(response.get('nodes', []))}")
    print(f"Relationships: {len(response.get('relationships', []))}")
    if response.get('nodes'):
        print("\nNodes:")
        for node in response['nodes'][:5]:
            print(f"  - {node.get('id')} ({node.get('type')}): {node.get('name', '')[:30]}")
except Exception as e:
    print(f"Error: {e}")

# 3. Test graph query - get all nodes
print("\n[3] Graph All Nodes")
print("-" * 70)
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/graph/nodes",
        timeout=10
    ).json()
    nodes = response.get('nodes', [])
    print(f"Total nodes: {len(nodes)}")

    # Count by type
    type_counts = {}
    for n in nodes:
        t = n.get('type', 'Unknown')
        type_counts[t] = type_counts.get(t, 0) + 1

    print("\nNodes by type:")
    for t, count in sorted(type_counts.items()):
        print(f"  - {t}: {count}")
except Exception as e:
    print(f"Error: {e}")

# 4. Test RAG query with graph insights
print("\n[4] RAG Query (转子超转试验要求)")
print("-" * 70)
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={
            "query": "转子超转试验的转速要求是多少？",
            "top_k": 3,
            "use_guardrail": False
        },
        timeout=30
    ).json()

    print(f"Answer: {response.get('answer', '')[:200]}...")
    print(f"\nRetrieval count: {response.get('retrievalCount', 0)}")

    if response.get('graphInsights'):
        print(f"\nGraph insights ({len(response['graphInsights'])}):")
        for insight in response['graphInsights'][:3]:
            print(f"  - {insight}")

    if response.get('citations'):
        print(f"\nCitations:")
        for cit in response['citations'][:2]:
            print(f"  - {cit.get('chapter')} > {cit.get('section')}")
except Exception as e:
    print(f"Error: {e}")

# 5. Test more queries
queries = [
    "限寿件包括哪些部件？",
    "吸鸟试验的验收标准是什么？",
    "150小时持久试验的要求是什么？"
]

print("\n[5] Multiple Queries")
print("-" * 70)

for query in queries:
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/query",
            json={"query": query, "top_k": 2, "use_guardrail": False},
            timeout=20
        ).json()

        graph_count = len(response.get('graphInsights', []))
        citation_count = len(response.get('citations', []))

        print(f"\nQ: {query}")
        print(f"  Graph insights: {graph_count}, Citations: {citation_count}")
        print(f"  Answer: {response.get('answer', '')[:100]}...")
    except Exception as e:
        print(f"\nQ: {query}")
        print(f"  Error: {e}")

print("\n" + "=" * 70)
print(" Test Complete")
print("=" * 70)
