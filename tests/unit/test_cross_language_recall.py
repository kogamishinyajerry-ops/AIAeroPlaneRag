"""
T2.3: BM25 同义词扩展跨语言召回验证
验证中↔英查询对的召回率 >= 0.6

测试策略：
- 构建包含中英文内容的小型 BM25 索引
- 用中文查询验证能否召回英文文档（通过同义词扩展）
- 用英文查询验证能否召回中文文档
- 目标：10对查询对中，至少6对能跨语言召回
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import BM25, expand_synonyms


# 双语语料库：每个文档同时包含中英文内容
BILINGUAL_CORPUS = [
    {
        "id": "doc-surge-en",
        "text": "The compressor must maintain adequate surge margin throughout the approved flight envelope to prevent compressor stall.",
        "metadata": {"source": "FAR-33", "section": "33.65"},
    },
    {
        "id": "doc-surge-zh",
        "text": "压气机必须在整个批准的飞行包线内保持足够的喘振裕度，以防止压气机失速。",
        "metadata": {"source": "CCAR-33", "section": "33.65"},
    },
    {
        "id": "doc-turbine-en",
        "text": "Turbine blade containment must be demonstrated by test or analysis. The turbine wheel must withstand overspeed conditions.",
        "metadata": {"source": "FAR-33", "section": "33.27"},
    },
    {
        "id": "doc-turbine-zh",
        "text": "涡轮叶片包容性必须通过试验或分析来验证。涡轮轮盘必须能承受超速条件。",
        "metadata": {"source": "CCAR-33", "section": "33.27"},
    },
    {
        "id": "doc-fuel-en",
        "text": "The fuel system must supply fuel to the engine at a flow rate and pressure that will permit satisfactory engine operation.",
        "metadata": {"source": "FAR-33", "section": "33.29"},
    },
    {
        "id": "doc-fuel-zh",
        "text": "燃油系统必须以满足发动机正常运行所需的流量和压力向发动机供油。",
        "metadata": {"source": "CCAR-33", "section": "33.29"},
    },
    {
        "id": "doc-temp-en",
        "text": "The engine must operate satisfactorily throughout the range of outside air temperature from -54°C to +49°C.",
        "metadata": {"source": "FAR-33", "section": "33.47"},
    },
    {
        "id": "doc-temp-zh",
        "text": "发动机必须在外界大气温度从-54°C到+49°C的范围内令人满意地运行。",
        "metadata": {"source": "CCAR-33", "section": "33.47"},
    },
    {
        "id": "doc-cert-en",
        "text": "Airworthiness certification requires compliance with all applicable regulations and standards.",
        "metadata": {"source": "FAR-33", "section": "33.1"},
    },
    {
        "id": "doc-cert-zh",
        "text": "适航审定要求符合所有适用的规章和标准。",
        "metadata": {"source": "CCAR-33", "section": "33.1"},
    },
    {
        "id": "doc-fatigue-en",
        "text": "Fatigue analysis must demonstrate that critical rotating parts have adequate life under all operating conditions.",
        "metadata": {"source": "FAR-33", "section": "33.70"},
    },
    {
        "id": "doc-fatigue-zh",
        "text": "疲劳分析必须证明关键旋转部件在所有运行条件下具有足够的寿命。",
        "metadata": {"source": "CCAR-33", "section": "33.70"},
    },
    {
        "id": "doc-vibration-en",
        "text": "Vibration tests must demonstrate that the engine is free from harmful vibration throughout the operating range.",
        "metadata": {"source": "FAR-33", "section": "33.83"},
    },
    {
        "id": "doc-vibration-zh",
        "text": "振动试验必须证明发动机在整个运行范围内不存在有害振动。",
        "metadata": {"source": "CCAR-33", "section": "33.83"},
    },
    {
        "id": "doc-emission-en",
        "text": "Exhaust emission standards limit NOx, CO, and unburned hydrocarbons from turbine engines.",
        "metadata": {"source": "FAR-34", "section": "34.21"},
    },
    {
        "id": "doc-emission-zh",
        "text": "排放标准限制涡轮发动机的NOx、CO和未燃烧碳氢化合物的排放量。",
        "metadata": {"source": "CCAR-34", "section": "34.21"},
    },
    {
        "id": "doc-noise-en",
        "text": "Noise certification requires measurement of engine noise levels during takeoff and approach.",
        "metadata": {"source": "FAR-36", "section": "36.1"},
    },
    {
        "id": "doc-noise-zh",
        "text": "噪声审定要求在起飞和进近过程中测量发动机噪声水平。",
        "metadata": {"source": "CCAR-36", "section": "36.1"},
    },
    {
        "id": "doc-maintenance-en",
        "text": "Maintenance instructions must include inspection intervals and procedures for all life-limited parts.",
        "metadata": {"source": "FAR-33", "section": "33.4"},
    },
    {
        "id": "doc-maintenance-zh",
        "text": "维修说明必须包括所有寿命限制件的检查间隔和程序。",
        "metadata": {"source": "CCAR-33", "section": "33.4"},
    },
]

# 10对跨语言查询对：(中文查询, 期望召回的英文文档ID, 英文查询, 期望召回的中文文档ID)
CROSS_LANGUAGE_PAIRS = [
    ("喘振裕度", "doc-surge-en", "surge margin", "doc-surge-zh"),
    ("涡轮叶片", "doc-turbine-en", "turbine blade", "doc-turbine-zh"),
    ("燃油系统", "doc-fuel-en", "fuel system", "doc-fuel-zh"),
    ("温度范围", "doc-temp-en", "temperature range", "doc-temp-zh"),
    ("适航审定", "doc-cert-en", "airworthiness certification", "doc-cert-zh"),
    ("疲劳寿命", "doc-fatigue-en", "fatigue life", "doc-fatigue-zh"),
    ("振动试验", "doc-vibration-en", "vibration test", "doc-vibration-zh"),
    ("排放标准", "doc-emission-en", "emission standard", "doc-emission-zh"),
    ("噪声审定", "doc-noise-en", "noise certification", "doc-noise-zh"),
    ("维修检查", "doc-maintenance-en", "maintenance inspection", "doc-maintenance-zh"),
]


@pytest.fixture(scope="module")
def bm25_index():
    """Build BM25 index with bilingual corpus."""
    index = BM25()
    index.index(BILINGUAL_CORPUS)
    return index


class TestCrossLanguageRecall:
    """Test cross-language recall via synonym expansion."""

    def _search_ids(self, bm25_index, query: str, top_k: int = 5):
        """Search and return list of doc IDs."""
        results = bm25_index.search(query, top_k=top_k)
        return [doc_id for doc_id, _ in results]

    def test_synonym_expansion_produces_cross_language_terms(self):
        """Verify expand_synonyms returns cross-language terms."""
        zh_expanded = expand_synonyms("喘振裕度")
        assert any("surge" in t.lower() or "stall" in t.lower() for t in zh_expanded), \
            f"喘振裕度 should expand to surge/stall, got: {zh_expanded}"

        en_expanded = expand_synonyms("surge margin")
        assert any("喘振" in t or "失速" in t for t in en_expanded), \
            f"surge margin should expand to 喘振/失速, got: {en_expanded}"

    def test_zh_query_recalls_en_doc(self, bm25_index):
        """Chinese query should recall English document via synonym expansion."""
        recalled = 0
        for zh_query, en_doc_id, _, _ in CROSS_LANGUAGE_PAIRS:
            # Expand synonyms and search
            expanded = expand_synonyms(zh_query)
            found = False
            for term in [zh_query] + expanded:
                results = self._search_ids(bm25_index, term, top_k=5)
                if en_doc_id in results:
                    found = True
                    break
            if found:
                recalled += 1

        recall_rate = recalled / len(CROSS_LANGUAGE_PAIRS)
        print(f"\n  ZH→EN recall: {recalled}/{len(CROSS_LANGUAGE_PAIRS)} = {recall_rate:.0%}")
        assert recall_rate >= 0.6, f"ZH→EN recall {recall_rate:.0%} < 60%"

    def test_en_query_recalls_zh_doc(self, bm25_index):
        """English query should recall Chinese document via synonym expansion."""
        recalled = 0
        for _, _, en_query, zh_doc_id in CROSS_LANGUAGE_PAIRS:
            expanded = expand_synonyms(en_query)
            found = False
            for term in [en_query] + expanded:
                results = self._search_ids(bm25_index, term, top_k=5)
                if zh_doc_id in results:
                    found = True
                    break
            if found:
                recalled += 1

        recall_rate = recalled / len(CROSS_LANGUAGE_PAIRS)
        print(f"\n  EN→ZH recall: {recalled}/{len(CROSS_LANGUAGE_PAIRS)} = {recall_rate:.0%}")
        assert recall_rate >= 0.6, f"EN→ZH recall {recall_rate:.0%} < 60%"

    def test_monolingual_recall_baseline(self, bm25_index):
        """Same-language queries should have high recall (baseline check)."""
        # Chinese query → Chinese doc
        zh_recalled = 0
        for zh_query, _, _, zh_doc_id in CROSS_LANGUAGE_PAIRS:
            results = self._search_ids(bm25_index, zh_query, top_k=5)
            if zh_doc_id in results:
                zh_recalled += 1

        # English query → English doc
        en_recalled = 0
        for _, en_doc_id, en_query, _ in CROSS_LANGUAGE_PAIRS:
            results = self._search_ids(bm25_index, en_query, top_k=5)
            if en_doc_id in results:
                en_recalled += 1

        zh_rate = zh_recalled / len(CROSS_LANGUAGE_PAIRS)
        en_rate = en_recalled / len(CROSS_LANGUAGE_PAIRS)
        print(f"\n  ZH→ZH baseline: {zh_recalled}/{len(CROSS_LANGUAGE_PAIRS)} = {zh_rate:.0%}")
        print(f"  EN→EN baseline: {en_recalled}/{len(CROSS_LANGUAGE_PAIRS)} = {en_rate:.0%}")
        assert zh_rate >= 0.7, f"ZH→ZH baseline {zh_rate:.0%} < 70%"
        assert en_rate >= 0.7, f"EN→EN baseline {en_rate:.0%} < 70%"

    @pytest.mark.parametrize("zh_query,en_doc_id,en_query,zh_doc_id", CROSS_LANGUAGE_PAIRS)
    def test_individual_pair_has_some_recall(self, bm25_index, zh_query, en_doc_id, en_query, zh_doc_id):
        """Each query pair should recall at least one of the two target docs."""
        zh_expanded = [zh_query] + expand_synonyms(zh_query)
        en_expanded = [en_query] + expand_synonyms(en_query)

        zh_found = any(en_doc_id in self._search_ids(bm25_index, t, top_k=5) for t in zh_expanded)
        en_found = any(zh_doc_id in self._search_ids(bm25_index, t, top_k=5) for t in en_expanded)

        # At least one direction should work
        assert zh_found or en_found, \
            f"Pair ({zh_query!r}, {en_query!r}): neither direction recalled target doc"
