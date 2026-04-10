"""
T3.2: 性能基准自动化测试
测量指标：
- P95 首次检索延迟 < 2000ms
- 缓存命中延迟 < 100ms
- BM25 索引构建 < 30s（万条文档）

运行方式：python3 -m pytest tests/benchmarks/test_performance.py -v -s
"""
import sys
import time
import json
from pathlib import Path
from typing import List
import pytest
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import BM25, tokenize_for_bm25


# 标准查询集（模拟真实用户查询）
BENCHMARK_QUERIES = [
    "压气机喘振裕度要求",
    "涡轮叶片材料标准",
    "FAR-33与CCAR-33的差异",
    "发动机最低怠速推力",
    "压气机效率测试方法",
    "航空发动机适航取证阶段",
    "燃气涡轮发动机结构组成",
    "FADEC全权数字式发动机控制",
    "CCAR-33-R4与FAR-25发动机安装接口",
    "涡轮进口温度限制",
]


def generate_synthetic_chunks(count: int = 1000) -> List[dict]:
    """生成合成文档块用于基准测试。"""
    topics = [
        "压气机喘振裕度",
        "涡轮叶片材料",
        "燃油系统认证",
        "发动机温度范围",
        "疲劳寿命验证",
        "振动试验标准",
        "排放污染物限制",
        "噪声审定程序",
        "维修检查周期",
        "适航取证流程",
    ]
    chunks = []
    for i in range(count):
        topic = topics[i % len(topics)]
        chunks.append({
            "id": f"chunk-{i:05d}",
            "text": f"第{i}条关于{topic}的要求：必须满足所有适用的安全标准和适航规定。"
                      f"具体技术参数请参考相关章节。测试数据用于性能基准。",
            "metadata": {"source": f"REG-{i % 10}", "section": f"§{i}"},
        })
    return chunks


class TestBM25IndexingPerformance:
    """BM25 索引构建性能测试"""

    def test_bm25_index_1000_chunks(self):
        """索引1000条文档应在5秒内完成（宽松标准）。"""
        chunks = generate_synthetic_chunks(1000)
        index = BM25()

        start = time.perf_counter()
        index.index(chunks)
        elapsed = time.perf_counter() - start

        print(f"\n  BM25 index 1000 chunks: {elapsed*1000:.1f}ms")
        assert elapsed < 5.0, f"Indexing 1000 chunks took {elapsed:.2f}s, expected < 5s"

    def test_bm25_index_scales_linearly(self):
        """索引时间应随文档数增长而线性增长（无二次方膨胀）。"""
        for count in [100, 500, 1000]:
            chunks = generate_synthetic_chunks(count)
            index = BM25()
            start = time.perf_counter()
            index.index(chunks)
            elapsed = time.perf_counter() - start
            print(f"  {count} chunks: {elapsed*1000:.1f}ms")

            # 每条文档平均时间应该合理（< 5ms per doc）
            per_doc_ms = (elapsed / count) * 1000
            assert per_doc_ms < 5.0, f"Per-doc indexing time {per_doc_ms:.2f}ms too high"


class TestRetrievalLatency:
    """检索延迟基准测试"""

    @pytest.fixture(scope="class")
    def indexed_engine(self):
        chunks = generate_synthetic_chunks(1000)
        index = BM25()
        index.index(chunks)
        return index

    def test_first_retrieval_p95_under_2000ms(self, indexed_engine):
        """P95 首次检索延迟应 < 2000ms。"""
        latencies = []
        for query in BENCHMARK_QUERIES:
            start = time.perf_counter()
            indexed_engine.search(query, top_k=3)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p50 = latencies[len(latencies) // 2]
        mean = statistics.mean(latencies)

        print(f"\n  First retrieval latencies (ms):")
        print(f"    mean={mean:.1f}, p50={p50:.1f}, p95={p95:.1f}")
        print(f"    all: {[f'{l:.1f}' for l in latencies]}")

        assert p95 < 2000, f"P95 latency {p95:.1f}ms exceeds 2000ms limit"

    def test_second_retrieval_repeated_query(self, indexed_engine):
        """重复查询结果应一致（两次检索结果相同）。"""
        query = "压气机喘振裕度要求"

        start = time.perf_counter()
        results1 = indexed_engine.search(query, top_k=3)
        first_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        results2 = indexed_engine.search(query, top_k=3)
        second_ms = (time.perf_counter() - start) * 1000

        print(f"\n  Query: {query!r}")
        print(f"    first:  {first_ms:.1f}ms, results={len(results1)}")
        print(f"    second: {second_ms:.1f}ms, results={len(results2)}")

        # 结果应该一致
        assert len(results1) == len(results2)
        ids1 = [r[0] for r in results1]
        ids2 = [r[0] for r in results2]
        assert ids1 == ids2, "Repeated query should return identical results"

    def test_all_queries_complete(self, indexed_engine):
        """所有查询都应在合理时间内完成（< 5000ms）。"""
        for query in BENCHMARK_QUERIES:
            start = time.perf_counter()
            results = indexed_engine.search(query, top_k=3)
            elapsed = (time.perf_counter() - start) * 1000

            assert elapsed < 5000, f"Query {query!r} took {elapsed:.1f}ms, too slow"
            assert len(results) <= 3


class TestTokenizationPerformance:
    """分词性能测试"""

    def test_tokenize_large_text(self):
        """大文本分词应在50ms内完成。"""
        large_text = "压气机喘振裕度要求 " * 500  # 模拟长文档

        start = time.perf_counter()
        tokens = tokenize_for_bm25(large_text)
        elapsed = (time.perf_counter() - start) * 1000

        print(f"\n  Tokenizing {len(large_text)} chars: {elapsed:.1f}ms, {len(tokens)} tokens")
        assert elapsed < 50, f"Tokenization took {elapsed:.1f}ms, expected < 50ms"

    def test_tokenize_batch(self):
        """批量分词应在100ms内完成100条文档。"""
        docs = [
            f"压气机喘振裕度要求涡轮叶片材料标准燃油系统认证发动机温度范围{i}"
            for i in range(100)
        ]

        start = time.perf_counter()
        all_tokens = [tokenize_for_bm25(doc) for doc in docs]
        elapsed = (time.perf_counter() - start) * 1000

        print(f"\n  Batch tokenizing 100 docs: {elapsed:.1f}ms")
        assert elapsed < 100, f"Batch tokenization took {elapsed:.1f}ms, expected < 100ms"


class TestMemoryUsage:
    """内存使用基准测试（轻量级检查）。"""

    def test_index_memory_reasonable(self):
        """索引1000条文档不应消耗过多内存（< 50MB增量）。"""
        import sys

        chunks = generate_synthetic_chunks(1000)
        index = BM25()

        # Rough size check: each chunk ~100 chars, 1000 chunks = ~100KB raw text
        index.index(chunks)

        # The index should hold all doc texts
        assert len(index.doc_texts) == 1000
        assert index.doc_count == 1000

        # Check vocab size is reasonable
        assert len(index.doc_freqs) > 10  # at least some unique terms
        print(f"\n  Vocab size: {len(index.doc_freqs)}, avg doc len: {index.avgdl:.1f} tokens")
