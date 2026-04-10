"""
PageIndex Engine - 推理式检索引擎，替代向量相似度检索
基于 CCAR-33-R2 的层级树结构进行推理式问答
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TreeNode:
    """树节点数据结构"""
    node_id: str
    title: str
    start_index: int
    end_index: Optional[int] = None
    summary: str = ""
    text: str = ""
    nodes: List['TreeNode'] = None

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "node_id": self.node_id,
            "title": self.title,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "summary": self.summary,
            "text": self.text,
            "nodes": [node.to_dict() for node in self.nodes]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TreeNode':
        """从字典创建节点"""
        nodes = [cls.from_dict(node_data) for node_data in data.get("nodes", [])]
        return cls(
            node_id=data["node_id"],
            title=data["title"],
            start_index=data["start_index"],
            end_index=data.get("end_index"),
            summary=data.get("summary", ""),
            text=data.get("text", ""),
            nodes=nodes
        )


class PageIndexEngine:
    """
    基于 PageIndex 树结构的推理式检索引擎

    相比向量检索的优势：
    1. 保留文档原始层级结构（章节-条款）
    2. 推理式定位，而非相似度匹配
    3. 检索路径完全可追溯
    """

    def __init__(self, structure_path: str = None):
        """
        初始化 PageIndex 引擎

        Args:
            structure_path: CCAR-33-R2 结构 JSON 文件路径
        """
        self.structure_path = structure_path or "./data/processed/CCAR-33-R2_structure.json"
        self.tree_root: List[TreeNode] = []
        self.node_map: Dict[str, TreeNode] = {}
        self._load_structure()

    def _load_structure(self):
        """加载 CCAR-33-R2 树结构"""
        structure_file = Path(self.structure_path)
        if not structure_file.exists():
            logger.warning("PageIndex structure file not found: %s", self.structure_path)
            return

        try:
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.tree_root = [TreeNode.from_dict(node) for node in data.get("structure", [])]
            self._build_node_map(self.tree_root)
            logger.info("Loaded PageIndex structure with %d root nodes, %d total nodes",
                       len(self.tree_root), len(self.node_map))

        except Exception as e:
            logger.error("Failed to load PageIndex structure: %s", e)

    def _build_node_map(self, nodes: List[TreeNode]):
        """构建节点ID到节点的映射，用于快速查找"""
        for node in nodes:
            self.node_map[node.node_id] = node
            if node.nodes:
                self._build_node_map(node.nodes)

    def search_by_keywords(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        基于关键词的树搜索（无需 LLM）

        策略：
        1. 提取查询中的关键词（章节号、条款号、技术术语）
        2. 在树中匹配相关节点
        3. 返回最相关的节点
        """
        if not self.tree_root:
            logger.warning("No structure loaded for search")
            return []

        keywords = self._extract_keywords(query)
        logger.info("Searching with keywords: %s", keywords)

        scored_nodes = []
        for node in self.node_map.values():
            score = self._calculate_relevance(node, keywords, query)
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
                    "source": "CCAR-33-R2",
                    "search_method": "pageindex_tree"
                }
            })

        logger.info("PageIndex search returned %d results", len(results))
        return results

    def _extract_keywords(self, query: str) -> Dict[str, List[str]]:
        """
        从查询中提取关键词

        返回: {
            "chapters": ["A", "C"],  # 章节号
            "sections": ["33.1", "33.75"],  # 条款号
            "terms": ["防火", "安全分析"]  # 技术术语
        }
        """
        keywords = {
            "chapters": [],
            "sections": [],
            "terms": []
        }

        # 提取章节号 (A章, B章, ...)
        chapter_match = re.findall(r'([A-H])章', query, re.IGNORECASE)
        keywords["chapters"].extend([m.upper() for m in chapter_match])

        # 提取条款号 (第33.1条, 33.75, etc)
        section_match = re.findall(r'(?:第)?\s*(\d+(?:\.\d+)?)\s*(?:条)?', query)
        keywords["sections"].extend(section_match)

        # 提取中文技术术语（2-4字的词组）
        chinese_terms = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
        keywords["terms"].extend(chinese_terms)

        # 拆分复合词，提取单个有意义的关键词
        for term in chinese_terms:
            # 如果是4字词，尝试拆分成两个2字词
            if len(term) == 4:
                keywords["terms"].append(term[:2])
                keywords["terms"].append(term[2:])

        return keywords

    def _calculate_relevance(self, node: TreeNode, keywords: Dict[str, List[str]], query: str) -> float:
        """
        计算节点与查询的相关性得分

        评分规则：
        - 章节匹配: +20分
        - 条款号匹配: +30分
        - 标题包含术语: +10分/词
        - 摘要/文本包含术语: +5分/词
        """
        score = 0.0
        node_text = (node.title + " " + (node.summary or "") + " " + (node.text or "")).lower()
        query_lower = query.lower()

        # 章节匹配
        for chapter in keywords["chapters"]:
            if chapter in node.title:
                score += 20

        # 条款号匹配
        for section in keywords["sections"]:
            if section in node.title or section in node_text:
                score += 30

        # 术语匹配
        for term in keywords["terms"]:
            term_lower = term.lower()
            if term_lower in node.title.lower():
                score += 10
            elif term_lower in node_text:
                score += 5

        # 部分匹配（query 包含在节点文本中）
        if query_lower in node_text:
            score += 15

        return score

    def get_node_by_id(self, node_id: str) -> Optional[TreeNode]:
        """根据节点 ID 获取节点"""
        return self.node_map.get(node_id)

    def get_tree_path(self, node_id: str) -> List[Dict]:
        """
        获取到指定节点的路径（用于追溯）

        返回从根节点到目标节点的完整路径
        """
        target = self.node_map.get(node_id)
        if not target:
            return []

        path = []
        current = target

        # 向上追溯
        while current:
            path.insert(0, {
                "node_id": current.node_id,
                "title": current.title,
                "page": current.start_index
            })

            # 找到父节点
            current = self._find_parent(current)

        return path

    def _find_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """查找节点的父节点"""
        for potential_parent in self.node_map.values():
            if node in potential_parent.nodes:
                return potential_parent
        return None

    def get_all_sections(self) -> List[Dict]:
        """获取所有条款节点"""
        sections = []
        for node in self.node_map.values():
            if "第" in node.title and "条" in node.title:
                sections.append({
                    "node_id": node.node_id,
                    "title": node.title,
                    "page": node.start_index,
                    "summary": node.summary
                })
        return sorted(sections, key=lambda x: x["page"])


# 使用示例
if __name__ == "__main__":
    # 初始化引擎
    engine = PageIndexEngine()

    # 测试查询
    test_queries = [
        "第33.75条关于安全分析的要求",
        "发动机的防火要求是什么",
        "涡轮发动机的试验要求",
        "喘振和失速特性"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print('='*60)
        results = engine.search_by_keywords(query, top_k=2)
        for i, result in enumerate(results, 1):
            print(f"\n结果 {i}:")
            print(f"  标题: {result['metadata']['title']}")
            print(f"  页码: {result['metadata']['page']}")
            print(f"  得分: {result['metadata']['score']}")
            print(f"  内容: {result['text'][:150]}...")
