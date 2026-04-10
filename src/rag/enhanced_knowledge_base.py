"""
增强型多规章知识库
集成了专业术语理解、同义词扩展和改进的相关性排序
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .aviation_terminology import (
    AviationTerminology,
    expand_query_with_synonyms,
    normalize_professional_query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SearchContext:
    """搜索上下文"""
    original_query: str
    normalized_query: str
    expanded_terms: List[str]
    professional_terms: Dict[str, List[str]]
    ccar_references: List[str]
    section_references: List[str]


@dataclass
class SearchResult:
    """增强的搜索结果"""
    node_id: str
    title: str
    text: str
    summary: str
    metadata: Dict
    relevance_score: float
    match_details: Dict
    cross_references: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "text": self.text or self.summary or self.title,
            "original_text": self.text,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score,
            "match_details": self.match_details,
            "cross_references": self.cross_references
        }


class EnhancedMultiCCARKB:
    """
    增强型多规章知识库

    改进点：
    1. 专业术语标准化和同义词扩展
    2. 改进的相关性计算
    3. 条款全文内容提取
    4. 跨规章关联推荐
    """

    def __init__(self, processed_dir: str = "./data/processed"):
        self.processed_dir = Path(processed_dir)
        self.documents: Dict[str, Dict] = {}
        self.node_map: Dict[str, Dict] = {}
        self.section_content_map: Dict[str, str] = {}  # 条号 -> 全文内容
        self._load_all_regulations()

    def _load_all_regulations(self):
        """加载所有规章结构"""
        structure_files = list(self.processed_dir.glob("*_structure.json"))

        for file_path in structure_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data["doc_name"]
                self.documents[doc_name] = data

                # 获取结构数据 - 处理两种格式
                # 格式1: structure 是列表 [{"nodes": [...]}]
                # 格式2: structure 是字典 {"chapters": [...]}
                structure_data = data.get("structure", [])
                if isinstance(structure_data, dict) and "chapters" in structure_data:
                    # 新格式 (FAR-25): {chapters: [...]}
                    for node_data in structure_data["chapters"]:
                        self._build_node_map(node_data, doc_name)
                        self._extract_section_content(node_data, doc_name)
                elif isinstance(structure_data, list):
                    # 旧格式 (CCAR): [{nodes: [...]}]
                    for node_data in structure_data:
                        self._build_node_map(node_data, doc_name)
                        self._extract_section_content(node_data, doc_name)

                logger.info(f"Loaded {doc_name}: {data.get('total_sections', 0)} sections")

            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")

        logger.info(f"Total documents: {len(self.documents)}")
        logger.info(f"Total nodes: {len(self.node_map)}")
        logger.info(f"Sections with content: {len(self.section_content_map)}")

    def _build_node_map(self, node_data: Dict, doc_name: str, parent_path: str = ""):
        """递归构建节点映射"""
        # 生成节点ID - 对于没有node_id的节点，使用title生成
        node_id = node_data.get("node_id")
        if not node_id:
            # 使用标题或其他唯一标识
            node_id = node_data.get("id", "") or node_data.get("number", "") or str(hash(str(node_data.get("title", ""))))
        global_id = f"{doc_name}:{node_id}"

        node = {
            **node_data,
            "doc_name": doc_name,
            "global_id": global_id,
            "parent_path": parent_path
        }
        self.node_map[global_id] = node
        self.node_map[node_id] = node  # 向后兼容

        # 递归处理子节点 - 支持多种格式
        # 格式1: nodes (CCAR格式)
        # 格式2: sections (FAR格式)
        children = node_data.get("nodes", []) or node_data.get("sections", [])
        for child in children:
            new_path = f"{parent_path}/{node.get('title', '')}" if parent_path else node.get('title', '')
            self._build_node_map(child, doc_name, new_path)

    def _extract_section_content(self, node_data: Dict, doc_name: str):
        """提取条款全文内容"""
        title = node_data.get("title", "")

        # 提取条款号 - 支持中文和FAA格式
        # 中文格式: "第25.1条"
        # FAA格式: "§ 25.1" 或 "25.1"
        section_match = re.search(r'第\s*([\d\.]+)\s*条', title)
        if not section_match:
            section_match = re.search(r'§\s*([\d\.]+)', title)
        if not section_match:
            section_match = re.search(r'^(\d+\.\d+)', title)

        if section_match:
            section_num = section_match.group(1)
            key = f"{doc_name}:{section_num}"

            # 组合 summary 和 content_parts 作为全文
            content_parts = []
            if node_data.get("summary"):
                content_parts.append(node_data["summary"])
            if node_data.get("content_parts"):
                content_parts.extend(node_data["content_parts"])

            full_content = " ".join(content_parts)
            if full_content:
                self.section_content_map[key] = full_content

        # 递归处理子节点 - 支持多种格式
        children = node_data.get("nodes", []) or node_data.get("sections", [])
        for child in children:
            self._extract_section_content(child, doc_name)

    def _parse_search_context(self, query: str) -> SearchContext:
        """解析搜索上下文"""
        # 标准化查询
        normalized = normalize_professional_query(query)

        # 扩展同义词
        expanded = expand_query_with_synonyms(query)

        # 提取专业术语
        professional_terms = AviationTerminology.extract_professional_terms(query)

        # 提取 CCAR/FAR/EASA 引用
        ccar_refs = professional_terms.get("ccar_refs", [])
        ccar_matches = re.findall(r'CCAR[-\s]*(\d+)', query, re.IGNORECASE)
        ccar_refs.extend([f"CCAR-{m}" for m in ccar_matches])

        # 检测 FAR 引用
        far_matches = re.findall(r'FAR[-\s]*(\d+)', query, re.IGNORECASE)
        ccar_refs.extend([f"FAR-{m}" for m in far_matches])

        # 检测 EASA/CS 引用
        easa_matches = re.findall(r'CS[-\s]*(\w+)', query, re.IGNORECASE)
        ccar_refs.extend([f"CS-{m}" for m in easa_matches])
        easa_matches2 = re.findall(r'EASA[-\s]*(\w+)', query, re.IGNORECASE)
        ccar_refs.extend([f"EASA-{m}" for m in easa_matches2])

        # 提取条款号引用
        section_matches = re.findall(r'(\d+(?:\.\d+)?)', query)
        section_refs = list(set(section_matches))

        return SearchContext(
            original_query=query,
            normalized_query=normalized,
            expanded_terms=expanded,
            professional_terms=professional_terms,
            ccar_references=list(set(ccar_refs)),
            section_references=section_refs
        )

    def _calculate_enhanced_relevance(
        self,
        node: Dict,
        context: SearchContext,
        preferred_docs: List[str] = None
    ) -> Tuple[float, Dict]:
        """计算增强相关性得分"""
        score = 0.0
        match_details = {
            "title_match": False,
            "content_match": False,
            "section_match": False,
            "ccar_match": False,
            "professional_match": [],
            "query_string_match": False
        }

        node_title = node.get("title", "").lower()
        node_summary = node.get("summary", "").lower()
        node_doc = node.get("doc_name", "")
        query_lower = context.original_query.lower()
        normalized_lower = context.normalized_query.lower()

        # 1. CCAR/FAA/EASA 文档匹配 (高权重)
        if context.ccar_references:
            for ccar_ref in context.ccar_references:
                ccar_num = ccar_ref.replace("CCAR-", "").replace("CCAR", "").replace("FAR-", "").replace("EASA-", "").replace("CS-", "")
                if ccar_num in node_doc:
                    score += 50
                    match_details["ccar_match"] = True
                    break

        # 2. 条款号精确匹配 (最高权重) - 支持中文和FAA格式
        if context.section_references:
            for section_num in context.section_references:
                # 检查各种格式: 25.1, § 25.1, 第25.1条
                section_patterns = [section_num, f"§ {section_num}", f"§{section_num}", f"{section_num} "]
                if any(s in node_title for s in section_patterns):
                    score += 60
                    match_details["section_match"] = True
                    break

        # 3. 专业术语匹配
        for category, terms in context.professional_terms.items():
            if category == "ccar_refs":
                continue
            for term in terms:
                term_lower = term.lower()
                if term_lower in node_title:
                    score += 15
                    match_details["professional_match"].append(f"{category}:{term}(title)")
                elif term_lower in node_summary:
                    score += 8
                    match_details["professional_match"].append(f"{category}:{term}(content)")

        # 4. 扩展同义词匹配
        for expanded_term in context.expanded_terms[:3]:  # 限制数量避免噪音
            expanded_lower = expanded_term.lower()
            if expanded_lower in node_title and expanded_lower not in query_lower:
                score += 5

        # 5. 原始查询字符串匹配
        if query_lower in node_title or query_lower in (node_summary + " " + node.get("text", "")).lower():
            score += 20
            match_details["query_string_match"] = True

        # 6. 标准化查询匹配
        if normalized_lower in node_title:
            score += 10
            match_details["title_match"] = True
        elif normalized_lower in node_summary:
            score += 5
            match_details["content_match"] = True

        # 7. 文档优先级加成
        if preferred_docs and any(pref in node_doc for pref in preferred_docs):
            score *= 1.2

        # 8. 条款类型加成 (支持中文"条"和FAA格式"§")
        is_section = "条" in node_title or "§" in node_title or "25." in node_title
        if is_section:
            score *= 1.1

        return score, match_details

    def _find_cross_references(self, result_node: Dict, context: SearchContext) -> List[Dict]:
        """查找跨规章关联"""
        references = []

        # 基于专业术语找相关条款
        related_docs = []
        for category, terms in context.professional_terms.items():
            if category == "ccar_refs" or not terms:
                continue
            for term in terms[:2]:  # 每个类别最多取2个术语
                related_docs.append(term)

        # 在其他文档中查找相关内容
        current_doc = result_node.get("doc_name", "")
        for global_id, node in self.node_map.items():
            if node.get("doc_name") == current_doc:
                continue  # 跳过同一文档

            node_title = node.get("title", "").lower()
            node_summary = node.get("summary", "").lower()

            # 检查是否有相关术语
            for term in related_docs:
                if term.lower() in node_title or term.lower() in node_summary:
                    references.append({
                        "doc_name": node.get("doc_name"),
                        "title": node.get("title"),
                        "page": node.get("start_index"),
                        "relevance_term": term
                    })
                    break

            if len(references) >= 3:  # 最多返回3个关联
                break

        return references

    def search(
        self,
        query: str,
        top_k: int = 5,
        preferred_docs: List[str] = None,
        include_references: bool = True
    ) -> List[SearchResult]:
        """
        增强型搜索

        Args:
            query: 查询文本
            top_k: 返回结果数
            preferred_docs: 优先检索的文档列表
            include_references: 是否包含跨规章关联
        """
        if not self.documents:
            logger.warning("No documents loaded")
            return []

        # 解析搜索上下文
        context = self._parse_search_context(query)
        logger.info(f"Searching: '{query}' -> normalized: '{context.normalized_query}'")

        # 计算所有节点得分
        scored_nodes = []
        for global_id, node in self.node_map.items():
            score, match_details = self._calculate_enhanced_relevance(node, context, preferred_docs)
            if score > 0:
                scored_nodes.append((score, node, match_details))

        # 排序
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # 构建结果
        results = []
        for score, node, match_details in scored_nodes[:top_k]:
            # 查找跨规章关联
            cross_refs = []
            if include_references:
                cross_refs = self._find_cross_references(node, context)

            # 获取完整文本 - 优先从 section_content_map 获取
            doc_name = node.get("doc_name", "")
            title = node.get("title", "")

            # 尝试从 section_content_map 获取全文
            full_text = ""
            # 提取条款号
            section_match = re.search(r'第\s*([\d\.]+)\s*条', title)
            if not section_match:
                section_match = re.search(r'§\s*([\d\.]+)', title)
            if not section_match:
                section_match = re.search(r'^(\d+\.\d+)', title)

            if section_match:
                section_num = section_match.group(1)
                key = f"{doc_name}:{section_num}"
                full_text = self.section_content_map.get(key, "")

            # 如果没找到，使用 summary 和 content_parts
            if not full_text:
                content_parts = []
                if node.get("summary"):
                    content_parts.append(node["summary"])
                if node.get("content_parts"):
                    content_parts.extend(node["content_parts"])
                full_text = " ".join(content_parts)

            # 如果还是没有，使用 title
            if not full_text:
                full_text = title

            # 构建源文件链接
            source_link = self._get_source_link(doc_name, section_match.group(1) if section_match else None, title)

            result = SearchResult(
                node_id=node.get("node_id"),
                title=title,
                text=full_text,
                summary=node.get("summary", "") or full_text[:200],
                metadata={
                    "node_id": node.get("node_id"),
                    "title": title,
                    "page": node.get("start_index"),
                    "score": round(score, 2),
                    "source": doc_name,
                    "source_link": source_link,
                    "section_number": section_match.group(1) if section_match else None,
                    "search_method": "enhanced_multi_ccar"
                },
                relevance_score=score,
                match_details=match_details,
                cross_references=cross_refs
            )
            results.append(result)

        logger.info(f"Found {len(results)} results from {len(set(r.metadata['source'] for r in results))} documents")
        return results

    def get_section_full_content(self, doc_name: str, section_num: str) -> Optional[str]:
        """获取条款全文内容"""
        key = f"{doc_name}:{section_num}"
        return self.section_content_map.get(key)

    def _get_source_link(self, doc_name: str, section_num: Optional[str], title: str) -> str:
        """构建源文件链接"""
        # 基础URL（可以替换为实际的官方文档URL）
        base_urls = {
            "CCAR-33-R2": "https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/202203/t20220328_212762.html",
            "CCAR-25-R4": "https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201111/t20111107_45562.html",
            "CCAR-29-R2": "https://www.caac.gov.cn/XXGK/XXGK/GFXWJ/201801/t20180108_206261.html",
            "FAR-25": "https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-25",
            "FAR-33": "https://www.ecfr.gov/current/title-14/chapter-I/subchapter-E/part-33",
            "CS-25": "https://www.easa.europa.eu/en/regulations/easy-access-rules-certification-specifications-large-aeroplanes",
            "CS-E": "https://www.easa.europa.eu/en/regulations/easy-access-rules-certification-specifications-engines",
        }

        # 获取基础URL
        base_url = base_urls.get(doc_name, "")

        # 如果有条款号，添加锚点
        if section_num and base_url:
            # 对于EASA，使用 #AMC 或 #CS 格式
            if doc_name.startswith("CS-"):
                anchor = f"#CS-{section_num.replace('.', '')}"
            else:
                anchor = f"#section-{section_num}"
            return f"{base_url}{anchor}"

        # 返回markdown文件链接作为备用
        md_file = self.processed_dir / f"{doc_name}_Full.md"
        if md_file.exists():
            # 构建本地文件链接
            return f"file://{md_file}"

        return base_url

    def get_related_sections(self, doc_name: str, section_num: str, top_k: int = 3) -> List[Dict]:
        """根据条款内容获取相关条款"""
        content = self.get_section_full_content(doc_name, section_num)
        if not content:
            return []

        # 使用内容作为查询进行搜索
        results = self.search(content[:200], top_k=top_k)  # 取前200字作为查询

        # 过滤掉自己
        related = []
        for r in results:
            if not (r.metadata["source"] == doc_name and f"第{section_num}条" in r.title):
                related.append(r.to_dict())

        return related[:top_k]

    def get_document_stats(self) -> Dict[str, Dict]:
        """获取文档统计"""
        stats = {}
        for doc_name, doc_data in self.documents.items():
            doc_nodes = [n for n in self.node_map.values() if n.get("doc_name") == doc_name]
            stats[doc_name] = {
                "title": doc_data.get("doc_title", ""),
                "ccar_number": doc_data.get("ccar_number", ""),
                "total_pages": doc_data.get("total_pages", 0),
                "total_sections": doc_data.get("total_sections", 0),
                "total_nodes": len(doc_nodes)
            }
        return stats


def print_search_results(results: List[SearchResult], query: str):
    """打印搜索结果"""
    print(f"\n{'='*70}")
    print(f"查询: {query}")
    print(f"{'='*70}")

    if not results:
        print("未找到相关结果")
        return

    for i, result in enumerate(results, 1):
        print(f"\n【结果 {i}】得分: {result.relevance_score:.1f}")
        print(f"  来源: {result.metadata['source']}")
        print(f"  条款: {result.title}")
        print(f"  页码: 第{result.metadata['page']}页")

        # 匹配详情
        if result.match_details.get("professional_match"):
            print(f"  匹配: {', '.join(result.match_details['professional_match'][:3])}")

        # 内容预览
        content = result.summary or result.text or ""
        if content:
            preview = content[:150] + "..." if len(content) > 150 else content
            print(f"  内容: {preview}")

        # 跨规章关联
        if result.cross_references:
            print(f"  相关条款:")
            for ref in result.cross_references:
                print(f"    - [{ref['doc_name']}] {ref['title']} (页{ref['page']})")


# 使用示例
if __name__ == "__main__":
    kb = EnhancedMultiCCARKB("/Users/Zhuanz/AIAeroPlaneRag/data/processed")

    # 显示统计
    print("="*70)
    print("增强型多规章知识库")
    print("="*70)
    stats = kb.get_document_stats()
    for doc_name, doc_stats in stats.items():
        print(f"\n{doc_name}:")
        print(f"  标题: {doc_stats['title']}")
        print(f"  条款数: {doc_stats['total_sections']}")
        print(f"  节点数: {doc_stats['total_nodes']}")

    # 测试查询（使用专家团队的测试场景）
    test_queries = [
        "发动机防火墙的穿透性要求",  # 防火系统
        "第33.75条安全分析的具体内容和要求",  # 动力装置
        "CCAR-25机身结构强度的基本要求",  # 结构强度
        "空调系统的设计和安装要求",  # 系统设计
    ]

    for query in test_queries:
        results = kb.search(query, top_k=3)
        print_search_results(results, query)
