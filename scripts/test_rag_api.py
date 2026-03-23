"""Test script for RAG API queries."""
import requests
import json

BASE_URL = "http://127.0.0.1:8001"

# Test queries
TEST_QUERIES = [
    "喘振裕度的要求是什么？",
    "转子超转试验的转速要求是多少？",
    "限寿件包括哪些部件？",
    "吸鸟试验的验收标准是什么？",
    "150小时持久试验包括哪些内容？",
]

def test_query(query: str, top_k: int = 3):
    """Test a single query."""
    payload = {
        "query": query,
        "top_k": top_k,
        "use_guardrail": False
    }

    response = requests.post(f"{BASE_URL}/api/v1/query", json=payload)
    response.raise_for_status()
    return response.json()

def main():
    print("=" * 70)
    print(" CCAR-33-R2 RAG Query Testing")
    print("=" * 70)

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[Query {i}] {query}")
        print("-" * 70)

        try:
            result = test_query(query, top_k=2)

            print(f"Answer: {result['answer'][:200]}...")
            print(f"\nRetrieval count: {result['retrievalCount']}")
            print(f"Response mode: {result['responseMode']}")

            if result['citations']:
                print(f"\nCitations ({len(result['citations'])}):")
                for cit in result['citations'][:2]:
                    print(f"  - {cit['chapter']} > {cit['section']}")

            if result['graphInsights']:
                print(f"\nGraph insights ({len(result['graphInsights'])}):")
                for insight in result['graphInsights'][:2]:
                    print(f"  - {insight}")

        except Exception as e:
            print(f"Error: {e}")

    # Test health endpoint
    print("\n" + "=" * 70)
    print(" Health Check")
    print("=" * 70)

    try:
        health = requests.get(f"{BASE_URL}/api/v1/health").json()
        print(f"Vector DB: {health['vector_db']}")
        print(f"Vector count: {health['vector_db_count']}")
        print(f"App version: {health['app_version']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
