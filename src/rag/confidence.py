"""
置信度评分模块 — 7 维度量化
============================
维度定义（权重随查询类型动态调整）:
  1. source_coverage     来源覆盖度   — 答案陈述有检索证据支持的比例
  2. citation_density    条款引用密度 — 具体条款号（§33.xx 等）出现频率
  3. term_precision      术语精确度   — 专业强制性用语 vs. 模糊表述比率
  4. cross_regulation    跨规章验证   — 涉及 CAAC/FAA/EASA 多机构数量
  5. numeric_specificity 数值具体性   — 含具体数值/单位陈述的比例
  6. authority_weight    权威性加权   — 检索来源机构的权威性均值
  7. source_consistency  来源一致性   — 多来源相互印证的陈述比例
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────────────────
AUTHORITY_WEIGHTS: Dict[str, float] = {
    "CAAC": 1.0,
    "FAA":  0.95,
    "EASA": 0.90,
    "OTHER": 0.70,
}

DIMENSION_LABELS: Dict[str, str] = {
    "source_coverage":     "来源覆盖度",
    "citation_density":    "条款引用密度",
    "term_precision":      "术语精确度",
    "cross_regulation":    "跨规章验证",
    "numeric_specificity": "数值具体性",
    "authority_weight":    "权威性加权",
    "source_consistency":  "来源一致性",
}

WEIGHTS_BY_QUERY_TYPE: Dict[str, Dict[str, float]] = {
    "regulatory": {
        "source_coverage": 0.25, "citation_density": 0.20, "term_precision": 0.15,
        "cross_regulation": 0.15, "numeric_specificity": 0.10,
        "authority_weight": 0.10, "source_consistency": 0.05,
    },
    "method": {
        "source_coverage": 0.25, "citation_density": 0.10, "term_precision": 0.15,
        "cross_regulation": 0.10, "numeric_specificity": 0.10,
        "authority_weight": 0.15, "source_consistency": 0.15,
    },
    "comparison": {
        "source_coverage": 0.20, "citation_density": 0.10, "term_precision": 0.10,
        "cross_regulation": 0.25, "numeric_specificity": 0.05,
        "authority_weight": 0.15, "source_consistency": 0.15,
    },
    "general": {
        "source_coverage": 0.25, "citation_density": 0.15, "term_precision": 0.15,
        "cross_regulation": 0.10, "numeric_specificity": 0.10,
        "authority_weight": 0.15, "source_consistency": 0.10,
    },
}


class DimensionScore(TypedDict):
    name: str          # 英文 key
    label: str         # 中文名称
    score: float       # 0-1
    weight: float      # 本次查询使用的权重
    weighted: float    # score * weight
    detail: str        # 计算依据说明


class ConfidenceResult(TypedDict):
    summary: float                     # 综合置信度 0-1（钳位到 [0.15, 0.95]）
    query_type: str                    # 检测到的查询类型
    dimensions: Dict[str, DimensionScore]  # 7 维度详细得分
    explanation: str                   # 人类可读的综合说明
    uncertainty_markers: List[str]     # 具体改进建议


def _detect_query_type(query: str) -> str:
    if re.search(r'要求|标准|限值|规定', query):
        return "regulatory"
    if re.search(r'方法|程序|如何|怎么', query):
        return "method"
    if re.search(r'比较|差异|区别', query):
        return "comparison"
    return "general"


def _split_statements(answer: str) -> List[str]:
    return [s.strip() for s in re.split(r'[。！？.!?]', answer) if len(s.strip()) > 5]


def score_confidence(
    answer: str,
    contexts: List[Dict],
    query: str = "",
) -> ConfidenceResult:
    """
    计算7维度置信度，返回完整的 ConfidenceResult 结构。

    Args:
        answer:   模型生成的答案文本
        contexts: 检索到的上下文列表，每项含 text / metadata
        query:    原始查询文本（用于检测查询类型）

    Returns:
        ConfidenceResult — 含 summary / query_type / dimensions / explanation / uncertainty_markers
    """
    try:
        statements = _split_statements(answer)
        if not statements:
            return _fallback_result("无法从答案中分割有效陈述")

        query_type = _detect_query_type(query)
        weights = WEIGHTS_BY_QUERY_TYPE[query_type]

        # ── 维度1: 来源覆盖度 ───────────────────────────────────────────────
        source_coverage_count = 0
        for stmt in statements:
            stmt_terms = (
                set(re.findall(r'[\u4e00-\u9fff]{2,}', stmt))
                | set(w.lower() for w in re.findall(r'[a-zA-Z]{3,}', stmt))
            )
            best_overlap = max(
                (
                    len(stmt_terms & (
                        set(re.findall(r'[\u4e00-\u9fff]{2,}', ctx.get("text", "")))
                        | set(w.lower() for w in re.findall(r'[a-zA-Z]{3,}', ctx.get("text", "")))
                    ))
                    for ctx in contexts
                ),
                default=0,
            )
            if best_overlap >= 2:
                source_coverage_count += 1
        dim1 = source_coverage_count / len(statements)
        d1_detail = f"{source_coverage_count}/{len(statements)} 条陈述有证据支持"

        # ── 维度2: 条款引用密度 ─────────────────────────────────────────────
        citation_pattern = r'(?:§|第|section|CCAR|FAR|CS)\s*[\d.\-]+|(?:33|25|29|91)\.\d+'
        citations_found = re.findall(citation_pattern, answer, re.IGNORECASE)
        dim2 = min(len(citations_found) / max(len(statements), 1), 1.0)
        d2_detail = f"发现 {len(citations_found)} 处条款引用"

        # ── 维度3: 术语精确度 ───────────────────────────────────────────────
        precise_terms = ["必须", "应当", "不得", "不低于", "不超过", "至少", "最大", "最小",
                         "shall", "must", "required", "minimum", "maximum"]
        vague_terms   = ["可能", "大概", "也许", "一般", "通常", "据说", "似乎",
                         "may", "might", "perhaps", "generally", "usually"]
        precise_count = sum(1 for t in precise_terms if t in answer)
        vague_count   = sum(1 for t in vague_terms   if t in answer)
        dim3 = min(precise_count / max(precise_count + vague_count, 1), 1.0)
        d3_detail = f"强制性用语 {precise_count} 处，模糊用语 {vague_count} 处"

        # ── 维度4: 跨规章验证 ───────────────────────────────────────────────
        agencies_mentioned: set = set()
        for pat, agency in [
            (r"CCAR|中国民航|CAAC",      "CAAC"),
            (r"FAR|FAA|AC.33|美国联邦",  "FAA"),
            (r"CS-|EASA|欧洲航空",       "EASA"),
        ]:
            if re.search(pat, answer, re.IGNORECASE):
                agencies_mentioned.add(agency)
        for ctx in contexts:
            src  = ctx.get("metadata", {}).get("source", "")
            auth = ctx.get("metadata", {}).get("authority", "")
            if "CCAR" in src:
                agencies_mentioned.add("CAAC")
            elif "FAR" in src or "AC_33" in src.upper():
                agencies_mentioned.add("FAA")
            elif "CS" in src or "EASA" in src:
                agencies_mentioned.add("EASA")
            if auth in AUTHORITY_WEIGHTS:
                agencies_mentioned.add(auth)
        dim4 = min(len(agencies_mentioned) / 2.0, 1.0)
        d4_detail = f"涉及机构: {', '.join(sorted(agencies_mentioned)) or '无'}"

        # ── 维度5: 数值具体性 ───────────────────────────────────────────────
        numbers = re.findall(
            r'\d+(?:\.\d+)?(?:\s*%|℃|°C|rpm|MPa|kN|kg|mm|m/s|nm|bar|psi)?', answer
        )
        dim5 = min(len(numbers) / max(len(statements), 1), 1.0)
        d5_detail = f"发现 {len(numbers)} 处数值/单位"

        # ── 维度6: 权威性加权 ───────────────────────────────────────────────
        auth_scores = [
            AUTHORITY_WEIGHTS.get(ctx.get("metadata", {}).get("authority", "OTHER"), 0.70)
            for ctx in contexts
        ]
        dim6 = sum(auth_scores) / len(auth_scores) if auth_scores else 0.5
        d6_detail = (
            f"均值权威性 {dim6:.2f}（{len(auth_scores)} 个来源）"
            if auth_scores else "无来源权威性信息"
        )

        # ── 维度7: 来源一致性 ───────────────────────────────────────────────
        consistent_count = 0
        for stmt in statements[:5]:
            stmt_terms = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', stmt.lower()))
            supporting = sum(
                1 for ctx in contexts
                if len(stmt_terms & set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}',
                                                   ctx.get("text", "").lower()))) >= 2
            )
            if supporting >= 2:
                consistent_count += 1
        dim7 = consistent_count / max(len(statements[:5]), 1)
        d7_detail = f"{consistent_count}/{min(len(statements), 5)} 条陈述有≥2个来源印证"

        # ── 综合得分 ────────────────────────────────────────────────────────
        raw_dims = {
            "source_coverage":     dim1,
            "citation_density":    dim2,
            "term_precision":      dim3,
            "cross_regulation":    dim4,
            "numeric_specificity": dim5,
            "authority_weight":    dim6,
            "source_consistency":  dim7,
        }
        details = {
            "source_coverage":     d1_detail,
            "citation_density":    d2_detail,
            "term_precision":      d3_detail,
            "cross_regulation":    d4_detail,
            "numeric_specificity": d5_detail,
            "authority_weight":    d6_detail,
            "source_consistency":  d7_detail,
        }

        summary_raw = sum(raw_dims[k] * weights[k] for k in raw_dims)
        summary = round(min(max(summary_raw, 0.15), 0.95), 4)

        dimensions: Dict[str, DimensionScore] = {
            k: DimensionScore(
                name=k,
                label=DIMENSION_LABELS[k],
                score=round(raw_dims[k], 4),
                weight=weights[k],
                weighted=round(raw_dims[k] * weights[k], 4),
                detail=details[k],
            )
            for k in raw_dims
        }

        # ── 不确定性标记 ────────────────────────────────────────────────────
        markers: List[str] = []
        if dim1 < 0.5:
            markers.append(f"来源覆盖不足：仅 {source_coverage_count}/{len(statements)} 条陈述有证据支持")
        if dim2 < 0.3:
            markers.append("条款引用不足：建议补充具体条款号（如 §33.xx）")
        if dim4 < 0.5:
            markers.append(f"缺少跨规章验证：仅涉及 {len(agencies_mentioned)} 个机构")
        if dim5 < 0.3:
            markers.append("缺少具体数值：建议补充定量要求（数值+单位）")
        if vague_count > 0:
            markers.append(f"存在 {vague_count} 处模糊表述，影响精确度")
        if dim6 < 0.7:
            markers.append("权威性来源不足：建议补充 CAAC/FAA/EASA 原文引用")
        if dim7 < 0.3:
            markers.append("多来源一致性不足：建议交叉验证关键陈述")

        # ── 综合说明 ────────────────────────────────────────────────────────
        level = "高" if summary >= 0.75 else "中" if summary >= 0.50 else "低"
        explanation = (
            f"综合置信度 {summary:.0%}（{level}）。"
            f"查询类型：{query_type}。"
            f"来源覆盖 {dim1:.0%}，条款引用 {len(citations_found)} 处，"
            f"跨规章验证 {len(agencies_mentioned)} 个机构，"
            f"数值引用 {len(numbers)} 处。"
            + (f" 待改进：{markers[0]}" if markers else " 各维度表现良好。")
        )

        logger.info(
            "[CONFIDENCE] summary=%.2f type=%s "
            "dims=[cov=%.2f cite=%.2f prec=%.2f cross=%.2f num=%.2f auth=%.2f cons=%.2f]",
            summary, query_type, dim1, dim2, dim3, dim4, dim5, dim6, dim7,
        )

        return ConfidenceResult(
            summary=summary,
            query_type=query_type,
            dimensions=dimensions,
            explanation=explanation,
            uncertainty_markers=markers,
        )

    except Exception as exc:
        logger.warning("score_confidence failed: %s", exc)
        return _fallback_result(f"置信度评估异常: {str(exc)[:60]}")


def _fallback_result(reason: str) -> ConfidenceResult:
    """返回安全的默认置信度结果。"""
    dummy_dim: DimensionScore = DimensionScore(
        name="unknown", label="未知", score=0.5,
        weight=0.0, weighted=0.0, detail=reason,
    )
    return ConfidenceResult(
        summary=0.5,
        query_type="general",
        dimensions={k: dummy_dim for k in DIMENSION_LABELS},
        explanation=f"置信度评估失败：{reason}",
        uncertainty_markers=[reason],
    )


# ── 向后兼容接口（旧调用方不需改动）──────────────────────────────────────────
def verify_answer_confidence(
    answer: str,
    contexts: List[Dict],
    query: str = "",
) -> Tuple[float, List[str]]:
    """
    向后兼容接口：返回 (confidence_score, uncertainty_markers)。
    内部调用 score_confidence，新代码请直接使用 score_confidence。
    """
    result = score_confidence(answer, contexts, query)
    return result["summary"], result["uncertainty_markers"]
