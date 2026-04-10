#!/usr/bin/env python3
"""
DeepInterpretationAgent - 深度条款解读专家

职责:
- 为每条条款生成专业设计要求解读
- 建立条款与设计任务的关联
- 识别潜在的验证要求
- 提供工程实践建议
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent.agent_base import BaseAgent, AgentTask

logger = logging.getLogger(__name__)


class DeepInterpretationAgent(BaseAgent):
    """
    深度解读 Agent

    为每条适航条款提供:
    1. 设计要求解读
    2. 验证方法建议
    3. 工程实践要点
    4. 相关条款关联
    """

    # 专业领域解读模板
    DOMAIN_TEMPLATES = {
        "防火": {
            "设计要求": [
                "使用阻燃或耐火材料",
                "防止火焰蔓延到其他区域",
                "关键系统防火隔离",
                "设置火警和灭火装置"
            ],
            "验证方法": ["防火试验", "材料阻燃测试", "系统安全性分析"],
            "工程实践": "选用经认证的防火材料，进行防火分区设计"
        },
        "结构": {
            "设计要求": [
                "满足极限载荷要求",
                "满足疲劳寿命要求",
                "考虑损伤容限",
                "防腐处理"
            ],
            "验证方法": ["静力试验", "疲劳试验", "损伤容限分析"],
            "工程实践": "选用高强轻质材料，进行表面防腐处理"
        },
        "OEI": {
            "设计要求": [
                "单发失效时保持足够推力",
                "冷却系统满足单发状态",
                "振动水平在限制范围内",
                "满足特定时段功率输出"
            ],
            "验证方法": ["150小时持久试车", "30秒OEI验证", "2.5分钟OEI验证"],
            "工程实践": "进行详细的性能分析和冷却计算"
        },
        "安全分析": {
            "设计要求": [
                "识别所有单点失效",
                "评估失效影响",
                "设计安全措施",
                "设置告警系统"
            ],
            "验证方法": ["FMEA分析", "故障树分析", "失效试验"],
            "工程实践": "建立完整的失效模式库，进行可靠性分析"
        },
        "安装": {
            "设计要求": [
                "保证接口兼容",
                "足够的安装空间",
                "维护可达性",
                "紧固可靠性"
            ],
            "验证方法": ["安装验证", "振动试验", "维护性评估"],
            "工程实践": "考虑人机工程，预留维护通道"
        },
        "控制系统": {
            "设计要求": [
                "控制冗余设计",
                "故障安全模式",
                "防止误操作",
                "系统解耦"
            ],
            "验证方法": ["仿真验证", "故障模拟", "飞行试验"],
            "工程实践": "采用冗余架构，设置逻辑隔离"
        },
        "燃油": {
            "设计要求": [
                "足够的燃油容量",
                "燃油系统可靠性",
                "燃油管理自动化",
                "应急燃油系统"
            ],
            "验证方法": ["系统试验", "飞行试验", "可靠性分析"],
            "工程实践": "设置多级燃油泵，考虑应急放油"
        },
        "操纵": {
            "设计要求": [
                "操纵面配平",
                "操纵力合理",
                "防止操纵反逆",
                "颤振抑制"
            ],
            "验证方法": ["操纵品质试验", "风洞试验", "飞行试验"],
            "工程实践": "进行详细的气动弹性分析"
        }
    }

    # 关键词映射
    KEYWORD_MAPPING = {
        # 防火相关
        "防火": "防火", "fire": "防火", "flame": "防火", "阻燃": "防火", "耐火": "防火",
        # 结构相关
        "结构": "结构", "strength": "结构", "载荷": "结构", "fatigue": "结构", "损伤": "结构",
        # 发动机相关
        "OEI": "OEI", "一发": "OEI", "功率": "OEI", "推力": "OEI", "温度": "OEI",
        # 安全相关
        "安全": "安全", "safety": "安全", "失效": "安全", "故障": "安全", "分析": "安全",
        # 安装相关
        "安装": "安装", "attachment": "安装", "连接": "安装", "mount": "安装",
        # 控制相关
        "控制": "控制系统", "control": "控制系统", "操纵": "控制系统",
        # 燃油相关
        "燃油": "燃油", "fuel": "燃油", "油箱": "燃油", "供油": "燃油"
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("DeepInterpretationAgent", knowledge_base_path)
        self.interpretations_cache = {}
        self.processed_dir = Path(knowledge_base_path)

    def get_capabilities(self) -> List[str]:
        return [
            "interpret_clauses",
            "extract_design_requirements",
            "build_clause_network",
            "generate_practical_guidance",
            "export_interpretations"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "interpret_clauses":
            return await self._interpret_clauses(task.params)
        elif action == "extract_design_requirements":
            return await self._extract_design_requirements(task.params)
        elif action == "build_clause_network":
            return await self._build_clause_network(task.params)
        elif action == "generate_practical_guidance":
            return await self._generate_practical_guidance(task.params)
        elif action == "export_interpretations":
            return await self._export_interpretations(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _classify_clause(self, title: str, content: str) -> Optional[str]:
        """分类条款到专业领域"""
        title_lower = title.lower()
        content_lower = content.lower()

        # 检查关键词映射
        for keyword, domain in self.KEYWORD_MAPPING.items():
            if keyword.lower() in title_lower or keyword.lower() in content_lower:
                return domain

        # 基于条款号模式判断
        if "33." in title or "33部" in title:
            # CCAR-33 发动机相关
            if any(kw in title_lower for kw in ["防火", "fire", "穿透", "penetration"]):
                return "防火"
            if "OEI" in title or "一发" in title:
                return "OEI"
            if "安全" in title or "safety" in title or "分析" in title:
                return "安全分析"
            if "安装" in title or "attachment" in title:
                return "安装"

        if "25." in title or "25部" in title:
            # CCAR-25 运输类飞机相关
            if "防火" in title or "fire" in title:
                return "防火"
            if "结构" in title or "structure" in title:
                return "结构"
            if "操纵" in title or "control" in title:
                return "操纵"
            if "燃油" in title or "fuel" in title:
                return "燃油"

        return None

    async def _interpret_clauses(self, params: Dict) -> Dict:
        """为所有条款生成深度解读"""
        max_clauses = params.get("max_clauses", 100)
        doc_filter = params.get("doc_filter", "")

        interpretations = []

        # 读取结构文件
        for json_file in self.processed_dir.glob("*_structure.json"):
            if doc_filter and doc_filter not in str(json_file):
                continue

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", json_file.stem)

                # 提取条款
                clauses = self._extract_clauses_from_structure(data)

                for clause in clauses[:max_clauses // len(list(self.processed_dir.glob("*_structure.json")))]:
                    domain = self._classify_clause(clause["title"], clause["content"])

                    interpretation = {
                        "doc_name": doc_name,
                        "clause_number": clause.get("number", ""),
                        "title": clause["title"],
                        "content": clause["content"][:200],
                        "domain": domain
                    }

                    if domain and domain in self.DOMAIN_TEMPLATES:
                        interpretation["design_requirements"] = self.DOMAIN_TEMPLATES[domain]["设计要求"]
                        interpretation["verification_methods"] = self.DOMAIN_TEMPLATES[domain]["验证方法"]
                        interpretation["practical_guidance"] = self.DOMAIN_TEMPLATES[domain]["工程实践"]
                    else:
                        interpretation["design_requirements"] = ["满足适航条款要求"]
                        interpretation["verification_methods"] = ["按适航要求验证"]
                        interpretation["practical_guidance"] = "参考相应咨询通告"

                    interpretations.append(interpretation)

            except Exception as e:
                logger.warning(f"Error processing {json_file}: {e}")

        # 缓存结果
        self.interpretations_cache = interpretations

        return {
            "improvements": [f"生成 {len(interpretations)} 条条款深度解读"],
            "total_interpretations": len(interpretations),
            "by_domain": self._count_by_domain(interpretations)
        }

    def _extract_clauses_from_structure(self, data: Dict) -> List[Dict]:
        """从结构数据中提取条款"""
        clauses = []
        seen = set()

        def extract(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")

                # 检查是否是条款节点
                if re.search(r'§\s*[\d.]+|第\s*[\d.]+\s*条|^\d+\.\d+', title):
                    # 提取条款号
                    match = re.search(r'([\d.]+)', title)
                    number = match.group(1) if match else ""

                    # 构建内容
                    content_parts = []
                    if node.get("summary"):
                        content_parts.append(node["summary"])
                    if node.get("content_parts"):
                        content_parts.extend(node["content_parts"])
                    content = " ".join(content_parts)

                    clause_id = f"{data.get('doc_name', '')}:{number}"
                    if clause_id not in seen:
                        clauses.append({
                            "number": number,
                            "title": title,
                            "content": content
                        })
                        seen.add(clause_id)

                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    extract(children)

        structure = data.get("structure", {})
        if isinstance(structure, dict) and "chapters" in structure:
            extract(structure["chapters"])
        elif isinstance(structure, list):
            extract(structure)

        return clauses

    def _count_by_domain(self, interpretations: List[Dict]) -> Dict[str, int]:
        """统计各领域的解读数量"""
        count = {}
        for item in interpretations:
            domain = item.get("domain", "未分类")
            count[domain] = count.get(domain, 0) + 1
        return count

    async def _export_interpretations(self, params: Dict) -> Dict:
        """导出解读结果"""
        output_path = params.get("output", str(self.processed_dir / "clause_interpretations.json"))

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "timestamp": str(Path.cwd()),
            "total": len(self.interpretations_cache),
            "by_domain": self._count_by_domain(self.interpretations_cache),
            "interpretations": self.interpretations_cache
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return {
            "improvements": [f"导出 {len(self.interpretations_cache)} 条解读到 {output_file}"],
            "output": str(output_file)
        }

    async def _extract_design_requirements(self, params: Dict) -> Dict:
        """提取设计要求"""
        requirements = []

        for interpretation in self.interpretations_cache:
            if interpretation.get("design_requirements"):
                requirements.append({
                    "clause": interpretation["title"],
                    "domain": interpretation["domain"],
                    "requirements": interpretation["design_requirements"]
                })

        return {
            "improvements": [f"提取 {len(requirements)} 项设计要求"],
            "total_requirements": len(requirements)
        }

    async def _build_clause_network(self, params: Dict) -> Dict:
        """构建条款关联网络"""
        # 按领域分组
        by_domain = {}
        for item in self.interpretations_cache:
            domain = item.get("domain", "未分类")
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(item)

        # 构建关联
        connections = []
        for domain, items in by_domain.items():
            if domain != "未分类":
                for item1 in items:
                    for item2 in items:
                        if item1["title"] != item2["title"]:
                            connections.append({
                                "source": item1["title"][:40],
                                "target": item2["title"][:40],
                                "domain": domain,
                                "relationship": "同领域相关"
                            })

        return {
            "improvements": [f"建立 {len(connections)} 条条款关联"],
            "connections": connections[:100]
        }

    async def _generate_practical_guidance(self, params: Dict) -> Dict:
        """生成工程实践指导"""
        guidance_list = []

        for interpretation in self.interpretations_cache:
            if interpretation.get("practical_guidance"):
                guidance_list.append({
                    "clause": interpretation["title"],
                    "domain": interpretation["domain"],
                    "guidance": interpretation["practical_guidance"]
                })

        return {
            "improvements": [f"生成 {len(guidance_list)} 条工程实践指导"],
            "guidance": guidance_list
        }


__all__ = ['DeepInterpretationAgent']
