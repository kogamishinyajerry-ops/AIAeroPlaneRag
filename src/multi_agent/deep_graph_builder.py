#!/usr/bin/env python3
"""
深度知识图谱构建器

专注于挖掘深层关系和跨文档关联
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeepGraphBuilder:
    """深度知识图谱构建器"""

    # 实体类型
    ENTITY_TYPES = {
        'regulation': '规章',
        'chapter': '章节',
        'section': '条款',
        'subsection': '子条款',
        'component': '部件',
        'system': '系统',
        'requirement': '要求',
        'test': '测试',
        'parameter': '参数',
        'value': '数值',
        'condition': '条件',
        'reference': '引用'
    }

    # 关系类型
    RELATION_TYPES = {
        'contains': '包含',
        'refines': '细化',
        'references': '引用',
        'equivalent': '等效',
        'requires': '要求',
        'tested_by': '测试',
        'applies_to': '适用于',
        'defines': '定义',
        'limits': '限制',
        'depends_on': '依赖',
        'exempts': '豁免',
        'modifies': '修改',
        'supersedes': '替代',
        'contradicts': '冲突',
        'related_to': '相关',
        'part_of': '组成部分',
        'instance_of': '实例'
    }

    # 部件-系统映射
    COMPONENT_SYSTEM_MAP = {
        '压气机': '发动机系统',
        '涡轮': '发动机系统',
        '燃烧室': '发动机系统',
        '转子': '发动机系统',
        'APU': '辅助动力系统',
        '燃油系统': '燃油系统',
        '液压系统': '液压系统',
        '起落架': '起落架系统',
        '襟翼': '机翼系统',
        '副翼': '机翼系统',
        '防火墙': '防火系统',
    }

    # 参数-部件映射
    PARAMETER_COMPONENT_MAP = {
        '喘振裕度': '压气机',
        '温度': '涡轮',
        '转速': '转子',
        '推力': '发动机',
        '压力': '燃油系统',
        '流量': '燃油系统',
    }

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.nodes = {}
        self.edges = []
        self.entity_cache = defaultdict(set)
        self.relation_cache = defaultdict(list)

    def build_comprehensive_graph(self) -> Dict[str, Any]:
        """构建综合知识图谱"""
        logger.info("开始构建深度知识图谱...")

        # 1. 从所有文档提取实体
        self._extract_all_entities()

        # 2. 发现层次关系
        self._discover_hierarchical_relations()

        # 3. 发现跨文档关系
        self._discover_cross_document_relations()

        # 4. 发现语义关系
        self._discover_semantic_relations()

        # 5. 发现部件-系统关系
        self._discover_component_system_relations()

        # 6. 发现参数-部件关系
        self._discover_parameter_component_relations()

        # 7. 发现测试关系
        self._discover_test_relations()

        # 8. 构建等效关系
        self._build_equivalence_relations()

        # 9. 添加引用关系
        self._add_reference_relations()

        # 10. 创建文档中心节点
        self._create_document_center_nodes()

        logger.info(f"图谱构建完成: {len(self.nodes)} 节点, {len(self.edges)} 边")

        return {
            'nodes': self.nodes,
            'edges': self.edges,
            'stats': self._get_stats()
        }

    def _extract_all_entities(self):
        """提取所有实体"""
        structure_files = list(self.kb_path.glob("*_structure.json"))

        for structure_file in structure_files:
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get('doc_name', structure_file.stem.replace('_structure', ''))

                # 创建文档节点
                doc_id = f"doc:{doc_name}"
                self.nodes[doc_id] = {
                    'id': doc_id,
                    'label': doc_name,
                    'type': 'regulation',
                    'document': doc_name
                }

                # 获取结构数据 - 兼容CS-E的dict格式和其他文档的list格式
                structure = data.get('structure', [])
                if isinstance(structure, dict):
                    # CS-E格式: {'chapters': [{'id': 'A', 'title': '...', 'sections': [...]}]}
                    chapters = structure.get('chapters', [])
                    for chapter in chapters:
                        chapter_title = chapter.get('title', '')
                        chapter_id = chapter.get('id', '')
                        # 创建章节节点
                        if chapter_id:
                            chapter_node_id = f"{doc_name}:chapter_{chapter_id}"
                            self.nodes[chapter_node_id] = {
                                'id': chapter_node_id,
                                'label': chapter_title,
                                'type': 'chapter',
                                'title': chapter_title,
                                'document': doc_name,
                                'level': 0
                            }
                            # 章节到文档的边
                            self.edges.append({
                                'source': doc_id,
                                'target': chapter_node_id,
                                'type': 'contains',
                                'weight': 1.0
                            })
                            # 处理章节下的条款
                            sections = chapter.get('sections', [])
                            self._extract_cse_sections(sections, doc_name, chapter_node_id, level=1)
                else:
                    # 标准格式 (list)
                    self._extract_from_structure(structure, doc_name, doc_id, level=0)

            except Exception as e:
                logger.warning(f"提取实体失败 {structure_file}: {e}")

    def _extract_cse_sections(self, sections: List, doc_name: str, parent_id: str, level: int):
        """处理CS-E/FAR-33的条款 (E.xxx 和 § xx.x 格式)"""
        for section in sections:
            if not isinstance(section, dict):
                continue

            number = section.get('number', '')
            title = section.get('title', '')
            summary = section.get('summary', '') or section.get('content', '') or ''

            # 标准化条款号: 移除 § 前缀和空格
            normalized = number.strip()
            if normalized.startswith('§'):
                normalized = normalized[1:].strip()
            # 跳过空的或无效的条款号
            if not normalized or not re.match(r'[\d.E]+', normalized.split()[0] if ' ' in normalized else normalized):
                continue

            # 提取条款号 - 匹配 E.10, 33.1, 33.201 等格式
            # 格式: [字母.]数字或[字母.]数字.数字...
            clause_match = re.match(r'([A-Z]?\.)?(\d+(?:\.\d+)*)', normalized)
            if not clause_match:
                continue

            prefix = clause_match.group(1) or ''  # E. 或空的
            num = clause_match.group(2)
            clean_number = f"{prefix}{num}"

            node_id = f"{doc_name}:{clean_number}"
            self.nodes[node_id] = {
                'id': node_id,
                'label': clean_number,
                'type': 'section',
                'title': title,
                'number': clean_number,
                'document': doc_name,
                'level': level
            }
            self.entity_cache['section'].add(node_id)

            # 添加层次边
            self.edges.append({
                'source': parent_id,
                'target': node_id,
                'type': 'contains',
                'weight': 1.0
            })

            # 提取关键词和参数
            self._extract_keywords_from_text(title + ' ' + summary, node_id, doc_name)
            self._extract_parameters_from_text(title + ' ' + summary, node_id, doc_name)

    def _extract_from_structure(self, nodes: List, doc_name: str, parent_id: str, level: int):
        """从结构中递归提取实体"""
        for node in nodes:
            if not isinstance(node, dict):
                continue

            title = node.get('title', '')
            content = node.get('summary', '') or node.get('content', '')

            # 提取条款号 - 支持多种格式:
            # § 33.1 (FAR/CCAR英文格式)
            # 第33.1条 (CCAR中文格式)
            # E.10 (CS-E格式)
            section_match = re.search(r'§\s*([\d.]+[a-z]?)', title)
            if not section_match:
                section_match = re.search(r'第(\d+\.\d+)条', title)
            if section_match:
                section_num = section_match.group(1)
                node_id = f"{doc_name}:{section_num}"

                # 创建条款节点
                self.nodes[node_id] = {
                    'id': node_id,
                    'label': f"{section_num}",
                    'type': 'section',
                    'title': title,
                    'document': doc_name,
                    'level': level
                }

                # 添加到缓存
                self.entity_cache['section'].add(node_id)

                # 添加层次边
                if parent_id != f"doc:{doc_name}":
                    self.edges.append({
                        'source': parent_id,
                        'target': node_id,
                        'type': 'contains',
                        'weight': 1.0
                    })

                # 提取关键词作为实体
                self._extract_keywords_from_text(title + ' ' + content, node_id, doc_name)

                # 提取参数
                self._extract_parameters_from_text(title + ' ' + content, node_id, doc_name)

            # 递归处理子节点
            children = node.get('nodes', []) or node.get('sections', [])
            if children:
                new_parent = node_id if section_match else parent_id
                self._extract_from_structure(children, doc_name, new_parent, level + 1)

    def _extract_keywords_from_text(self, text: str, source_id: str, doc_name: str):
        """从文本中提取关键词实体"""
        # 航空领域关键词
        keywords = [
            '发动机', '压气机', '涡轮', '燃烧室', '转子', 'APU',
            '燃油系统', '液压系统', '电气系统', '空调系统',
            '防火', '防爆', '应急', '撤离',
            '起落架', '机翼', '机身', '襟翼', '副翼',
            '喘振裕度', '温度', '压力', '转速', '推力'
        ]

        for keyword in keywords:
            if keyword in text:
                keyword_id = f"keyword:{keyword}"
                if keyword_id not in self.nodes:
                    self.nodes[keyword_id] = {
                        'id': keyword_id,
                        'label': keyword,
                        'type': 'component' if keyword in ['压气机', '涡轮', '转子', 'APU', '起落架', '襟翼'] else 'system',
                    }

                # 添加提及关系
                self.edges.append({
                    'source': source_id,
                    'target': keyword_id,
                    'type': 'mentions',
                    'weight': 0.5
                })

    def _extract_parameters_from_text(self, text: str, source_id: str, doc_name: str):
        """从文本中提取参数"""
        # 提取数值参数
        patterns = [
            r'(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s*度',
            r'(\d+(?:\.\d+)?)\s*分钟',
            r'(\d+(?:\.\d+)?)\s*小时',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                param_id = f"param:{match}_{source_id}"
                self.nodes[param_id] = {
                    'id': param_id,
                    'label': f"值:{match}",
                    'type': 'value',
                    'value': match
                }

                self.edges.append({
                    'source': source_id,
                    'target': param_id,
                    'type': 'specifies',
                    'weight': 0.3
                })

    def _discover_hierarchical_relations(self):
        """发现层次关系"""
        logger.info("发现层次关系...")

        # 按文档分组章节
        doc_sections = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.get('type') == 'section':
                doc = node.get('document', '')
                if doc:
                    doc_sections[doc].append(node_id)

        # 为每个文档添加层次边
        for doc, sections in doc_sections.items():
            # 按章节号排序
            sections_sorted = sorted(
                [s for s in sections if self.nodes[s]['label'].replace('.', '').isdigit()],
                key=lambda x: [int(i) for i in self.nodes[x]['label'].split('.')]
            )

            # 添加相邻关系
            for i in range(len(sections_sorted) - 1):
                self.edges.append({
                    'source': sections_sorted[i],
                    'target': sections_sorted[i + 1],
                    'type': 'follows',
                    'weight': 0.2
                })

    def _discover_cross_document_relations(self):
        """发现跨文档关系"""
        logger.info("发现跨文档关系...")

        # 已知的等效条款映射
        equivalent_mappings = [
            ('CCAR-25-R4:25.1', 'FAR-25:25.1', 'CS-25:25.1'),
            ('CCAR-33-R2:33.5', 'FAR-33:33.5', 'CS-E:CS-E.5'),
            ('CCAR-29-R2:29.1', 'FAR-29:29.1', 'CS-29:29.1'),
            ('CCAR-23:23.1', 'FAR-23:23.1'),
        ]

        for mapping in equivalent_mappings:
            for i in range(len(mapping)):
                for j in range(i + 1, len(mapping)):
                    if mapping[i] in self.nodes and mapping[j] in self.nodes:
                        self.edges.append({
                            'source': mapping[i],
                            'target': mapping[j],
                            'type': 'equivalent',
                            'weight': 1.0
                        })

        # 按主题分组添加相关关系
        topic_groups = {
            '发动机': ['CCAR-33-R2', 'FAR-33', 'CS-E'],
            '运输机': ['CCAR-25-R4', 'FAR-25', 'CS-25'],
            '直升机': ['CCAR-29-R2', 'FAR-29', 'CS-29'],
        }

        for topic, docs in topic_groups.items():
            for i in range(len(docs)):
                for j in range(i + 1, len(docs)):
                    doc_i = f"doc:{docs[i]}"
                    doc_j = f"doc:{docs[j]}"
                    if doc_i in self.nodes and doc_j in self.nodes:
                        self.edges.append({
                            'source': doc_i,
                            'target': doc_j,
                            'type': 'related_to',
                            'weight': 0.7
                        })

    def _discover_semantic_relations(self):
        """发现语义关系"""
        logger.info("发现语义关系...")

        # 基于标题相似度发现关系
        sections_by_type = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.get('type') == 'section':
                title = node.get('title', '')
                # 分类
                if '防火' in title or '火' in title:
                    sections_by_type['防火'].append(node_id)
                elif '喘振' in title:
                    sections_by_type['喘振'].append(node_id)
                elif '转子' in title:
                    sections_by_type['转子'].append(node_id)
                elif '燃油' in title:
                    sections_by_type['燃油'].append(node_id)

        # 为同类型添加边
        for topic, sections in sections_by_type.items():
            for i in range(len(sections)):
                for j in range(i + 1, len(sections)):
                    self.edges.append({
                        'source': sections[i],
                        'target': sections[j],
                        'type': 'related_to',
                        'weight': 0.6
                    })

    def _discover_component_system_relations(self):
        """发现部件-系统关系"""
        logger.info("发现部件-系统关系...")

        for component, system in self.COMPONENT_SYSTEM_MAP.items():
            comp_id = f"keyword:{component}"
            sys_id = f"keyword:{system}"

            # 确保节点存在
            if comp_id not in self.nodes:
                self.nodes[comp_id] = {
                    'id': comp_id,
                    'label': component,
                    'type': 'component'
                }
            if sys_id not in self.nodes:
                self.nodes[sys_id] = {
                    'id': sys_id,
                    'label': system,
                    'type': 'system'
                }

            self.edges.append({
                'source': comp_id,
                'target': sys_id,
                'type': 'part_of',
                'weight': 0.8
            })

    def _discover_parameter_component_relations(self):
        """发现参数-部件关系"""
        logger.info("发现参数-部件关系...")

        for param, component in self.PARAMETER_COMPONENT_MAP.items():
            param_id = f"keyword:{param}"
            comp_id = f"keyword:{component}"

            if param_id in self.nodes and comp_id in self.nodes:
                self.edges.append({
                    'source': param_id,
                    'target': comp_id,
                    'type': 'applies_to',
                    'weight': 0.7
                })

    def _discover_test_relations(self):
        """发现测试关系"""
        logger.info("发现测试关系...")

        for node_id, node in self.nodes.items():
            if node.get('type') == 'section':
                title = node.get('title', '')
                # 查找测试相关条款
                if '试验' in title or '测试' in title:
                    # 从标题中提取被测对象
                    for component in ['压气机', '涡轮', '转子', '燃烧室', 'APU']:
                        if component in title:
                            comp_id = f"keyword:{component}"
                            if comp_id in self.nodes:
                                self.edges.append({
                                    'source': node_id,
                                    'target': comp_id,
                                    'type': 'tested_by',
                                    'weight': 0.9
                                })

    def _build_equivalence_relations(self):
        """构建等效关系"""
        logger.info("构建等效关系...")

        # 为不同规章的相同条款号添加等效关系
        section_equivalents = defaultdict(list)
        for node_id, node in self.nodes.items():
            if node.get('type') == 'section':
                section = node.get('label', '')
                if section:
                    section_equivalents[section].append(node_id)

        for section, nodes in section_equivalents.items():
            if len(nodes) > 1:
                for i in range(len(nodes)):
                    for j in range(i + 1, len(nodes)):
                        self.edges.append({
                            'source': nodes[i],
                            'target': nodes[j],
                            'type': 'equivalent',
                            'weight': 0.8
                        })

    def _add_reference_relations(self):
        """添加引用关系"""
        logger.info("添加引用关系...")

        # 章节引用关系
        chapter_order = {
            'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7,
            'H': 8, 'I': 9, 'J': 10, 'K': 11, 'L': 12
        }

        for node_id, node in self.nodes.items():
            if node.get('type') == 'section':
                doc = node.get('document', '')
                label = node.get('label', '')

                # 解析章节
                if '.' in label:
                    parts = label.split('.')
                    main_section = parts[0]

                    # 查找相关子节
                    for other_id, other in self.nodes.items():
                        if other_id != node_id and other.get('document') == doc:
                            other_label = other.get('label', '')
                            if other_label.startswith(main_section + '.') and other_label.count('.') > label.count('.'):
                                self.edges.append({
                                    'source': node_id,
                                    'target': other_id,
                                    'type': 'refines',
                                    'weight': 0.5
                                })

    def _create_document_center_nodes(self):
        """创建文档中心节点"""
        logger.info("创建文档中心节点...")

        # 为每个领域创建中心节点
        domain_centers = {
            '发动机领域': ['CCAR-33-R2', 'FAR-33', 'CS-E'],
            '运输机领域': ['CCAR-25-R4', 'FAR-25', 'CS-25'],
            '直升机领域': ['CCAR-29-R2', 'FAR-29', 'CS-29'],
        }

        for domain, docs in domain_centers.items():
            center_id = f"domain:{domain}"
            self.nodes[center_id] = {
                'id': center_id,
                'label': domain,
                'type': 'domain',
            }

            for doc in docs:
                doc_id = f"doc:{doc}"
                if doc_id in self.nodes:
                    self.edges.append({
                        'source': center_id,
                        'target': doc_id,
                        'type': 'contains',
                        'weight': 0.4
                    })

    def _get_stats(self) -> Dict:
        """获取统计信息"""
        node_types = defaultdict(int)
        for node in self.nodes.values():
            node_types[node.get('type', 'unknown')] += 1

        relation_types = defaultdict(int)
        for edge in self.edges:
            relation_types[edge.get('type', 'unknown')] += 1

        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': dict(node_types),
            'relation_types': dict(relation_types)
        }

    def save_graph(self, output_path: str = None):
        """保存图谱"""
        if output_path is None:
            output_path = self.kb_path / "knowledge_graph" / "deep_graph.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)

        graph_data = {
            'nodes': self.nodes,
            'edges': self.edges,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'version': '2.0',
                'stats': self._get_stats()
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        logger.info(f"图谱已保存到: {output_path}")


__all__ = ['DeepGraphBuilder']
