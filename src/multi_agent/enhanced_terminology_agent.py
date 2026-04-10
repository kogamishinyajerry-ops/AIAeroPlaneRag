#!/usr/bin/env python3
"""
增强术语提取Agent

专注于深度提取航空专业术语和构建语义网络
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict, Counter
from datetime import datetime
from itertools import combinations

from .agent_base import BaseAgent, AgentTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedTerminologyAgent(BaseAgent):
    """
    增强术语提取Agent

    核心功能：
    1. 深度术语提取（专业术语、缩写、复合术语）
    2. 语义关系网络（同义、上下位、相关）
    3. 领域本体构建（分类体系、属性定义）
    4. 缩写自动检测（中英文缩写映射）
    """

    # 航空领域术语模式
    TERM_PATTERNS = {
        # 缩写模式 (APU, OEI, ETOPS等)
        "abbreviation": re.compile(r'\b([A-Z]{2,6})\b'),

        # 中文专业术语模式
        "chinese_term": re.compile(r'[\u4e00-\u9fff]{2,6}'),

        # 英文专业术语模式
        "english_term": re.compile(r'\b[a-zA-Z]{4,20}\b'),

        # 数字+字母组合 (25.831, CCAR-25等)
        "code": re.compile(r'\b(?:§)?\d+(?:\.\d+)?(?:[a-z])?\b'),

        # 复合术语 (防火墙、防火测试、防火材料等)
        "compound": re.compile(r'[\u4e00-\u9fff]+(?:测试|系统|装置|要求|规定|保护|材料)'),
    }

    # 已知航空术语库
    AVIATION_TERMS = {
        # 发动机相关
        "发动机": ["engine", "powerplant", "动力装置", "引擎"],
        "APU": ["辅助动力装置", "Auxiliary Power Unit"],
        "涡轮": ["turbine", "透平"],
        "燃烧室": ["combustion chamber", "燃烧器"],
        "压气机": ["compressor", "压缩机"],
        "喷嘴": ["nozzle", "喷管"],

        # 飞行条件
        "OEI": ["One Engine Inoperative", "单发失效", "一发失效"],
        "ETOPS": ["Extended Operations", "延伸航程运行"],
        "VMC": ["Minimum Control Speed", "最小操纵速度"],
        "VNE": ["Never Exceed Speed", "不可逾越速度"],

        # 系统相关
        "液压系统": ["hydraulic system", "液压"],
        "燃油系统": ["fuel system", "燃油"],
        "空调系统": ["air conditioning system", "空调", "环境控制系统"],
        "电气系统": ["electrical system", "电气"],

        # 安全相关
        "防火墙": ["firewall", "防火"],
        "防爆": ["explosion proof", "隔爆"],
        "应急": ["emergency", "紧急"],
        "撤离": ["evacuation", "逃生"],

        # 结构相关
        "机身": ["fuselage", "机体"],
        "机翼": ["wing", "翼"],
        "起落架": ["landing gear", "起落装置"],
        "襟翼": ["flap", "襟翼"],
        "方向舵": ["rudder"],
        "升降舵": ["elevator"],

        # 适航相关
        "适航": ["airworthiness", "适航性"],
        "型号合格证": ["Type Certificate", "TC"],
        "生产许可证": ["Production Certificate", "PC"],
        "持续适航": ["Continued Airworthiness"],

        # 测试相关
        "台架测试": ["bench test", "地面台架试验"],
        "飞行测试": ["flight test", "试飞"],
        "耐久性测试": ["endurance test", "持久试验"],
        "破坏性测试": ["destructive test", "破坏试验"],
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("EnhancedTerminologyAgent", knowledge_base_path)

        # 术语库
        self.terms: Dict[str, Dict] = {}  # term_id -> term_data
        self.occurrences: Dict[str, Set[str]] = defaultdict(set)  # term -> clauses
        self.co_occurrences: Dict[Tuple[str, str], int] = Counter()  # (term1, term2) -> count
        self.semantic_relations: Dict[str, List[Dict]] = defaultdict(list)  # term -> relations

    def get_capabilities(self) -> List[str]:
        return [
            "extract_comprehensive_terms",
            "build_semantic_network",
            "detect_abbreviations",
            "generate_domain_ontology",
            "find_synonyms",
            "classify_terms"
        ]

    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        action = task.action

        if action == "extract_comprehensive_terms":
            return await self._extract_comprehensive_terms(task.params)
        elif action == "build_semantic_network":
            return await self._build_semantic_network(task.params)
        elif action == "detect_abbreviations":
            return await self._detect_abbreviations(task.params)
        elif action == "generate_domain_ontology":
            return await self._generate_domain_ontology(task.params)
        elif action == "find_synonyms":
            return await self._find_synonyms(task.params)
        elif action == "classify_terms":
            return await self._classify_terms(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _extract_comprehensive_terms(self, params: Dict) -> Dict:
        """全面提取术语"""
        improvements = []
        min_freq = params.get("min_freq", 2)
        max_docs = params.get("max_docs", 20)

        # 1. 从结构文件中提取
        for structure_file in list(self.kb_path.glob("*_structure.json"))[:max_docs]:
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))
                extracted = await self._extract_terms_from_structure(data, doc_name)
                improvements.append(f"{doc_name}: 提取了 {extracted['terms']} 个术语")

            except Exception as e:
                logger.warning(f"提取术语失败 {structure_file}: {e}")

        # 2. 过滤低频术语
        filtered_terms = {k: v for k, v in self.terms.items() if v.get("frequency", 0) >= min_freq}

        # 3. 保存术语库
        term_dir = self.kb_path / "terminology"
        term_dir.mkdir(exist_ok=True)

        with open(term_dir / "comprehensive_terms.json", 'w', encoding='utf-8') as f:
            json.dump({
                "terms": filtered_terms,
                "metadata": {
                    "total_terms": len(filtered_terms),
                    "min_frequency": min_freq,
                    "generated_at": datetime.now().isoformat()
                }
            }, f, ensure_ascii=False, indent=2)

        improvements.append(f"保存了 {len(filtered_terms)} 个高频术语（频率 >= {min_freq}）")

        return {
            "improvements": improvements,
            "metrics": {
                "total_terms": len(self.terms),
                "filtered_terms": len(filtered_terms),
                "co_occurrence_pairs": len(self.co_occurrences)
            }
        }

    async def _extract_terms_from_structure(self, data: Dict, doc_name: str) -> Dict:
        """从结构数据中提取术语"""
        term_count = 0

        def process_nodes(nodes, path=""):
            nonlocal term_count

            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                summary = node.get("summary", "")
                content = " ".join(node.get("content_parts", []))
                full_text = f"{title} {summary} {content}"

                # 获取条款号
                section_match = re.search(r'§\s*(\d+\.\d+[a-z]*)', title)
                clause_id = f"{doc_name}:§{section_match.group(1)}" if section_match else f"{doc_name}:{title[:30]}"

                # 提取各种类型的术语
                terms_in_text = set()

                # 1. 已知航空术语
                for known_term, synonyms in self.AVIATION_TERMS.items():
                    if known_term in full_text:
                        terms_in_text.add(known_term)
                        for syn in synonyms:
                            if syn in full_text:
                                terms_in_text.add(syn)

                # 2. 缩写检测
                abbreviations = self.TERM_PATTERNS["abbreviation"].findall(full_text)
                common_abbrevs = {"APU", "OEI", "ETOPS", "VMC", "VNE", "TC", "PC", "FAR", "CCAR", "CS"}
                for abbr in abbreviations:
                    if abbr in common_abbrevs:
                        terms_in_text.add(abbr)

                # 3. 中文专业术语
                chinese_terms = self.TERM_PATTERNS["chinese_term"].findall(full_text)
                for term in chinese_terms:
                    if len(term) >= 2 and self._is_likely_term(term, full_text):
                        terms_in_text.add(term)

                # 4. 英文专业术语
                english_terms = self.TERM_PATTERNS["english_term"].findall(full_text)
                for term in english_terms:
                    if len(term) >= 4 and term[0].isupper():
                        terms_in_text.add(term.lower())

                # 5. 复合术语
                compounds = self.TERM_PATTERNS["compound"].findall(full_text)
                terms_in_text.update(compounds)

                # 6. 数值术语
                percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', full_text)
                for pct in percentages:
                    term_id = f"value:{pct}%"
                    if term_id not in self.terms:
                        self.terms[term_id] = {
                            "id": term_id,
                            "text": f"{pct}%",
                            "type": "value",
                            "category": "percentage",
                            "frequency": 0
                        }
                    self.terms[term_id]["frequency"] += 1
                    self.terms[term_id]["clauses"] = self.terms[term_id].get("clauses", []) + [clause_id]
                    term_count += 1

                # 保存提取的术语
                for term in terms_in_text:
                    if len(term) < 2:
                        continue

                    term_id = term.lower().replace(" ", "_")

                    if term_id not in self.terms:
                        self.terms[term_id] = {
                            "id": term_id,
                            "text": term,
                            "frequency": 0,
                            "clauses": [],
                            "type": self._classify_term_type(term),
                            "category": self._classify_term_category(term)
                        }

                    self.terms[term_id]["frequency"] += 1
                    self.terms[term_id]["clauses"].append(clause_id)
                    self.occurrences[term].add(clause_id)
                    term_count += 1

                # 记录共现关系
                term_list = list(terms_in_text)
                for t1, t2 in combinations(term_list, 2):
                    if t1 != t2:
                        self.co_occurrences[(t1, t2)] += 1

                # 递归处理子节点
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    current_path = f"{path}/{title[:30]}" if path else title[:30]
                    process_nodes(children, current_path)

        # 处理结构
        structure = data.get("structure", [])
        if isinstance(structure, list):
            process_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            process_nodes(structure["chapters"])

        return {"terms": term_count}

    def _is_likely_term(self, text: str, context: str) -> bool:
        """判断是否可能是专业术语"""
        # 常见的航空术语后缀
        term_suffixes = [
            "系统", "装置", "设备", "测试", "试验", "要求", "规定",
            "保护", "控制", "监测", "指示", "记录", "报警", "防火",
            "防爆", "应急", "撤离", "液压", "燃油", "电气", "电子"
        ]

        for suffix in term_suffixes:
            if text.endswith(suffix):
                return True

        # 检查是否在专业语境中
        technical_contexts = ["要求", "规定", "必须", "应当", "符合", "满足"]
        for ctx in technical_contexts:
            if ctx in context and text in context:
                return True

        return False

    def _classify_term_type(self, term: str) -> str:
        """分类术语类型"""
        if term.upper() == term and len(term) <= 6:
            return "abbreviation"
        elif any(c in term for c in "一二三四五六七八九十百分"):
            return "numeric"
        elif re.match(r'^[\u4e00-\u9fff]+$', term):
            return "chinese"
        elif re.match(r'^[a-zA-Z\s]+$', term):
            return "english"
        else:
            return "mixed"

    def _classify_term_category(self, term: str) -> str:
        """分类术语领域"""
        categories = {
            "发动机": ["发动机", "引擎", "engine", "turbine", "combustor", "压气机", "燃烧室"],
            "飞行": ["飞行", "flight", "起飞", "降落", "爬升", "巡航", "下降"],
            "系统": ["系统", "system", "液压", "燃油", "电气", "空调"],
            "安全": ["安全", "safety", "防火", "防爆", "应急", "emergency"],
            "结构": ["结构", "structure", "机身", "机翼", "起落架", "襟翼"],
            "测试": ["测试", "test", "试验", "验证", "verification"],
            "适航": ["适航", "airworthiness", "规章", "regulation", "CCAR", "FAR"],
        }

        for category, keywords in categories.items():
            if any(kw in term for kw in keywords):
                return category

        return "other"

    async def _build_semantic_network(self, params: Dict) -> Dict:
        """构建语义网络"""
        improvements = []

        # 1. 基于共现构建关联
        min_co_occurrence = params.get("min_co_occurrence", 2)

        for (t1, t2), count in self.co_occurrences.items():
            if count >= min_co_occurrence:
                # 添加语义关系
                self.semantic_relations[t1].append({
                    "target": t2,
                    "relation": "co_occurs",
                    "weight": count
                })
                self.semantic_relations[t2].append({
                    "target": t1,
                    "relation": "co_occurs",
                    "weight": count
                })

        improvements.append(f"构建了 {len(self.co_occurrences)} 个共现关系")

        # 2. 基于已知同义词构建关系
        synonym_count = 0
        for known_term, synonyms in self.AVIATION_TERMS.items():
            if known_term in self.terms:
                for syn in synonyms:
                    if syn in self.terms:
                        self.semantic_relations[known_term].append({
                            "target": syn,
                            "relation": "synonym",
                            "weight": 1.0
                        })
                        synonym_count += 1

        improvements.append(f"添加了 {synonym_count} 个同义词关系")

        # 3. 保存语义网络
        term_dir = self.kb_path / "terminology"
        term_dir.mkdir(exist_ok=True)

        with open(term_dir / "semantic_network.json", 'w', encoding='utf-8') as f:
            json.dump(dict(self.semantic_relations), f, ensure_ascii=False, indent=2)

        return {
            "improvements": improvements,
            "metrics": {
                "total_relations": sum(len(rels) for rels in self.semantic_relations.values()),
                "synonym_relations": synonym_count
            }
        }

    async def _detect_abbreviations(self, params: Dict) -> Dict:
        """检测缩写"""
        improvements = []

        # 缩写映射
        abbreviation_map = {}

        # 1. 从已知库中提取
        for full_form, abbreviations in self.AVIATION_TERMS.items():
            for abbr in abbreviations:
                if abbr.upper() == abbr and len(abbr) <= 6:
                    if abbr not in abbreviation_map:
                        abbreviation_map[abbr] = []
                    abbreviation_map[abbr].append(full_form)

        # 2. 从文本中检测缩写定义模式
        # 如 "辅助动力装置 (APU)" 或 "APU (Auxiliary Power Unit)"
        definition_patterns = [
            re.compile(r'([\u4e00-\u9fff]+(?:装置|系统|设备)?)\s*\(([A-Z]{2,6})\)'),
            re.compile(r'([A-Z]{2,6})\s*\(([^)]+)\)'),
        ]

        for structure_file in list(self.kb_path.glob("*_structure.json"))[:10]:
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", "")

                def scan_text(text):
                    for pattern in definition_patterns:
                        matches = pattern.findall(text)
                        for match in matches:
                            if len(match) == 2:
                                term, abbr = match
                                # 确定哪个是缩写
                                if abbr.upper() == abbr:
                                    if abbr not in abbreviation_map:
                                        abbreviation_map[abbr] = []
                                    abbreviation_map[abbr].append(term)

                def scan_nodes(nodes):
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue
                        title = node.get("title", "")
                        content = " ".join(node.get("content_parts", []))
                        scan_text(title)
                        scan_text(content)
                        children = node.get("nodes", []) or node.get("sections", [])
                        if children:
                            scan_nodes(children)

                structure = data.get("structure", [])
                if isinstance(structure, list):
                    scan_nodes(structure)
                elif isinstance(structure, dict) and "chapters" in structure:
                    scan_nodes(structure["chapters"])

            except Exception as e:
                logger.warning(f"检测缩写失败 {structure_file}: {e}")

        # 保存缩写映射
        term_dir = self.kb_path / "terminology"
        term_dir.mkdir(exist_ok=True)

        with open(term_dir / "abbreviations.json", 'w', encoding='utf-8') as f:
            json.dump(abbreviation_map, f, ensure_ascii=False, indent=2)

        improvements.append(f"检测到 {len(abbreviation_map)} 个缩写映射")

        return {"improvements": improvements}

    async def _generate_domain_ontology(self, params: Dict) -> Dict:
        """生成领域本体"""
        improvements = []

        # 构建分类层次
        ontology = {
            "categories": {},
            "relations": [],
            "axioms": []
        }

        # 按类别组织术语
        for term_id, term_data in self.terms.items():
            category = term_data.get("category", "other")
            if category not in ontology["categories"]:
                ontology["categories"][category] = {
                    "name": category,
                    "terms": [],
                    "subcategories": {}
                }
            ontology["categories"][category]["terms"].append(term_data)

        # 添加已知关系
        for known_term, related in self.AVIATION_TERMS.items():
            category = self._classify_term_category(known_term)
            if category in ontology["categories"]:
                for rel in related:
                    ontology["relations"].append({
                        "source": known_term,
                        "target": rel,
                        "type": "synonym"
                    })

        # 保存本体
        term_dir = self.kb_path / "terminology"
        term_dir.mkdir(exist_ok=True)

        with open(term_dir / "domain_ontology.json", 'w', encoding='utf-8') as f:
            json.dump(ontology, f, ensure_ascii=False, indent=2)

        improvements.append(f"生成了 {len(ontology['categories'])} 个类别的本体")

        return {
            "improvements": improvements,
            "metrics": {
                "categories": len(ontology["categories"]),
                "relations": len(ontology["relations"])
            }
        }

    async def _find_synonyms(self, params: Dict) -> Dict:
        """查找同义词"""
        term = params.get("term")
        if not term:
            return {"synonyms": []}

        synonyms = set()

        # 1. 从已知库查找
        for known_term, related in self.AVIATION_TERMS.items():
            if term in known_term or known_term in term:
                synonyms.update(related)
            if term in related:
                synonyms.add(known_term)

        # 2. 从语义网络查找
        if term in self.semantic_relations:
            for rel in self.semantic_relations[term]:
                if rel.get("relation") == "synonym":
                    synonyms.add(rel["target"])

        return {
            "term": term,
            "synonyms": list(synonyms),
            "count": len(synonyms)
        }

    async def _classify_terms(self, params: Dict) -> Dict:
        """分类术语"""
        improvements = []

        # 统计各类别
        category_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for term_data in self.terms.values():
            category = term_data.get("category", "other")
            term_type = term_data.get("type", "unknown")
            category_counts[category] += 1
            type_counts[term_type] += 1

        improvements.append(f"分类了 {len(self.terms)} 个术语")

        return {
            "improvements": improvements,
            "metrics": {
                "by_category": dict(category_counts),
                "by_type": dict(type_counts)
            }
        }


__all__ = ['EnhancedTerminologyAgent']
