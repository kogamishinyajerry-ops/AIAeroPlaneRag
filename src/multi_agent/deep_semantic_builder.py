#!/usr/bin/env python3
"""
深层语义关系构建器

构建因果、依赖、参数映射等深层关系
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeepSemanticBuilder:
    """深层语义关系构建器"""

    # 航空领域因果链
    CAUSAL_CHAINS = {
        '喘振裕度不足': ['发动机喘振', '推力丧失', '飞行安全风险'],
        '防火墙失效': ['火灾蔓延', '结构损坏', '灾难性失效'],
        '转子破裂': ['非包容性破坏', '飞机损伤', '人员伤亡风险'],
        '燃油系统故障': ['发动机停车', '迫降风险', '飞行事故'],
        '液压系统失效': ['控制困难', '操纵受限', '着陆风险'],
    }

    # 条款依赖关系
    DEPENDENCY_MAP = {
        'CCAR-25-R4_25.1': ['CCAR-33-R2_33.5', 'FAR-33_33.5'],  # 运输机依赖发动机
        'CCAR-25-R4_25.903': ['CCAR-25-R4_25.561'],  # 发动机安装依赖防火
        'CCAR-29-R2_29.1': ['CCAR-33-R2_33.5'],  # 直升机依赖发动机
        'FAR-25_25.901': ['FAR-33_33.5'],
    }

    # 参数-条款映射
    PARAMETER_CLAUSES = {
        '喘振裕度': {
            'values': ['15%', '10%'],
            'clauses': ['CCAR-33-R2_33.23', 'FAR-33_33.23', 'CS-E_5'],
            'condition': '巡航状态不低于15%，起飞不低于10%'
        },
        '防火墙温度': {
            'values': ['1200°C', '2000°F'],
            'clauses': ['CCAR-33-R2_33.17', 'FAR-33_33.17'],
            'condition': '必须承受'
        },
        '转子转速': {
            'values': ['120%', '110%'],
            'clauses': ['CCAR-33-R2_33.27', 'FAR_33_33.27'],
            'condition': '最大限制转速'
        },
        '燃油容量': {
            'values': ['30分钟', '60分钟'],
            'clauses': ['CCAR-25-R2_25.953', 'FAR_25_25.953'],
            'condition': '储备飞行时间'
        },
    }

    # 测试-要求关联
    TEST_REQUIREMENT_MAP = {
        '持久试验': ['转子完整性', '寿命验证'],
        '破坏性试验': ['包容性', '破裂防护'],
        '防火试验': ['防火墙', '阻燃材料'],
        '喘振试验': ['喘振裕度', '稳定边界'],
        '疲劳试验': ['疲劳寿命', '损伤容限'],
    }

    # 部件-系统-位置层级
    COMPONENT_HIERARCHY = {
        '发动机系统': {
            '压气机': {
                '转子': ['叶片', '盘', '轴'],
                '静子': ['静子叶片', '机匣'],
            },
            '燃烧室': ['火焰筒', '喷嘴', '点火器'],
            '涡轮': {
                '涡轮转子': ['涡轮叶片', '涡轮盘'],
                '涡轮静子': ['喷嘴', '导向叶片'],
            },
        },
        '燃油系统': ['油箱', '泵', '阀门', '管路', '喷油嘴'],
        '液压系统': ['液压泵', '作动筒', '阀门', '蓄压器'],
        '防火系统': ['防火墙', '探测器', '灭火瓶'],
    }

    def __init__(self, kb_path: str):
        self.kb_path = Path(kb_path)
        self.nodes = {}
        self.edges = []

    def build_deep_relations(self, base_graph: Dict = None) -> Dict:
        """构建深层语义关系"""
        if base_graph:
            self.nodes = {n['id']: n for n in base_graph['nodes']}
            self.edges = base_graph['edges']
        else:
            # 加载基础图谱
            graph_file = self.kb_path / 'knowledge_graph' / 'final_graph.json'
            with open(graph_file) as f:
                data = json.load(f)
            self.nodes = {n['id']: n for n in data['nodes']}
            self.edges = data['edges']

        logger.info(f"基础图谱: {len(self.nodes)} 节点, {len(self.edges)} 边")

        # 1. 构建因果链
        self._build_causal_chains()

        # 2. 构建依赖关系
        self._build_dependencies()

        # 3. 构建参数映射
        self._build_parameter_mappings()

        # 4. 构建测试-要求关联
        self._build_test_relations()

        # 5. 构建部件层级
        self._build_component_hierarchy()

        # 6. 构建条款引用网络
        self._build_reference_network()

        # 7. 构建相似度增强网络
        self._build_similarity_network()

        return {
            'nodes': list(self.nodes.values()),
            'edges': self.edges,
            'metadata': {
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'depth_enhanced': True
            }
        }

    def _build_causal_chains(self):
        """构建因果链"""
        logger.info("构建因果链...")
        added = 0

        for cause, effects in self.CAUSAL_CHAINS.items():
            cause_id = f'concept_{cause}'
            if cause_id not in self.nodes:
                self.nodes[cause_id] = {
                    'id': cause_id,
                    'label': cause,
                    'type': 'concept',
                    'category': 'condition'
                }

            prev_id = cause_id
            for effect in effects:
                effect_id = f'concept_{effect}'
                if effect_id not in self.nodes:
                    self.nodes[effect_id] = {
                        'id': effect_id,
                        'label': effect,
                        'type': 'concept',
                        'category': 'effect'
                    }

                self.edges.append({
                    'source': prev_id,
                    'target': effect_id,
                    'type': 'causes',
                    'weight': 0.9
                })
                added += 1
                prev_id = effect_id

        logger.info(f"添加了 {added} 条因果链")

    def _build_dependencies(self):
        """构建依赖关系"""
        logger.info("构建依赖关系...")
        added = 0

        for main_clause, dep_clauses in self.DEPENDENCY_MAP.items():
            if main_clause not in self.nodes:
                continue

            for dep_clause in dep_clauses:
                if dep_clause in self.nodes:
                    self.edges.append({
                        'source': dep_clause,
                        'target': main_clause,
                        'type': 'dependency',
                        'weight': 0.8
                    })
                    added += 1

        logger.info(f"添加了 {added} 条依赖关系")

    def _build_parameter_mappings(self):
        """构建参数映射"""
        logger.info("构建参数映射...")
        added = 0

        for param, info in self.PARAMETER_CLAUSES.items():
            param_id = f'param_{param}'
            if param_id not in self.nodes:
                self.nodes[param_id] = {
                    'id': param_id,
                    'label': f"{param}({info['values'][0]})",
                    'type': 'parameter',
                    'values': info['values'],
                    'condition': info['condition']
                }

            for clause in info['clauses']:
                if clause in self.nodes:
                    self.edges.append({
                        'source': clause,
                        'target': param_id,
                        'type': 'specifies',
                        'weight': 0.95
                    })
                    added += 1

        logger.info(f"添加了 {added} 条参数映射")

    def _build_test_relations(self):
        """构建测试-要求关联"""
        logger.info("构建测试-要求关联...")
        added = 0

        for test_type, requirements in self.TEST_REQUIREMENT_MAP.items():
            test_id = f'test_{test_type}'
            if test_id not in self.nodes:
                self.nodes[test_id] = {
                    'id': test_id,
                    'label': test_type,
                    'type': 'test_method',
                    'category': 'test'
                }

            for req in requirements:
                # 查找相关章节
                matching_sections = [
                    n for n in self.nodes.values()
                    if n.get('type') == 'section' and
                    any(kw in n.get('title', '') for kw in [req, req.replace('完整性', ''), req.replace('防护', '')])
                ]

                for section in matching_sections[:5]:
                    self.edges.append({
                        'source': section['id'],
                        'target': test_id,
                        'type': 'tested_by',
                        'weight': 0.7
                    })
                    added += 1

        logger.info(f"添加了 {added} 条测试关联")

    def _build_component_hierarchy(self):
        """构建部件层级"""
        logger.info("构建部件层级...")
        added = 0

        def add_hierarchy(parent_id, items, level=0):
            nonlocal added
            for item in items:
                if isinstance(item, str):
                    item_id = f'comp_{item}'
                    if item_id not in self.nodes:
                        self.nodes[item_id] = {
                            'id': item_id,
                            'label': item,
                            'type': 'component',
                            'level': level
                        }

                    if parent_id:
                        self.edges.append({
                            'source': parent_id,
                            'target': item_id,
                            'type': 'part_of',
                            'weight': 0.8
                        })
                        added += 1
                    parent_id = item_id
                elif isinstance(item, dict):
                    for sub_name, sub_items in item.items():
                        sub_id = f'comp_{sub_name}'
                        if sub_id not in self.nodes:
                            self.nodes[sub_id] = {
                                'id': sub_id,
                                'label': sub_name,
                                'type': 'component',
                                'level': level
                            }

                        if parent_id:
                            self.edges.append({
                                'source': parent_id,
                                'target': sub_id,
                                'type': 'part_of',
                                'weight': 0.8
                            })
                            added += 1

                        add_hierarchy(sub_id, sub_items, level + 1)

        for system, components in self.COMPONENT_HIERARCHY.items():
            system_id = f'sys_{system}'
            if system_id not in self.nodes:
                self.nodes[system_id] = {
                    'id': system_id,
                    'label': system,
                    'type': 'system'
                }

            add_hierarchy(system_id, components)

        logger.info(f"添加了 {added} 条部件层级")

    def _build_reference_network(self):
        """构建条款引用网络"""
        logger.info("构建引用网络...")
        added = 0

        # 扫描章节内容找引用
        for node_id, node_data in list(self.nodes.items()):
            if node_data.get('type') != 'section':
                continue

            title = node_data.get('title', '')
            # 查找引用其他规章的模式
            refs = re.findall(r'(CCAR|FAR|CS)[- ]?\d+[A-Z]?', title)

            for ref in refs:
                # 找到被引用的文档节点
                ref_doc_id = f'doc_{ref}'
                if ref_doc_id in self.nodes:
                    self.edges.append({
                        'source': node_id,
                        'target': ref_doc_id,
                        'type': 'references',
                        'weight': 0.5
                    })
                    added += 1

        logger.info(f"添加了 {added} 条引用关系")

    def _build_similarity_network(self):
        """构建相似度增强网络"""
        logger.info("构建相似度网络...")
        added = 0

        # 按内容相似度连接
        section_nodes = {
            k: v for k, v in self.nodes.items()
            if v.get('type') == 'section'
        }

        # 按主题分组
        topic_keywords = {
            '强度': ['强度', '载荷', '应力', '变形'],
            '防火': ['防火', '阻燃', '火', '热'],
            '疲劳': ['疲劳', '寿命', '循环', '损伤'],
            '操作': ['操作', '控制', '飞行员', '程序'],
            '应急': ['应急', '撤离', '迫降', '故障'],
        }

        for topic, keywords in topic_keywords.items():
            topic_sections = []
            for sid, sdata in section_nodes.items():
                title = sdata.get('title', '').lower()
                if any(kw in title for kw in keywords):
                    topic_sections.append(sid)

            # 为同主题章节添加连接
            for i in range(len(topic_sections)):
                for j in range(i+1, min(i+8, len(topic_sections))):
                    # 避免重复
                    exists = any(
                        (e['source'] == topic_sections[i] and e['target'] == topic_sections[j]) or
                        (e['source'] == topic_sections[j] and e['target'] == topic_sections[i])
                        for e in self.edges
                    )
                    if not exists:
                        self.edges.append({
                            'source': topic_sections[i],
                            'target': topic_sections[j],
                            'type': f'similar_{topic}',
                            'weight': 0.5
                        })
                        added += 1

        logger.info(f"添加了 {added} 条相似度连接")

    def save(self, output_path: str = None):
        """保存增强图谱"""
        if output_path is None:
            output_path = self.kb_path / 'knowledge_graph' / 'deep_semantic_graph.json'

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'nodes': list(self.nodes.values()),
                'edges': self.edges,
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"深层语义图谱已保存: {output_path}")


__all__ = ['DeepSemanticBuilder']
