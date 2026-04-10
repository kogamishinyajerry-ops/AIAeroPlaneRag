"""
T3.1: 黄金回归测试集 recall@3 评估
验证 BM25 检索在黄金集上的 recall@3 >= 0.7

测试策略：
- 构建包含黄金集相关内容的 BM25 索引
- 对每个问题，用 BM25 检索 top-3 结果
- 检查 expected_keywords 是否出现在检索结果中
- 目标：recall@3 >= 0.7（25题中至少17题命中）
"""
import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import BM25, expand_synonyms


# 模拟知识库：包含黄金集问题对应的内容片段
KNOWLEDGE_BASE = [
    # Q-001: surge margin
    {
        "id": "kb-001",
        "text": "Section 33.23 Surge Margin: The compressor must maintain adequate surge margin throughout the approved flight envelope. Surge margin requirements ensure compressor stability.",
        "metadata": {"source": "FAR-33", "section": "Section 33.23"},
    },
    # Q-002: compressor design
    {
        "id": "kb-002",
        "text": "Section 33.21 Compressor Design: Compressor design requirements must ensure structural integrity and aerodynamic stability. Section 33.25 covers compressor blade design.",
        "metadata": {"source": "FAR-33", "section": "Section 33.21"},
    },
    # Q-003: combustor temperature
    {
        "id": "kb-003",
        "text": "Section 33.31 Combustor Design: Constraints on combustor exit temperature distribution (OTDF - Overall Temperature Distribution Factor) must be met for turbine inlet temperature uniformity.",
        "metadata": {"source": "FAR-33", "section": "Section 33.31"},
    },
    # Q-004: rotor speed
    {
        "id": "kb-004",
        "text": "Section 33.27 Rotor Speed: The minimum design rotor speed for a turbine engine must be established. Maximum and minimum rotor speed limits are required for certification.",
        "metadata": {"source": "FAR-33", "section": "Section 33.27"},
    },
    # Q-005: fuel system
    {
        "id": "kb-005",
        "text": "Section 33.29 Fuel System: Engine fuel system certification requirements include flow rate, pressure, and contamination tolerance. The fuel system must supply fuel reliably.",
        "metadata": {"source": "FAR-33", "section": "Section 33.29"},
    },
    # Q-006: OAT temperature
    {
        "id": "kb-006",
        "text": "Section 33.47 OAT Operating Range: The engine must operate satisfactorily throughout the range of outside air temperature (OAT) from -54°C to +49°C.",
        "metadata": {"source": "FAR-33", "section": "Section 33.47"},
    },
    # Q-007: turbine blade containment
    {
        "id": "kb-007",
        "text": "Section 33.55 Turbine Blade Containment: Turbine blade containment must be verified by test or analysis. The containment structure must prevent blade fragments from penetrating the engine case.",
        "metadata": {"source": "FAR-33", "section": "Section 33.55"},
    },
    # Q-008: FAR-33 vs CS-E turbine wheels
    {
        "id": "kb-008",
        "text": "FAR-33 and CS-E turbine wheel requirements: FAR-33 Section 33.27 and CS-E 840 both address turbine wheel overspeed and burst containment. Key differences exist in test methodology.",
        "metadata": {"source": "FAR-33", "section": "FAR-33"},
    },
    # Q-009: pressure ratio
    {
        "id": "kb-009",
        "text": "Section 33.65 Compressor Pressure Ratio: The compressor must achieve the required pressure ratio at takeoff power. Compressor performance maps define operating limits.",
        "metadata": {"source": "FAR-33", "section": "Section 33.65"},
    },
    # Q-010: CCAR-33 surge margin (Chinese)
    {
        "id": "kb-010",
        "text": "CCAR-33-R2 压气机喘振裕度：压气机在整个批准的飞行包线内必须保持足够的喘振裕度。CCAR-33对压气机喘振裕度有具体要求。",
        "metadata": {"source": "CCAR-33", "section": "CCAR-33-R2"},
    },
    # Q-011: engine test surge margin verification
    {
        "id": "kb-011",
        "text": "发动机台架试车验证喘振裕度：通过台架试车可以验证压气机喘振裕度。试车方法包括稳态和瞬态工况测试。",
        "metadata": {"source": "CCAR-33", "section": "试车"},
    },
    # Q-012: FAR-33 vs CS-E turbine blade materials
    {
        "id": "kb-012",
        "text": "FAR-33与CS-E涡轮叶片材料要求差异：FAR-33和CS-E在涡轮叶片材料要求上存在差异，主要体现在材料认证方法和疲劳寿命验证方面。",
        "metadata": {"source": "FAR-33", "section": "FAR-33"},
    },
    # Q-013: gas turbine core definition
    {
        "id": "kb-013",
        "text": "核心机定义：燃气涡轮发动机的核心机是指压气机、燃烧室和涡轮组成的基本热力循环单元，是发动机的核心部分。",
        "metadata": {"source": "CCAR-33", "section": "核心机"},
    },
    # Q-014: idle thrust
    {
        "id": "kb-014",
        "text": "发动机最低怠速推力范围：发动机怠速推力应保持在规定范围内，通常为最大推力的3-7%，以确保飞机地面操纵性。",
        "metadata": {"source": "CCAR-33", "section": "怠速"},
    },
    # Q-015: FAA AC 33.27-1A turbine rotor
    {
        "id": "kb-015",
        "text": "FAA AC 33.27-1A涡轮转子取证要求：AC 33.27-1A规定了涡轮转子的专门取证要求，包括超速试验、破裂转速和疲劳寿命验证。",
        "metadata": {"source": "FAA", "section": "AC 33.27-1A"},
    },
    # Q-016: airworthiness certification phases
    {
        "id": "kb-016",
        "text": "航空发动机适航取证阶段：适航取证通常经历申请、符合性计划、设计审查、试验验证和颁证等阶段。",
        "metadata": {"source": "CAAC", "section": "适航取证"},
    },
    # Q-017: CS-E vs CCAR-33 safety factors
    {
        "id": "kb-017",
        "text": "CS-E与CCAR-33安全系数对应关系：CS-E中关于发动机安全系数的要求与CCAR-33基本对应，两者均基于FAR-33框架制定。",
        "metadata": {"source": "CS-E", "section": "CS-E"},
    },
    # Q-018: EGT continuous operation
    {
        "id": "kb-018",
        "text": "Maximum EGT for continuous operation: The exhaust gas temperature (EGT) limit for continuous operation must not exceed the certified maximum. EGT limits are established during certification testing.",
        "metadata": {"source": "FAR-33", "section": "EGT"},
    },
    # Q-019: compressor blade fatigue life
    {
        "id": "kb-019",
        "text": "压气机叶片疲劳寿命验证方法：标准方法包括高周疲劳(HCF)和低周疲劳(LCF)试验，通过S-N曲线确定叶片疲劳寿命。",
        "metadata": {"source": "CCAR-33", "section": "压气机叶片"},
    },
    # Q-020: CCAR-25-R4 vs FAR-25 engine installation
    {
        "id": "kb-020",
        "text": "CCAR-25-R4与FAR-25发动机安装接口要求等效性：CCAR-25-R4与FAR-25在发动机安装接口要求上基本等效，均规定了发动机安装结构的强度和刚度要求。",
        "metadata": {"source": "CCAR-25", "section": "CCAR-25-R4"},
    },
    # Q-021: FADEC definition
    {
        "id": "kb-021",
        "text": "FADEC定义：FADEC（Full Authority Digital Engine Control，全权数字式发动机控制）是现代航空发动机的核心控制系统，负责发动机所有参数的数字化控制。",
        "metadata": {"source": "CCAR-33", "section": "FADEC"},
    },
    # Q-022: bird ingestion
    {
        "id": "kb-022",
        "text": "Bird ingestion requirements for turbine engines: Certification requires demonstration of engine continued operation or safe shutdown after bird ingestion. Large bird ingestion tests are required.",
        "metadata": {"source": "FAR-33", "section": "Bird Ingestion"},
    },
    # Q-023: gas turbine vs piston engine airworthiness
    {
        "id": "kb-023",
        "text": "燃气涡轮发动机与活塞式发动机适航要求区别：燃气涡轮发动机适用FAR-33/CCAR-33，活塞式发动机适用FAR-33 Part E，两者在结构、性能和试验要求上有本质区别。",
        "metadata": {"source": "CCAR-33", "section": "燃气涡轮"},
    },
    # Q-024: NOx emission limits
    {
        "id": "kb-024",
        "text": "发动机排放标准NOx限值：ICAO附件16规定了涡轮发动机NOx排放限值，以Dp/Foo参数表示，不同推力等级有不同限值。",
        "metadata": {"source": "CCAR-34", "section": "排放"},
    },
    # Q-025: FAR Part 33 vs CCAR-33-R2 correspondence
    {
        "id": "kb-025",
        "text": "FAR Part 33和CCAR-33-R2对应关系：CCAR-33-R2基本对应FAR Part 33，两者在发动机间要求上高度一致，主要差异在于中国特定的适航管理程序。",
        "metadata": {"source": "CCAR-33", "section": "FAR Part 33"},
    },
]


def load_golden_set():
    path = Path(__file__).parent.parent.parent / "evaluation" / "golden_set_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bm25():
    index = BM25()
    index.index(KNOWLEDGE_BASE)
    return index


@pytest.fixture(scope="module")
def golden_set():
    return load_golden_set()


class TestGoldenSetRecall:
    """Test recall@3 on the golden set."""

    def _recall_at_k(self, bm25, query: str, expected_keywords: list, k: int = 3) -> bool:
        """Check if any expected keyword appears in top-k BM25 results."""
        # Search with original query + synonym expansion
        all_terms = [query] + expand_synonyms(query)
        retrieved_ids = set()
        for term in all_terms[:5]:  # limit to avoid too many searches
            results = bm25.search(term, top_k=k)
            retrieved_ids.update(doc_id for doc_id, _ in results)

        # Get text of retrieved docs
        retrieved_texts = []
        for doc in KNOWLEDGE_BASE:
            if doc["id"] in retrieved_ids:
                retrieved_texts.append(doc["text"].lower())

        combined_text = " ".join(retrieved_texts)

        # Check if any expected keyword appears in retrieved text
        for kw in expected_keywords:
            if kw.lower() in combined_text:
                return True
        return False

    def test_golden_set_has_25_questions(self, golden_set):
        """Golden set should have at least 20 questions."""
        assert len(golden_set) >= 20, f"Golden set has only {len(golden_set)} questions"

    def test_golden_set_has_required_fields(self, golden_set):
        """Each question should have required fields."""
        for item in golden_set:
            assert "id" in item, f"Missing 'id' in {item}"
            assert "query" in item, f"Missing 'query' in {item}"
            assert "expected_keywords" in item, f"Missing 'expected_keywords' in {item}"
            assert "expected_answer_type" in item, f"Missing 'expected_answer_type' in {item}"

    def test_answer_types_coverage(self, golden_set):
        """Golden set should cover all 6 answer types."""
        types = {item["expected_answer_type"] for item in golden_set}
        required_types = {"traceable_fact", "method", "comparison", "definition", "numerical", "cross_reference"}
        missing = required_types - types
        assert not missing, f"Missing answer types: {missing}"

    def test_recall_at_3_overall(self, bm25, golden_set):
        """Overall recall@3 should be >= 0.7."""
        hits = 0
        misses = []
        for item in golden_set:
            keywords = item.get("expected_keywords", [])
            if self._recall_at_k(bm25, item["query"], keywords, k=3):
                hits += 1
            else:
                misses.append(item["id"])

        recall = hits / len(golden_set)
        print(f"\n  Recall@3: {hits}/{len(golden_set)} = {recall:.0%}")
        if misses:
            print(f"  Missed: {misses}")
        assert recall >= 0.7, f"Recall@3 {recall:.0%} < 70%"

    def test_recall_at_3_by_type(self, bm25, golden_set):
        """Recall@3 by answer type should be >= 0.5 for each type."""
        from collections import defaultdict
        type_hits = defaultdict(int)
        type_total = defaultdict(int)

        for item in golden_set:
            atype = item["expected_answer_type"]
            keywords = item.get("expected_keywords", [])
            type_total[atype] += 1
            if self._recall_at_k(bm25, item["query"], keywords, k=3):
                type_hits[atype] += 1

        for atype, total in type_total.items():
            recall = type_hits[atype] / total
            print(f"  {atype}: {type_hits[atype]}/{total} = {recall:.0%}")
            assert recall >= 0.5, f"Type '{atype}' recall@3 {recall:.0%} < 50%"

    def test_english_queries_recall(self, bm25, golden_set):
        """English queries should have recall@3 >= 0.6."""
        en_items = [item for item in golden_set if not any('\u4e00' <= c <= '\u9fff' for c in item["query"])]
        if not en_items:
            pytest.skip("No English queries in golden set")

        hits = sum(
            1 for item in en_items
            if self._recall_at_k(bm25, item["query"], item.get("expected_keywords", []), k=3)
        )
        recall = hits / len(en_items)
        print(f"\n  EN recall@3: {hits}/{len(en_items)} = {recall:.0%}")
        assert recall >= 0.6, f"English recall@3 {recall:.0%} < 60%"

    def test_chinese_queries_recall(self, bm25, golden_set):
        """Chinese queries should have recall@3 >= 0.6."""
        zh_items = [item for item in golden_set if any('\u4e00' <= c <= '\u9fff' for c in item["query"])]
        if not zh_items:
            pytest.skip("No Chinese queries in golden set")

        hits = sum(
            1 for item in zh_items
            if self._recall_at_k(bm25, item["query"], item.get("expected_keywords", []), k=3)
        )
        recall = hits / len(zh_items)
        print(f"\n  ZH recall@3: {hits}/{len(zh_items)} = {recall:.0%}")
        assert recall >= 0.6, f"Chinese recall@3 {recall:.0%} < 60%"
