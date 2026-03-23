"""Test API on port 8888."""
import requests

BASE = "http://127.0.0.1:8888"

# Health check
health = requests.get(f"{BASE}/").json()
print("API Health:")
print(f"  Service: {health.get('service')}")
print(f"  Version: {health.get('version')}")
print(f"  Status: {health.get('status')}")

# Health endpoint
health_detail = requests.get(f"{BASE}/api/v1/health").json()
print(f"\nVector DB: {health_detail.get('vector_db')}")
print(f"Vector count: {health_detail.get('vector_db_count')}")
print(f"Graph DB: {health_detail.get('graph_db')}")
print(f"Graph nodes: {health_detail.get('graph_node_count')}")

# Test query
print("\nTest Query:")
response = requests.post(f"{BASE}/api/v1/query", json={
    "query": "转子超转试验的转速要求是多少？",
    "top_k": 2,
    "use_guardrail": False
}).json()

print(f"  Answer: {response.get('answer', '')[:150]}...")
print(f"  Citations: {len(response.get('citations', []))}")

print(f"\nAPI running at: http://127.0.0.1:8888")
print(f"Web UI: ui/index.html")
print(f"Neo4j Browser: http://localhost:7474")
