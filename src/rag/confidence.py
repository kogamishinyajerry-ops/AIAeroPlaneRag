import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
def verify_answer_confidence(answer: str, contexts: List[Dict], query: str = "") -> tuple[float, List[str]]:
    """
    多维度置信度评估，返回 (confidence_score, uncertainty_markers)

    评估维度:
    1. 来源覆盖度 (0.25) - 答案中的陈述是否有检索证据支持
    2. 条款引用密度 (0.15) - 是否引用了具体条款号
    3. 术语精确度 (0.15) - 是否使用了专业术语而非模糊表述
    4. 跨规章验证 (0.10) - 是否有多个规章体系的交叉验证
    5. 数值具体性 (0.10) - 是否包含具体数值而非模糊描述
    6. 权威性加权 (0.15) - 根据文档权威性调整得分
    7. 一致性验证 (0.10) - 多来源是否相互印证
    """
    try:
        statements = [s.strip() for s in re.split(r'[。！？.!?]', answer) if len(s.strip()) > 5]
        if not statements:
            return 0.5, ["无法分割答案为有效陈述"]

        # 查询类型检测（用于动态权重）
        query_type = "general"
        if re.search(r'要求|标准|限值|规定', query):
            query_type = "regulatory"
        elif re.search(r'方法|程序|如何|怎么', query):
            query_type = "method"
        elif re.search(r'比较|差异|区别', query):
            query_type = "comparison"

        # 权威性权重映射
        AUTHORITY_WEIGHTS = {"CAAC": 1.0, "FAA": 0.95, "EASA": 0.90, "OTHER": 0.70}

        # 维度1: 来源覆盖度 (支持中英文混合来源)
        source_coverage = 0
        for stmt in statements:
            stmt_cn = set(re.findall(r'[\u4e00-\u9fff]{2,}', stmt))
            stmt_en = set(w.lower() for w in re.findall(r'[a-zA-Z]{3,}', stmt))
            stmt_terms = stmt_cn | stmt_en
            best_overlap = 0
            for ctx in contexts:
                src_text = ctx.get("text", "")
                src_cn = set(re.findall(r'[\u4e00-\u9fff]{2,}', src_text))
                src_en = set(w.lower() for w in re.findall(r'[a-zA-Z]{3,}', src_text))
                src_terms = src_cn | src_en
                overlap = len(stmt_terms & src_terms)
                best_overlap = max(best_overlap, overlap)
            if best_overlap >= 2:
                source_coverage += 1
        dim1 = source_coverage / len(statements) if statements else 0

        # 维度2: 条款引用密度
        citation_pattern = r'(?:§|第|section|CCAR|FAR|CS)\s*[\d.\-]+|(?:33|25|29|91)\.\d+'
        citations_found = re.findall(citation_pattern, answer, re.IGNORECASE)
        dim2 = min(len(citations_found) / max(len(statements), 1), 1.0)

        # 维度3: 术语精确度
        precise_terms = ["必须", "应当", "不得", "不低于", "不超过", "至少", "最大", "最小"]
        vague_terms = ["可能", "大概", "也许", "一般", "通常", "据说", "似乎"]
        precise_count = sum(1 for t in precise_terms if t in answer)
        vague_count = sum(1 for t in vague_terms if t in answer)
        dim3 = min(precise_count / max(precise_count + vague_count, 1), 1.0)

        # 维度4: 跨规章验证
        agencies_mentioned = set()
        for pattern, agency in [("CCAR|中国", "CAAC"), ("FAR|FAA|AC_33|美国", "FAA"), ("CS-|EASA|欧洲", "EASA")]:
            if re.search(pattern, answer, re.IGNORECASE):
                agencies_mentioned.add(agency)
        for ctx in contexts:
            src = ctx.get("metadata", {}).get("source", "")
            auth = ctx.get("metadata", {}).get("authority", "")
            if "CCAR" in src: agencies_mentioned.add("CAAC")
            elif "FAR" in src or "AC_33" in src.upper(): agencies_mentioned.add("FAA")
            elif "CS" in src or "EASA" in src: agencies_mentioned.add("EASA")
            if auth in AUTHORITY_WEIGHTS:
                agencies_mentioned.add(auth)
        dim4 = min(len(agencies_mentioned) / 2.0, 1.0)

        # 维度5: 数值具体性
        numbers = re.findall(r'\d+(?:\.\d+)?(?:\s*%|℃|°C|rpm|MPa|kN|kg|mm|m/s)?', answer)
        dim5 = min(len(numbers) / max(len(statements), 1), 1.0)

        # 维度6: 权威性加权（基于context来源的机构权重）
        authority_scores = []
        for ctx in contexts:
            auth = ctx.get("metadata", {}).get("authority", "OTHER")
            weight = AUTHORITY_WEIGHTS.get(auth, 0.70)
            authority_scores.append(weight)
        dim6 = sum(authority_scores) / len(authority_scores) if authority_scores else 0.5

        # 维度7: 一致性验证（多来源支持同一陈述）
        consistent_statements = 0
        for stmt in statements[:5]:  # 检查前5个主要陈述
            supporting_sources = 0
            stmt_terms = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', stmt.lower()))
            for ctx in contexts:
                ctx_text = ctx.get("text", "").lower()
                overlap = len(stmt_terms & set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', ctx_text)))
                if overlap >= 2:
                    supporting_sources += 1
            if supporting_sources >= 2:
                consistent_statements += 1
        dim7 = consistent_statements / max(len(statements[:5]), 1)

        # 动态权重调整
        if query_type == "regulatory":
            weights = {"dim1": 0.25, "dim2": 0.20, "dim3": 0.15, "dim4": 0.15, "dim5": 0.10, "dim6": 0.10, "dim7": 0.05}
        elif query_type == "method":
            weights = {"dim1": 0.25, "dim2": 0.10, "dim3": 0.15, "dim4": 0.10, "dim5": 0.10, "dim6": 0.15, "dim7": 0.15}
        elif query_type == "comparison":
            weights = {"dim1": 0.20, "dim2": 0.10, "dim3": 0.10, "dim4": 0.25, "dim5": 0.05, "dim6": 0.15, "dim7": 0.15}
        else:
            weights = {"dim1": 0.25, "dim2": 0.15, "dim3": 0.15, "dim4": 0.10, "dim5": 0.10, "dim6": 0.15, "dim7": 0.10}

        confidence = (dim1 * weights["dim1"] + dim2 * weights["dim2"] + dim3 * weights["dim3"] +
                      dim4 * weights["dim4"] + dim5 * weights["dim5"] + dim6 * weights["dim6"] + dim7 * weights["dim7"])
        confidence = min(max(confidence, 0.15), 0.95)

        # 生成不确定性标记
        uncertain_markers = []
        if dim1 < 0.5:
            uncertain_markers.append(f"来源覆盖不足：仅{source_coverage}/{len(statements)}条陈述有证据支持")
        if dim2 < 0.3:
            uncertain_markers.append(f"条款引用不足：建议补充具体条款号（如§33.xx）")
        if dim4 < 0.5 and len(agencies_mentioned) < 2:
            uncertain_markers.append(f"缺少跨规章验证：未涉及多机构等效条款")
        if dim5 < 0.3:
            uncertain_markers.append("缺少具体数值：建议补充定量要求")
        if vague_count > 0:
            uncertain_markers.append(f"存在{vague_count}处模糊表述")
        if dim6 < 0.7:
            uncertain_markers.append("权威性来源不足：建议补充CAAC/FAA/EASA原文")
        if dim7 < 0.3:
            uncertain_markers.append("多来源一致性不足：建议交叉验证")

        logger.info(f"[CONFIDENCE] score={confidence:.2f} type={query_type} dims=[src={dim1:.2f}, cite={dim2:.2f}, "
                    f"precise={dim3:.2f}, cross={dim4:.2f}, numeric={dim5:.2f}, auth={dim6:.2f}, consist={dim7:.2f}]")

        return confidence, uncertain_markers

    except Exception as e:
        logger.warning(f"Answer verification failed: {e}")
        return 0.5, [f"置信度评估异常: {str(e)[:50]}"]



