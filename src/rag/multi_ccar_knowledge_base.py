"""
多规章联合 PageIndex 知识库
支持 CCAR-25, CCAR-29, CCAR-33 等多种规章的联合检索
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RegulationDocument:
    """规章文档"""
    doc_name: str
    doc_title: str
    ccar_number: str
    total_pages: int
    total_sections: int
    structure_path: str


@dataclass
class TreeNode:
    """树节点"""
    node_id: str
    title: str
    start_index: int
    end_index: Optional[int] = None
    summary: str = ""
    text: str = ""
    nodes: List['TreeNode'] = None
    doc_name: str = ""  # 所属文档

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []

    def to_dict(self) -> Dict:
        d = {
            "node_id": self.node_id,
            "title": self.title,
            "start_index": self.start_index,
            "summary": self.summary,
            "nodes": [node.to_dict() for node in self.nodes]
        }
        if self.end_index:
            d["end_index"] = self.end_index
        if self.text:
            d["text"] = self.text
        if self.doc_name:
            d["doc_name"] = self.doc_name
        return d

    @classmethod
    def from_dict(cls, data: Dict, doc_name: str = "") -> 'TreeNode':
        nodes = [cls.from_dict(n, doc_name) for n in data.get("nodes", [])]
        return cls(
            node_id=data["node_id"],
            title=data["title"],
            start_index=data["start_index"],
            end_index=data.get("end_index"),
            summary=data.get("summary", ""),
            text=data.get("text", ""),
            nodes=nodes,
            doc_name=doc_name or data.get("doc_name", "")
        )


class MultiCCARKnowledgeBase:
    """
    多规章联合知识库

    支持同时检索多个 CCAR 规章：
    - CCAR-25: 运输类飞机
    - CCAR-29: 运输类旋翼航空器
    - CCAR-33: 航空发动机
    - CCAR-23: 正常类、实用类飞机
    - CCAR-27: 正常类旋翼航空器
    等
    """

    def __init__(self, processed_dir: str = "./data/processed"):
        self.processed_dir = Path(processed_dir)
        self.documents: Dict[str, RegulationDocument] = {}
        self.node_map: Dict[str, TreeNode] = {}
        self._load_all_regulations()

    def _count_sections(self, structure: List) -> int:
        """递归统计条款数量"""
        count = 0
        for node in structure:
            if "条" in node.get("title", ""):
                count += 1
            if node.get("nodes"):
                count += self._count_sections(node["nodes"])
        return count

    def _load_all_regulations(self):
        """加载所有可用的规章结构"""
        structure_files = list(self.processed_dir.glob("*_structure.json"))

        for file_path in structure_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc = RegulationDocument(
                    doc_name=data["doc_name"],
                    doc_title=data.get("doc_title", ""),
                    ccar_number=data.get("ccar_number", ""),
                    total_pages=data.get("total_pages", 0),
                    total_sections=data.get("total_sections", self._count_sections(data.get("structure", []))),
                    structure_path=str(file_path)
                )
                self.documents[doc.doc_name] = doc

                # 构建节点映射（带文档前缀）
                doc_prefix = doc.doc_name
                for node_data in data.get("structure", []):
                    self._build_node_map(node_data, doc_prefix)

                logger.info(f"Loaded {doc.doc_name}: {doc.total_sections} sections")

            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")

        logger.info(f"Total documents loaded: {len(self.documents)}")
        logger.info(f"Total nodes indexed: {len(self.node_map)}")

    def _build_node_map(self, node_data: Dict, doc_name: str):
        """递归构建节点映射"""
        node = TreeNode.from_dict(node_data, doc_name)

        # 添加全局唯一 ID（文档名:节点ID）
        global_id = f"{doc_name}:{node.node_id}"
        self.node_map[global_id] = node
        self.node_map[node.node_id] = node  # 保留向后兼容

        for child in node.nodes:
            self._build_node_map(child.to_dict(), doc_name)

    def search(self, query: str, top_k: int = 5,
               preferred_docs: List[str] = None) -> List[Dict]:
        """
        跨规章检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            preferred_docs: 优先检索的文档列表（如 ["CCAR-33", "CCAR-25"]）
        """
        if not self.documents:
            logger.warning("No documents loaded")
            return []

        keywords = self._extract_keywords(query)
        logger.info(f"Searching with keywords: {keywords}")

        scored_nodes = []
        for global_id, node in self.node_map.items():
            score = self._calculate_relevance(node, keywords, query, preferred_docs)
            if score > 0:
                scored_nodes.append((score, node))

        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, node in scored_nodes[:top_k]:
            results.append({
                "text": node.summary or node.text or node.title,
                "original_text": node.text,
                "metadata": {
                    "node_id": node.node_id,
                    "title": node.title,
                    "page": node.start_index,
                    "score": score,
                    "source": node.doc_name,
                    "search_method": "multi_ccar_pageindex"
                }
            })

        logger.info(f"Search returned {len(results)} results from {len(set(r['metadata']['source'] for r in results))} documents")
        return results

    def _extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """提取查询关键词"""
        import re
        keywords = {
            "ccar_numbers": [],
            "section_numbers": [],
            "terms": []
        }

        # CCAR 部号 (CCAR-25, CCAR-33)
        ccar_match = re.findall(r'CCAR[-\s]*(\d+)', query, re.IGNORECASE)
        keywords["ccar_numbers"].extend([m.upper() for m in ccar_match])

        # 条款号 (25.1, 33.75)
        section_match = re.findall(r'(\d+(?:\.\d+)?)', query)
        keywords["section_numbers"].extend(section_match)

        # 中文术语
        chinese_terms = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
        keywords["terms"].extend(chinese_terms)

        # 拆分复合词
        for term in chinese_terms:
            if len(term) == 4:
                keywords["terms"].extend([term[:2], term[2:]])

        return keywords

    def _calculate_relevance(self, node: TreeNode, keywords: Dict,
                            query: str, preferred_docs: List[str]) -> float:
        """计算相关性得分"""
        score = 0.0
        node_text = (node.title + " " + (node.summary or "") + " " + (node.text or "")).lower()
        query_lower = query.lower()

        # 文档优先级
        if preferred_docs and node.doc_name in preferred_docs:
            score += 10

        # CCAR 部号匹配
        for ccar in keywords["ccar_numbers"]:
            if ccar in node.doc_name:
                score += 25

        # 条款号匹配
        for section in keywords["section_numbers"]:
            if section in node.title or section in node_text:
                score += 30

        # 术语匹配
        for term in keywords["terms"]:
            term_lower = term.lower()
            if term_lower in node.title.lower():
                score += 10
            elif term_lower in node_text:
                score += 5

        # 查询字符串匹配
        if query_lower in node_text:
            score += 15

        return score

    def get_document_stats(self) -> Dict[str, Dict]:
        """获取各规章统计信息"""
        stats = {}
        for doc_name, doc in self.documents.items():
            doc_nodes = [n for n in self.node_map.values() if n.doc_name == doc_name]
            stats[doc_name] = {
                "title": doc.doc_title,
                "ccar_number": doc.ccar_number,
                "total_pages": doc.total_pages,
                "total_sections": doc.total_sections,
                "total_nodes": len(doc_nodes)
            }
        return stats

    def get_all_sections_by_doc(self, doc_name: str) -> List[Dict]:
        """获取指定规章的所有条款"""
        sections = []
        for node in self.node_map.values():
            if node.doc_name == doc_name and "条" in node.title:
                sections.append({
                    "node_id": node.node_id,
                    "title": node.title,
                    "page": node.start_index,
                    "summary": node.summary,
                    "doc_name": node.doc_name
                })
        return sorted(sections, key=lambda x: x["page"])


# 使用示例
if __name__ == "__main__":
    kb = MultiCCARKnowledgeBase("/Users/Zhuanz/AIAeroPlaneRag/data/processed")

    print("="*60)
    print("多规章知识库统计")
    print("="*60)
    stats = kb.get_document_stats()
    for doc_name, doc_stats in stats.items():
        print(f"\n{doc_name}:")
        print(f"  标题: {doc_stats['title']}")
        print(f"  CCAR号: {doc_stats['ccar_number']}")
        print(f"  条款数: {doc_stats['total_sections']}")

    # 测试跨规章查询
    test_queries = [
        "发动机防火要求",  # CCAR-33
        "起飞距离要求",      # CCAR-25, CCAR-29
        "安全分析",         # CCAR-33, CCAR-25
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print('='*60)
        results = kb.search(query, top_k=3)
        for r in results:
            print(f"  [{r['metadata']['source']}] {r['metadata']['title']} (页{r['metadata']['page']}, 得分{r['metadata']['score']})")
