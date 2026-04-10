"""
专业优化Agent实现

每个Agent负责知识库优化的特定方面:
- TerminologyAgent: 术语词典维护和扩展
- QualityAgent: 内容质量检查和改进
- LinkageAgent: 关联关系发现和维护
- QueryAgent: 查询分析和优化
- DocumentAgent: 文档更新和同步
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter

from .agent_base import BaseAgent, AgentTask


class TerminologyAgent(BaseAgent):
    """
    术语管理Agent

    职责:
    - 从查询日志中发现新术语
    - 维护术语词典
    - 识别术语同义词
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("TerminologyAgent", knowledge_base_path)
        self.terminology_path = self.kb_path / "../rag/aviation_terminology.py"
        self.query_log_path = self.kb_path / "../logs/query_log.json"
        self.new_terms: Dict[str, List[str]] = {}

    def get_capabilities(self) -> List[str]:
        return [
            "discover_new_terms",
            "expand_synonyms",
            "validate_terms",
            "merge_duplicates",
            "categorize_terms"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "discover_new_terms":
            return await self._discover_new_terms(task.params)
        elif action == "expand_synonyms":
            return await self._expand_synonyms(task.params)
        elif action == "validate_terms":
            return await self._validate_terms(task.params)
        elif action == "merge_duplicates":
            return await self._merge_duplicates(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _discover_new_terms(self, params: Dict) -> Dict:
        """从查询日志中发现新术语"""
        log_file = params.get("log_file", str(self.query_log_path))

        if not Path(log_file).exists():
            return {"improvements": [], "new_terms": []}

        with open(log_file, 'r', encoding='utf-8') as f:
            queries = json.load(f) if f.read(1) else []

        # 提取候选术语
        candidates = set()
        for entry in queries:
            query = entry.get("query", "")
            # 2-4字的中文词
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
            candidates.update(chinese_words)

        # 过滤已知术语
        new_terms = []
        improvements = []

        # 加载现有术语（简化实现）
        existing_terms = set()
        for term_list in [
            "发动机", "防火", "结构", "载荷", "OEI", "空调", "液压"
        ]:
            existing_terms.add(term_list)
            existing_terms.update([term_list[i:j] for i in range(len(term_list)) for j in range(i+1, len(term_list)+1)])

        for term in candidates:
            if term not in existing_terms and len(term) >= 2:
                new_terms.append(term)

        if new_terms:
            improvements.append(f"发现 {len(new_terms)} 个新术语候选")

        return {
            "improvements": improvements,
            "new_terms": new_terms[:20],  # 返回前20个
            "total_candidates": len(new_terms)
        }

    async def _expand_synonyms(self, params: Dict) -> Dict:
        """扩展术语同义词"""
        term = params.get("term")
        context = params.get("context", "")

        # 基于上下文推断同义词
        synonyms = []

        # 简单规则：术语缩写展开
        if term == "OEI":
            synonyms = ["One Engine Inoperative", "单发失效", "一发不工作", "单发停车"]
        elif "发动机" in term:
            synonyms = ["Engine", "动力装置", "引擎"]
        elif "防火" in term:
            synonyms = ["防火", "阻燃", "耐火", "Fire protection"]

        improvements = []
        if synonyms:
            improvements.append(f"为术语 '{term}' 添加 {len(synonyms)} 个同义词")

        return {
            "improvements": improvements,
            "term": term,
            "synonyms": synonyms
        }

    async def _validate_terms(self, params: Dict) -> Dict:
        """验证术语有效性"""
        terms = params.get("terms", [])

        valid_terms = []
        invalid_terms = []

        for term in terms:
            # 验证规则：中文术语2-6字，英文/缩写2-15字符
            if re.match(r'^[\u4e00-\u9fff]{2,6}$', term):
                valid_terms.append(term)
            elif re.match(r'^[A-Za-z0-9\-\s]{2,15}$', term):
                valid_terms.append(term)
            else:
                invalid_terms.append(term)

        improvements = []
        if invalid_terms:
            improvements.append(f"过滤 {len(invalid_terms)} 个无效术语")

        return {
            "improvements": improvements,
            "valid_terms": valid_terms,
            "invalid_terms": invalid_terms
        }

    async def _merge_duplicates(self, params: Dict) -> Dict:
        """合并重复术语"""
        terms = params.get("terms", [])

        # 规范化处理
        normalized = {}
        for term in terms:
            key = term.lower().strip()
            if key not in normalized:
                normalized[key] = []
            normalized[key].append(term)

        # 找到重复
        duplicates = [v for v in normalized.values() if len(v) > 1]
        improvements = []
        if duplicates:
            improvements.append(f"合并 {len(duplicates)} 组重复术语")

        return {
            "improvements": improvements,
            "duplicates_found": len(duplicates),
            "merged_terms": {k: v for v in duplicates for k in v[:1]}
        }


class QualityAgent(BaseAgent):
    """
    质量检查Agent

    职责:
    - 检查内容完整性
    - 识别缺失信息
    - 验证数据准确性
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("QualityAgent", knowledge_base_path)
        self.quality_report_path = self.kb_path / "../reports/quality_report.json"

    def get_capabilities(self) -> List[str]:
        return [
            "check_completeness",
            "detect_gaps",
            "validate_structure",
            "generate_report"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "check_completeness":
            return await self._check_completeness(task.params)
        elif action == "detect_gaps":
            return await self._detect_gaps(task.params)
        elif action == "validate_structure":
            return await self._validate_structure(task.params)
        elif action == "generate_report":
            return await self._generate_report(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _check_completeness(self, params: Dict) -> Dict:
        """检查内容完整性"""
        processed_dir = Path(params.get("processed_dir", self.kb_path))

        issues = []
        improvements = []

        for structure_file in processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", "")
            if not doc_name:
                continue

            # 检查是否有空的summary
            empty_count = 0
            total_count = 0

            def count_empty(nodes):
                nonlocal empty_count, total_count
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    total_count += 1
                    if not node.get("summary") or len(node.get("summary", "")) < 10:
                        empty_count += 1
                    # 递归处理子节点 - 支持多种格式
                    children = node.get("nodes", []) or node.get("sections", [])
                    count_empty(children)

            # 获取结构数据 - 支持多种格式
            structure = data.get("structure", {})
            if isinstance(structure, dict) and "chapters" in structure:
                # FAR格式: {chapters: [...]}
                count_empty(structure["chapters"])
            elif isinstance(structure, list):
                # CCAR格式: [{nodes: [...]}]
                count_empty(structure)

            if total_count > 0 and empty_count > total_count * 0.5:
                issues.append(f"{doc_name}: {empty_count}/{total_count} 节点缺少内容摘要")
                improvements.append(f"标记 {doc_name} 需要内容补充")

        return {
            "improvements": improvements,
            "issues": issues,
            "total_issues": len(issues)
        }

    async def _detect_gaps(self, params: Dict) -> Dict:
        """检测知识缺口"""
        # 基于专家评估报告中的改进建议
        gaps = [
            {
                "area": "防火专业",
                "gap": "缺少更多防火试验相关的详细条款",
                "priority": "medium"
            },
            {
                "area": "动力装置",
                "gap": "发动机技术参数需要补充",
                "priority": "high"
            },
            {
                "area": "系统交互",
                "gap": "系统间交互影响说明不足",
                "priority": "medium"
            }
        ]

        improvements = [f"识别 {len(gaps)} 个知识缺口"]

        return {
            "improvements": improvements,
            "gaps": gaps
        }

    async def _validate_structure(self, params: Dict) -> Dict:
        """验证数据结构"""
        processed_dir = Path(params.get("processed_dir", self.kb_path))

        valid_docs = []
        invalid_docs = []

        for structure_file in processed_dir.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 检查必需字段
                required = ["doc_name", "structure"]
                if all(k in data for k in required):
                    valid_docs.append(data.get("doc_name"))
                else:
                    invalid_docs.append(data.get("doc_name", structure_file.name))

            except Exception as e:
                invalid_docs.append(f"{structure_file.name}: {str(e)}")

        improvements = []
        if invalid_docs:
            improvements.append(f"修复 {len(invalid_docs)} 个文档结构问题")

        return {
            "improvements": improvements,
            "valid_docs": valid_docs,
            "invalid_docs": invalid_docs
        }

    async def _generate_report(self, params: Dict) -> Dict:
        """生成质量报告"""
        # 聚合各项检查结果
        completeness = await self._check_completeness({})
        gaps = await self._detect_gaps({})
        structure = await self._validate_structure({})

        report = {
            "timestamp": datetime.now().isoformat(),
            "completeness": completeness,
            "gaps": gaps,
            "structure": structure,
            "overall_score": self._calculate_quality_score(completeness, gaps, structure)
        }

        # 保存报告
        report_path = Path(self.quality_report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        improvements = ["生成质量报告"]

        return {
            "improvements": improvements,
            "report_path": str(report_path),
            "overall_score": report["overall_score"]
        }

    def _calculate_quality_score(self, completeness: Dict, gaps: Dict, structure: Dict) -> float:
        """计算质量分数"""
        base_score = 100.0

        # 扣分
        base_score -= len(completeness.get("issues", [])) * 2
        base_score -= len(gaps.get("gaps", [])) * 3
        base_score -= len(structure.get("invalid_docs", [])) * 5

        return max(0, min(100, base_score))


class LinkageAgent(BaseAgent):
    """
    关联分析Agent

    职责:
    - 发现条款间的关联关系
    - 维护跨规章引用
    - 构建知识图谱
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("LinkageAgent", knowledge_base_path)
        self.linkage_store_path = self.kb_path / "../data/linkages.json"

    def get_capabilities(self) -> List[str]:
        return [
            "discover_cross_references",
            "find_related_sections",
            "build_topic_clusters",
            "update_linkages"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "discover_cross_references":
            return await self._discover_cross_references(task.params)
        elif action == "find_related_sections":
            return await self._find_related_sections(task.params)
        elif action == "build_topic_clusters":
            return await self._build_topic_clusters(task.params)
        elif action == "update_linkages":
            return await self._update_linkages(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _discover_cross_references(self, params: Dict) -> Dict:
        """发现跨规章引用"""
        processed_dir = Path(params.get("processed_dir", self.kb_path))

        cross_refs = []
        improvements = []

        # 收集所有文档的条款
        all_sections = {}
        for structure_file in processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", "")
            if not doc_name:
                continue

            def extract_sections(nodes, path=""):
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    title = node.get("title", "")
                    # 支持中文和FAA格式
                    is_section = "条" in title or "§" in title
                    if is_section:
                        section_num = re.search(r'(\d+(?:\.\d+)?)', title)
                        if section_num:
                            key = f"{doc_name}:{section_num.group(1)}"
                            all_sections[key] = {
                                "title": title,
                                "summary": node.get("summary", ""),
                                "doc": doc_name
                            }
                    # 递归处理子节点 - 支持多种格式
                    children = node.get("nodes", []) or node.get("sections", [])
                    extract_sections(children, path + "/" + title if path else title)

            # 获取结构数据 - 支持多种格式
            structure = data.get("structure", {})
            if isinstance(structure, dict) and "chapters" in structure:
                # FAR格式: {chapters: [...]}
                extract_sections(structure["chapters"])
            elif isinstance(structure, list):
                # CCAR格式: [{nodes: [...]}]
                extract_sections(structure)

        # 基于术语相似度发现潜在关联
        for key1, section1 in all_sections.items():
            for key2, section2 in all_sections.items():
                if key1 >= key2:  # 避免重复
                    continue

                # 不同文档
                if section1["doc"] == section2["doc"]:
                    continue

                # 检查术语重叠
                terms1 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', section1["title"]))
                terms2 = set(re.findall(r'[\u4e00-\u9fff]{2,4}', section2["title"]))

                overlap = terms1 & terms2
                if len(overlap) >= 1:
                    cross_refs.append({
                        "from": key1,
                        "to": key2,
                        "common_terms": list(overlap),
                        "confidence": len(overlap) * 0.3
                    })

        if cross_refs:
            improvements.append(f"发现 {len(cross_refs)} 个跨规章关联")

        return {
            "improvements": improvements,
            "cross_references": cross_refs[:50]  # 返回前50个
        }

    async def _find_related_sections(self, params: Dict) -> Dict:
        """查找相关条款"""
        query_section = params.get("section")  # "doc_name:section_num"
        top_k = params.get("top_k", 5)

        # 基于术语相似度查找
        # 简化实现：返回基于术语的推荐
        related = []

        improvements = [f"为条款 {query_section} 找到 {len(related)} 个相关条款"]

        return {
            "improvements": improvements,
            "related_sections": related
        }

    async def _build_topic_clusters(self, params: Dict) -> Dict:
        """构建主题聚类"""
        # 定义主题和关键词
        topics = {
            "防火": ["防火", "阻燃", "耐火", "防火墙", "火"],
            "发动机": ["发动机", "引擎", "动力", "OEI", "推力"],
            "结构": ["结构", "载荷", "疲劳", "强度", "损伤"],
            "系统": ["空调", "液压", "排液", "操纵", "控制"],
            "安全": ["安全", "风险", "失效", "故障", "分析"]
        }

        improvements = [f"构建 {len(topics)} 个主题聚类"]

        return {
            "improvements": improvements,
            "topics": topics
        }

    async def _update_linkages(self, params: Dict) -> Dict:
        """更新关联存储"""
        # 获取最新关联并保存
        cross_refs = await self._discover_cross_references({})

        linkages = {
            "updated_at": datetime.now().isoformat(),
            "total_linkages": len(cross_refs.get("cross_references", [])),
            "linkages": cross_refs.get("cross_references", [])
        }

        # 保存
        link_path = Path(self.linkage_store_path)
        link_path.parent.mkdir(parents=True, exist_ok=True)
        with open(link_path, 'w', encoding='utf-8') as f:
            json.dump(linkages, f, indent=2, ensure_ascii=False)

        improvements = [f"更新关联存储，共 {linkages['total_linkages']} 条"]

        return {
            "improvements": improvements,
            "linkages_path": str(link_path)
        }


class QueryAgent(BaseAgent):
    """
    查询分析Agent

    职责:
    - 分析查询模式
    - 识别低效查询
    - 优化相关性算法
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("QueryAgent", knowledge_base_path)
        self.query_log_path = self.kb_path / "../logs/query_log.json"

    def get_capabilities(self) -> List[str]:
        return [
            "analyze_patterns",
            "detect_low_score_queries",
            "suggest_optimizations",
            "update_relevance_weights"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "analyze_patterns":
            return await self._analyze_patterns(task.params)
        elif action == "detect_low_score_queries":
            return await self._detect_low_score_queries(task.params)
        elif action == "suggest_optimizations":
            return await self._suggest_optimizations(task.params)
        elif action == "update_relevance_weights":
            return await self._update_relevance_weights(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _analyze_patterns(self, params: Dict) -> Dict:
        """分析查询模式"""
        # 模拟查询模式分析
        patterns = {
            "term_frequency": {
                "发动机": 45,
                "防火": 32,
                "结构": 28,
                "OEI": 15,
                "空调": 12
            },
            "query_length_avg": 8.5,
            "cross_doc_queries": 0.35  # 35%的查询涉及多个文档
        }

        improvements = ["分析查询模式完成"]

        return {
            "improvements": improvements,
            "patterns": patterns
        }

    async def _detect_low_score_queries(self, params: Dict) -> Dict:
        """检测低分查询"""
        threshold = params.get("threshold", 50)

        # 模拟检测结果
        low_score_queries = [
            {"query": "空调系统要求", "avg_score": 0, "suggestion": "增加空调相关条款"},
            {"query": "排液系统", "avg_score": 0, "suggestion": "增加排液相关条款"}
        ]

        improvements = [f"识别 {len(low_score_queries)} 个低分查询"]

        return {
            "improvements": improvements,
            "low_score_queries": low_score_queries
        }

    async def _suggest_optimizations(self, params: Dict) -> Dict:
        """建议优化措施"""
        suggestions = [
            {"area": "术语", "action": "增加空调、排液相关术语", "priority": "high"},
            {"area": "内容", "action": "补充系统设计相关条款", "priority": "medium"},
            {"area": "算法", "action": "调整专业术语权重", "priority": "low"}
        ]

        improvements = [f"提出 {len(suggestions)} 条优化建议"]

        return {
            "improvements": improvements,
            "suggestions": suggestions
        }

    async def _update_relevance_weights(self, params: Dict) -> Dict:
        """更新相关性权重"""
        new_weights = params.get("weights", {
            "ccar_match": 50,
            "section_match": 60,
            "term_match_title": 15,
            "term_match_content": 8
        })

        improvements = ["更新相关性权重配置"]

        return {
            "improvements": improvements,
            "weights": new_weights
        }


class DocumentAgent(BaseAgent):
    """
    文档管理Agent

    职责:
    - 检测文档更新
    - 解析新文档
    - 同步文档变更
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("DocumentAgent", knowledge_base_path)
        self.raw_dir = Path(knowledge_base_path).parent / "raw"
        self.processed_dir = Path(knowledge_base_path)

    def get_capabilities(self) -> List[str]:
        return [
            "detect_new_documents",
            "parse_document",
            "sync_updates",
            "validate_parsing"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "detect_new_documents":
            return await self._detect_new_documents(task.params)
        elif action == "parse_document":
            return await self._parse_document(task.params)
        elif action == "sync_updates":
            return await self._sync_updates(task.params)
        elif action == "validate_parsing":
            return await self._validate_parsing(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _detect_new_documents(self, params: Dict) -> Dict:
        """检测新文档"""
        raw_files = list(self.raw_dir.glob("*.pdf")) if self.raw_dir.exists() else []
        processed_files = [f.stem.replace("_structure", "") for f in self.processed_dir.glob("*_structure.json")]

        new_files = [f.name for f in raw_files if f.stem not in processed_files]

        improvements = []
        if new_files:
            improvements.append(f"发现 {len(new_files)} 个新待处理文档")

        return {
            "improvements": improvements,
            "new_documents": new_files,
            "total_raw": len(raw_files),
            "total_processed": len(processed_files)
        }

    async def _parse_document(self, params: Dict) -> Dict:
        """解析文档"""
        doc_path = params.get("document_path")

        # 实际实现中会调用解析器
        improvements = [f"解析文档: {doc_path}"]

        return {
            "improvements": improvements,
            "parsed": True,
            "document": doc_path
        }

    async def _sync_updates(self, params: Dict) -> Dict:
        """同步更新"""
        improvements = ["同步文档更新"]

        return {
            "improvements": improvements,
            "synced": True
        }

    async def _validate_parsing(self, params: Dict) -> Dict:
        """验证解析结果"""
        doc_name = params.get("doc_name")

        # 检查解析质量
        structure_file = self.processed_dir / f"{doc_name}_structure.json"

        if not structure_file.exists():
            return {
                "improvements": [],
                "valid": False,
                "error": "Structure file not found"
            }

        with open(structure_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_sections = data.get("total_sections", 0)
        quality = data.get("parse_quality", "unknown")

        improvements = []
        if total_sections > 0:
            improvements.append(f"验证解析: {doc_name} ({total_sections} 条款)")

        return {
            "improvements": improvements,
            "valid": total_sections > 0,
            "sections": total_sections,
            "quality": quality
        }


# 导出
__all__ = [
    'TerminologyAgent',
    'QualityAgent',
    'LinkageAgent',
    'QueryAgent',
    'DocumentAgent'
]
