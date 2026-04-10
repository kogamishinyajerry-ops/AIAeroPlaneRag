#!/usr/bin/env python3
"""
Enhanced DeepInterpretationAgent - 深度条款解读专家 (增强版)

深度分析每条条款:
1. 设计要求解读 - 提取具体设计指标
2. 验证方法建议 - 详细的验证程序
3. 工程实践指导 - 实际实施建议
4. 跨条款关联 - 发现相关条款
5. 设计任务映射 - 映射到具体设计任务
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent.agent_base import BaseAgent, AgentTask

logger = logging.getLogger(__name__)


class EnhancedDeepInterpretationAgent(BaseAgent):
    """
    增强深度解读 Agent

    为每条适航条款提供深度专业解读:
    1. 逐句分析条款内容
    2. 提取具体设计参数
    3. 建立验证程序
    4. 关联相关条款
    5. 生成实施检查清单
    """

    # 详细专业领域解读库
    DOMAIN_KNOWLEDGE = {
        "防火": {
            "keywords": ["防火", "fire", "阻燃", "耐火", "火焰", "穿透", "penetration"],
            "design_requirements": [
                "材料防火等级: 必须使用阻燃或耐火材料",
                "防火墙设计: 设置防火隔离区域",
                "穿透件保护: 穿越防火墙的部件必须密封或防火",
                "火警系统: 设置火警探测装置",
                "灭火系统: 配备固定灭火系统"
            ],
            "verification_methods": [
                "防火试验: 按CCAR-33部附录B进行防火试验",
                "材料测试: 阻燃性测试(垂直、水平、45度)",
                "穿透件测试: 验证穿透件的防火性能",
                "系统评估: 整体防火安全性评估"
            ],
            "design_parameters": [
                "阻燃时间要求: 通常要求15分钟阻燃",
                "防火隔离距离: 根据部件类型确定",
                "温度限制: 材料在特定温度下的性能"
            ],
            "implementation_checklist": [
                "□ 选择经认证的防火材料",
                "□ 进行材料阻燃性测试",
                "□ 设计防火隔离区域",
                "□ 验证穿透件防火性能",
                "□ 安装火警探测系统",
                "□ 配备灭火设备",
                "✓ 完成防火符合性验证"
            ]
        },
        "结构": {
            "keywords": ["结构", "structure", "载荷", "load", "强度", "strength", "疲劳", "fatigue", "损伤", "damage"],
            "design_requirements": [
                "极限载荷: 承受1.5倍限制载荷",
                "疲劳强度: 满足疲劳寿命要求",
                "损伤容限: 结构在损伤后仍能承受限制载荷",
                "材料认证: 使用经适航认证的材料",
                "腐蚀防护: 表面防腐处理"
            ],
            "verification_methods": [
                "静力试验: 验证极限载荷承载能力",
                "疲劳试验: 验证疲劳寿命",
                "损伤容限试验: 验证损伤后的承载能力",
                "材料测试: 材料力学性能测试"
            ],
            "design_parameters": [
                "安全系数: 通常取1.5",
                "疲劳寿命: 根据使用循环次数确定",
                "裂纹扩展: 控制裂纹扩展速率"
            ],
            "implementation_checklist": [
                "□ 进行结构应力分析",
                "□ 选择满足强度要求的材料",
                "□ 进行疲劳寿命计算",
                "□ 设计损伤容限结构",
                "□ 表面防腐处理",
                "□ 静力试验验证",
                "□ 疲劳试验验证",
                "✓ 完成结构符合性验证"
            ]
        },
        "OEI": {
            "keywords": ["OEI", "一发", "单发", "功率", "power", "推力", "thrust", "温度", "temperature"],
            "design_requirements": [
                "30秒OEI功率: 一发失效后30秒内达到额定功率",
                "2.5分钟OEI功率: 一发失效后2.5分钟内达到连续功率",
                "最大连续功率: 持续运行的功率输出",
                "冷却能力: 单发状态下的冷却能力",
                "振动限制: 单发时的振动水平在限制内"
            ],
            "verification_methods": [
                "150小时持久试车: 验证发动机耐久性",
                "30秒OEI试车: 验证30秒功率能力",
                "2.5分钟OEI试车: 验证持续功率能力",
                "振动测试: 验证振动水平",
                "冷却测试: 验证单发冷却能力"
            ],
            "design_parameters": [
                "30秒功率: 通常为最大起飞推力的105%",
                "2.5分钟功率: 通常为最大连续推力",
                "冷却温度限制: 涡滑油、燃气温度限制"
            ],
            "implementation_checklist": [
                "□ 进行发动机性能分析",
                "□ 计算单发性能参数",
                "□ 设计冷却系统",
                "□ 进行150小时持久试车",
                "□ 进行30秒OEI验证",
                "□ 进行2.5分钟OEI验证",
                "✓ 完成OEI符合性验证"
            ]
        },
        "安全分析": {
            "keywords": ["安全", "safety", "分析", "analysis", "失效", "failure", "故障", "fault", "风险", "risk"],
            "design_requirements": [
                "单点失效识别: 识别所有可能导致危险的单一失效",
                "失效影响分析: 评估每次失效的影响",
                "安全措施设计: 设计保护措施防止失效",
                "告警系统: 关键参数超限时告警",
                "安全裕度: 设计足够的安全裕度"
            ],
            "verification_methods": [
                "FMEA分析: 失效模式与影响分析",
                "故障树分析: 定量风险评估",
                "失效试验: 模拟失效场景验证",
                "安全性评估报告: 综合安全性评估"
            ],
            "design_parameters": [
                "失效概率要求: 极不可能的失效概率",
                "安全裕度: 通常10^-9量级",
                "检测时间: 故障检测时间要求"
            ],
            "implementation_checklist": [
                "□ 进行完整FMEA分析",
                "□ 建立故障树模型",
                "□ 识别关键失效模式",
                "□ 设计保护措施",
                "□ 设置告警系统",
                "□ 进行失效试验验证",
                "□ 编写安全性评估报告",
                "✓ 完成安全性符合性验证"
            ]
        },
        "安装": {
            "keywords": ["安装", "installation", "attachment", "mount", "连接", "connection", "接口", "interface"],
            "design_requirements": [
                "接口兼容: 与飞机结构和系统的接口兼容",
                "安装空间: 预留足够的安装和维护空间",
                "可达性: 维护检查的可达性",
                "紧固可靠性: 振动环境下的紧固可靠性",
                "载荷传递: 合理的载荷传递路径"
            ],
            "verification_methods": [
                "安装验证试验: 验证安装正确性",
                "振动试验: 验证振动环境下的紧固可靠性",
                "维护性评估: 评估维护可达性",
                "载荷传递试验: 验证载荷传递"
            ],
            "design_parameters": [
                "紧固扭矩: 按规范要求的扭矩值",
                "安装间隙: 预留热膨胀间隙",
                "维护通道: 最小维护空间要求"
            ],
            "implementation_checklist": [
                "□ 设计安装接口",
                "□ 计算紧固扭矩",
                "□ 预留安装空间",
                "□ 设计维护通道",
                "□ 进行安装验证试验",
                "□ 进行振动试验",
                "□ 评估维护可达性",
                "✓ 完成安装符合性验证"
            ]
        },
        "燃油": {
            "keywords": ["燃油", "fuel", "油箱", "tank", "供油", "fuel", "管理", "management"],
            "design_requirements": [
                "燃油容量: 满足规章规定的燃油容量要求",
                "供油可靠性: 双路供油系统",
                "燃油管理: 自动燃油管理系统",
                "应急燃油: 应急放油系统",
                "燃油指示: 精确的燃油量指示"
            ],
            "verification_methods": [
                "燃油系统试验: 验证供油可靠性",
                "飞行试验: 各种姿态下的供油验证",
                "应急放油试验: 验证应急放油能力",
                "燃油指示校准: 精度验证"
            ],
            "design_parameters": [
                "燃油容量要求: 根据航程和储备要求",
                "供油流量: 满足最大燃油消耗需求",
                "应急放油时间: 15分钟内排放一半"
            ],
            "implementation_checklist": [
                "□ 设计燃油箱容量",
                "□ 设计双路供油系统",
                "□ 安装燃油量传感器",
                "□ 设计燃油管理系统",
                "□ 设计应急放油系统",
                "□ 进行系统试验验证",
                "□ 进行飞行试验验证",
                "✓ 完成燃油系统符合性验证"
            ]
        },
        "控制系统": {
            "keywords": ["控制", "control", "操纵", "操纵面", "控制面", "自动", "auto", "FADEC", "FADEC", "EEC"],
            "design_requirements": [
                "控制冗余: 双通道或三余度控制",
                "故障安全: 单一失效不影响安全",
                "防误操作: 防止飞行员误操作",
                "系统解耦: 相关系统间的解耦设计",
                "模式转换: 平滑的模式转换"
            ],
            "verification_methods": [
                "仿真验证: 控制律仿真验证",
                "故障模拟: 各种失效模式验证",
                "飞行试验: 实际飞行验证",
                "人机工程评估: 飞行员操作评估"
            ],
            "design_parameters": [
                "控制响应时间: 响应时间要求",
                "控制权限限: 控制权限分配",
                "故障转换时间: 备用通道激活时间"
            ],
            "implementation_checklist": [
                "□ 设计控制架构",
                "□ 实现控制律算法",
                "□ 设计故障检测逻辑",
                "□ 设计模式转换逻辑",
                "□ 建立人机界面",
                "□ 进行仿真验证",
                "□ 进行故障模拟试验",
                "✓ 完成控制系统符合性验证"
            ]
        },
        "噪声": {
            "keywords": ["噪声", "noise", "噪音", "声音", "sound", "级", "level", "EPNL", "EPNLdB"],
            "design_requirements": [
                "噪声级限制: 满足CCAR-36噪声级要求",
                "噪声控制: 源头降噪设计",
                "舱内噪声: 乘客舱噪声舒适性",
                "外部噪声: 社区噪声限制"
            ],
            "verification_methods": [
                "噪声测量试验: 按CCAR-36附录测量",
                "飞行剖面验证: 各飞行阶段噪声验证",
                "频谱分析: 噪声频谱分析"
            ],
            "design_parameters": [
                "EPNL限制: 典型限制为XX EPNdB",
                "感觉噪声级: PNdb计算方法"
            ],
            "implementation_checklist": [
                "□ 进行噪声源分析",
                "□ 设计降噪措施",
                "□ 进行地面噪声试验",
                "□ 进行飞行剖面试验",
                "□ 编制噪声符合性报告",
                "✓ 完成噪声符合性验证"
            ]
        }
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("EnhancedDeepInterpretationAgent", knowledge_base_path)
        self.processed_dir = Path(knowledge_base_path)
        self.interpretations = {}
        self.clause_network = defaultdict(list)

    def get_capabilities(self) -> List[str]:
        return [
            "deep_interpret_clauses",
            "extract_design_parameters",
            "build_verification_plans",
            "create_checklists",
            "analyze_clause_dependencies",
            "map_to_design_tasks",
            "export_detailed_interpretations",
            "find_cross_clause_references",
            "build_clause_dependency_graph",
            "extract_compliance_methods",
            "generate_design_review_checklist"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "deep_interpret_clauses":
            return await self._deep_interpret_clauses(task.params)
        elif action == "extract_design_parameters":
            return await self._extract_design_parameters(task.params)
        elif action == "build_verification_plans":
            return await self._build_verification_plans(task.params)
        elif action == "create_checklists":
            return await self._create_checklists(task.params)
        elif action == "analyze_clause_dependencies":
            return await self._analyze_clause_dependencies(task.params)
        elif action == "map_to_design_tasks":
            return await self._map_to_design_tasks(task.params)
        elif action == "export_detailed_interpretations":
            return await self._export_detailed_interpretations(task.params)
        elif action == "find_cross_clause_references":
            return await self.find_cross_clause_references(task.params)
        elif action == "build_clause_dependency_graph":
            return await self.build_clause_dependency_graph(task.params)
        elif action == "extract_compliance_methods":
            return await self.extract_compliance_methods(task.params)
        elif action == "generate_design_review_checklist":
            return await self.generate_design_review_checklist(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    def _classify_clause_deep(self, title: str, content: str) -> Optional[str]:
        """深度分类条款到专业领域"""
        title_lower = title.lower()
        content_lower = content.lower()

        scores = {}
        for domain, knowledge in self.DOMAIN_KNOWLEDGE.items():
            score = 0
            for keyword in knowledge["keywords"]:
                if keyword.lower() in title_lower:
                    score += 10
                if keyword.lower() in content_lower:
                    score += 5
            scores[domain] = score

        # 返回得分最高的领域
        best_domain = max(scores.items(), key=lambda x: x[1]) if scores else None
        if best_domain and best_domain[1] > 0:
            return best_domain[0]
        return None

    async def _deep_interpret_clauses(self, params: Dict) -> Dict:
        """深度解读所有条款"""
        max_clauses = params.get("max_clauses", 200)
        doc_filter = params.get("doc_filter", "")

        interpretations = []

        # 读取所有结构文件
        for json_file in self.processed_dir.glob("*_structure.json"):
            if doc_filter and doc_filter not in str(json_file):
                continue

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", json_file.stem)

                # 深度提取条款
                clauses = self._extract_clauses_detailed(data)

                for clause in clauses:
                    # 深度分类
                    domain = self._classify_clause_deep(clause["title"], clause["full_content"])

                    # 构建深度解读
                    interpretation = {
                        "doc_name": doc_name,
                        "clause_number": clause.get("number", ""),
                        "title": clause["title"],
                        "full_content": clause["full_content"],
                        "domain": domain,
                        "content_analysis": self._analyze_content(clause["full_content"]),
                        "design_implications": self._extract_design_implications(domain, clause),
                        "related_clauses": []
                    }

                    if domain and domain in self.DOMAIN_KNOWLEDGE:
                        interpretation["design_requirements"] = self.DOMAIN_KNOWLEDGE[domain]["design_requirements"]
                        interpretation["verification_methods"] = self.DOMAIN_KNOWLEDGE[domain]["verification_methods"]
                        interpretation["design_parameters"] = self.DOMAIN_KNOWLEDGE[domain].get("design_parameters", [])
                        interpretation["implementation_checklist"] = self.DOMAIN_KNOWLEDGE[domain]["implementation_checklist"]

                    interpretations.append(interpretation)

                    # 构建条款关联网络
                    if domain:
                        self.clause_network[domain].append({
                            "clause": clause["title"],
                            "doc": doc_name,
                            "number": clause.get("number", "")
                        })

            except Exception as e:
                logger.warning(f"Error processing {json_file}: {e}")

        self.interpretations = interpretations

        return {
            "improvements": [f"深度解读 {len(interpretations)} 条条款"],
            "total_interpretations": len(interpretations),
            "by_domain": self._count_by_domain(interpretations),
            "domains_covered": len(set(i.get("domain") for i in interpretations if i.get("domain")))
        }

    def _extract_clauses_detailed(self, data: Dict) -> List[Dict]:
        """深度提取条款，包括完整内容"""
        clauses = []
        seen = set()

        def extract_deep(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")

                # 匹配条款 - 支持多种格式
                # "第33.1条"、"§33.1"、"33.1" 等
                has_clause_pattern = False

                # 检查是否包含条款模式
                if re.search(r'第\s*[\d.]+\s*条', title):
                    has_clause_pattern = True
                elif re.search(r'§\s*[\d.]+', title):
                    has_clause_pattern = True
                elif re.search(r'[\d.]+\.[\d.]+', title):  # 至少有两个点的数字或带点的数字
                    has_clause_pattern = True

                if has_clause_pattern:
                    # 提取条款号
                    number = None
                    match = re.search(r'第\s*([\d.]+)\s*条', title)
                    if match:
                        number = match.group(1)
                    else:
                        match = re.search(r'§\s*([\d.]+)', title)
                        if match:
                            number = match.group(1)
                        else:
                            match = re.search(r'([\d.]+\.[\d.]+)', title)
                            if match:
                                number = match.group(1)

                    if not number:
                        continue

                    # 构建完整内容
                    content_parts = []
                    if node.get("summary"):
                        content_parts.append(node["summary"])
                    if node.get("content_parts"):
                        content_parts.extend(node["content_parts"])

                    # 如果没有详细内容，尝试从子节点获取
                    if not content_parts or len(" ".join(content_parts)) < 50:
                        children = node.get("nodes", []) or node.get("sections", [])
                        for child in children:
                            if isinstance(child, dict):
                                if child.get("summary"):
                                    content_parts.append(child["summary"])

                    full_content = " ".join(content_parts)

                    clause_id = f"{data.get('doc_name', '')}:{number}"
                    if clause_id not in seen and full_content:
                        clauses.append({
                            "number": number,
                            "title": title,
                            "full_content": full_content
                        })
                        seen.add(clause_id)

                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    extract_deep(children)

        structure = data.get("structure", {})
        if isinstance(structure, dict) and "chapters" in structure:
            extract_deep(structure["chapters"])
        elif isinstance(structure, list):
            extract_deep(structure)

        return clauses

    def _analyze_content(self, content: str) -> Dict:
        """分析条款内容，提取关键信息"""
        analysis = {
            "content_length": len(content),
            "has_specific_requirements": False,
            "mentions_percentages": False,
            "mentions_temperatures": False,
            "mentions_time": False,
            "mentions_materials": False,
            "key_sentences": []
        }

        # 检测特定要求
        if any(kw in content for kw in ["必须", "应当", "应该", "不得", "要求"]):
            analysis["has_specific_requirements"] = True
        if re.search(r'\d+%', content):
            analysis["mentions_percentages"] = True
        if re.search(r'\d+°?[CFc]', content):
            analysis["mentions_temperatures"] = True
        if re.search(r'\d+\s*(秒|分钟|小时)', content):
            analysis["mentions_time"] = True
        if any(kw in content for kw in ["材料", "material", "合金", "复合材料"]):
            analysis["mentions_materials"] = True

        # 提取关键句子（包含"必须"、"要求"等的句子）
        sentences = content.split('。')
        for sentence in sentences:
            if any(kw in sentence for kw in ["必须", "应当", "应该", "要求", "不得", "需"]):
                if len(sentence.strip()) > 10:
                    analysis["key_sentences"].append(sentence.strip()[:100])
                    if len(analysis["key_sentences"]) >= 3:
                        break

        return analysis

    def _extract_design_implications(self, domain: Optional[str], clause: Dict) -> List[str]:
        """提取设计影响"""
        implications = []

        content = clause["full_content"]

        # 基于领域和内容提取设计影响
        if domain == "防火":
            if "穿透" in content or "penetration" in content.lower():
                implications.append("需要对所有防火墙穿透件进行防火保护")
            if "阻燃" in content or "flame resistant" in content.lower():
                implications.append("所有材料必须满足阻燃要求")
            if "隔离" in content:
                implications.append("需要设计防火隔离区域")

        elif domain == "结构":
            if "极限" in content or "limit" in content.lower():
                implications.append("结构必须能承受1.5倍限制载荷")
            if "疲劳" in content:
                implications.append("需要进行疲劳寿命分析")
            if "损伤" in content or "damage" in content.lower():
                implications.append("结构应具备损伤容限特性")

        elif domain == "OEI":
            if "30秒" in content or "30-second" in content:
                implications.append("需验证30秒OEI功率能力")
            if "2.5分钟" in content or "2.5-minute" in content:
                implications.append("需验证2.5分钟连续功率能力")

        elif domain == "安全分析":
            implications.append("必须进行FMEA分析")
            implications.append("需要建立故障树模型")
            implications.append("应设计安全裕度")

        return implications

    def _count_by_domain(self, interpretations: List[Dict]) -> Dict[str, int]:
        """统计各领域的解读数量"""
        count = {}
        for item in interpretations:
            domain = item.get("domain", "未分类")
            count[domain] = count.get(domain, 0) + 1
        return count

    async def _export_detailed_interpretations(self, params: Dict) -> Dict:
        """导出详细解读结果"""
        output_path = params.get("output", str(self.processed_dir / "detailed_interpretations.json"))

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "timestamp": str(Path.cwd()),
            "total": len(self.interpretations),
            "by_domain": self._count_by_domain(self.interpretations),
            "clause_network": dict(self.clause_network),
            "interpretations": self.interpretations
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return {
            "improvements": [f"导出 {len(self.interpretations)} 条详细解读到 {output_file}"],
            "output": str(output_file),
            "domains": list(self._count_by_domain(self.interpretations).keys())
        }

    async def _create_checklists(self, params: Dict) -> Dict:
        """创建实施检查清单"""
        checklists_by_domain = defaultdict(list)

        for interpretation in self.interpretations:
            domain = interpretation.get("domain")
            if domain and "implementation_checklist" in interpretation:
                checklists_by_domain[domain].append({
                    "clause": interpretation["title"],
                    "checklist": interpretation["implementation_checklist"]
                })

        return {
            "improvements": [f"创建 {len(checklists_by_domain)} 个领域的检查清单"],
            "checklists": dict(checklists_by_domain)
        }

    async def _build_verification_plans(self, params: Dict) -> Dict:
        """构建验证计划"""
        plans = []

        for interpretation in self.interpretations:
            if interpretation.get("verification_methods"):
                plans.append({
                    "clause": interpretation["title"],
                    "domain": interpretation["domain"],
                    "verification_plan": interpretation["verification_methods"],
                    "related_clauses": []
                })

        return {
            "improvements": [f"构建 {len(plans)} 个验证计划"],
            "total_plans": len(plans),
            "plans": plans[:50]
        }

    async def _analyze_clause_dependencies(self, params: Dict) -> Dict:
        """分析条款依赖关系"""
        dependencies = []

        # 按领域分析条款依赖
        for domain, clauses in self.clause_network.items():
            for i, clause1 in enumerate(clauses):
                for clause2 in clauses[i+1:]:
                    dependencies.append({
                        "domain": domain,
                        "from_clause": clause1["clause"],
                        "to_clause": clause2["clause"],
                        "relationship": "同领域关联"
                    })

        return {
            "improvements": [f"发现 {len(dependencies)} 条条款依赖关系"],
            "total_dependencies": len(dependencies),
            "dependencies": dependencies[:100]
        }

    async def _map_to_design_tasks(self, params: Dict) -> Dict:
        """映射条款到设计任务"""
        design_tasks = []

        # 基于解读生成设计任务
        for interpretation in self.interpretations:
            if interpretation.get("design_requirements"):
                task = {
                    "clause": interpretation["title"],
                    "domain": interpretation["domain"],
                    "tasks": interpretation["design_requirements"],
                    "verification": interpretation.get("verification_methods", []),
                    "priority": "HIGH" if interpretation["domain"] in ["防火", "安全"] else "MEDIUM"
                }
                design_tasks.append(task)

        return {
            "improvements": [f"映射 {len(design_tasks)} 个设计任务"],
            "total_tasks": len(design_tasks),
            "tasks": design_tasks
        }

    async def _extract_design_parameters(self, params: Dict) -> Dict:
        """提取设计参数"""
        parameters = []

        for interpretation in self.interpretations:
            if interpretation.get("design_parameters"):
                parameters.append({
                    "clause": interpretation["title"],
                    "domain": interpretation["domain"],
                    "parameters": interpretation["design_parameters"]
                })

        return {
            "improvements": [f"提取 {len(parameters)} 组设计参数"],
            "total_parameters": len(parameters),
            "parameters": parameters
        }

    async def find_cross_clause_references(self, params: Dict) -> Dict:
        """
        查找跨条款引用 - 发现哪些条款引用了其他条款

        这有助于理解条款之间的依赖关系和引用链
        """
        cross_references = []

        for interpretation in self.interpretations:
            content = interpretation.get("full_content", "")
            title = interpretation.get("title", "")

            # 查找引用其他条款的模式
            refs = []

            # 匹配 "§33.XX" 格式
            section_refs = re.findall(r'§\s*[\d.]+', content)
            for ref in section_refs:
                refs.append({"type": "section", "value": ref})

            # 匹配 "第XX条" 格式
            article_refs = re.findall(r'第\s*[\d.]+\s*条', content)
            for ref in article_refs:
                refs.append({"type": "article", "value": ref})

            # 匹配 "CCAR-XX" 格式
            ccar_refs = re.findall(r'CCAR-[\d-]+', content)
            for ref in ccar_refs:
                refs.append({"type": "document", "value": ref})

            # 匹配 "FAR-XX" 格式
            far_refs = re.findall(r'FAR-[\d.]+', content)
            for ref in far_refs:
                refs.append({"type": "document", "value": ref})

            # 匹配 "AS" / "AMC" / "GM" 格式（EASA）
            easa_refs = re.findall(r'(?:AS|AMC|GM|CS)-[\d.]+', content, re.IGNORECASE)
            for ref in easa_refs:
                refs.append({"type": "easa", "value": ref})

            if refs:
                cross_references.append({
                    "clause": title,
                    "domain": interpretation.get("domain"),
                    "references": refs,
                    "reference_count": len(refs)
                })

        return {
            "improvements": [f"发现 {len(cross_references)} 条包含跨条款引用的条款"],
            "total_cross_refs": len(cross_references),
            "cross_references": cross_references
        }

    async def build_clause_dependency_graph(self, params: Dict) -> Dict:
        """
        构建条款依赖关系图

        分析哪些条款是其他条款的前置条件，形成依赖链
        """
        dependency_graph = {}
        root_clauses = []
        dependent_clauses = []

        for interpretation in self.interpretations:
            clause_id = interpretation.get("clause_number", interpretation.get("title", ""))
            domain = interpretation.get("domain", "unknown")

            # 检查是否包含引用其他条款的内容
            content = interpretation.get("full_content", "")

            # 包含"按...要求"、"根据..."等依赖指示词
            dependency_indicators = [
                "按.*要求", "根据.*规定", "符合.*条款", "满足.*条件",
                "shall.*comply", "must.*meet", "as.*required.*by"
            ]

            has_dependency = False
            dependencies = []

            for pattern in dependency_indicators:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # 提取被引用的内容
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end].strip()
                    dependencies.append(context)
                    has_dependency = True

            node_info = {
                "id": clause_id,
                "title": interpretation.get("title"),
                "domain": domain,
                "dependencies": dependencies
            }

            if has_dependency:
                dependent_clauses.append(node_info)
            else:
                root_clauses.append(node_info)

            dependency_graph[clause_id] = node_info

        return {
            "improvements": [f"构建依赖图: {len(root_clauses)} 个根条款, {len(dependent_clauses)} 个依赖条款"],
            "root_count": len(root_clauses),
            "dependent_count": len(dependent_clauses),
            "dependency_graph": dependency_graph
        }

    async def extract_compliance_methods(self, params: Dict) -> Dict:
        """
        提取符合性方法

        分析条款中建议或要求的验证方法（试验、分析、检查等）
        """
        compliance_methods = []

        method_keywords = {
            "试验": ["试验", "测试", "test", "地面试验", "飞行试验"],
            "分析": ["分析", "计算", "计算分析", "analysis", "计算方法"],
            "检查": ["检查", "inspection", "目视检查", "详细检查"],
            "演示": ["演示", "demonstration", "功能演示"],
            "设备鉴定": ["设备鉴定", "部件认证", "equipment qualification"],
            "服务经验": ["服务经验", "运行经验", "service experience"]
        }

        for interpretation in self.interpretations:
            content = interpretation.get("full_content", "")
            title = interpretation.get("title", "")
            domain = interpretation.get("domain")

            clause_methods = []

            for method_type, keywords in method_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in content.lower():
                        # 提取包含该方法的句子
                        sentences = re.split(r'[。；;]', content)
                        for sentence in sentences:
                            if keyword.lower() in sentence.lower():
                                clause_methods.append({
                                    "method": method_type,
                                    "keyword": keyword,
                                    "context": sentence.strip()[:200]
                                })
                                break  # 每个关键词只取一个匹配

            if clause_methods:
                compliance_methods.append({
                    "clause": title,
                    "domain": domain,
                    "methods": clause_methods
                })

        # 统计方法类型分布
        method_distribution = {}
        for cm in compliance_methods:
            for method in cm["methods"]:
                mt = method["method"]
                method_distribution[mt] = method_distribution.get(mt, 0) + 1

        return {
            "improvements": [f"从 {len(compliance_methods)} 条条款中提取符合性方法"],
            "total_methods": sum(len(cm["methods"]) for cm in compliance_methods),
            "method_distribution": method_distribution,
            "compliance_methods": compliance_methods[:50]  # 限制返回数量
        }

    async def generate_design_review_checklist(self, params: Dict) -> Dict:
        """
        生成设计评审检查清单

        基于所有条款生成系统化的设计评审问题
        """
        review_questions = []

        for interpretation in self.interpretations:
            title = interpretation.get("title", "")
            domain = interpretation.get("domain")
            content = interpretation.get("full_content", "")

            # 基于领域生成特定的评审问题
            if domain == "防火":
                review_questions.extend([
                    {
                        "clause": title,
                        "category": "防火安全",
                        "question": f"设计是否满足 {title} 的防火要求？",
                        "evidence_required": "防火测试报告或材料认证"
                    },
                    {
                        "clause": title,
                        "category": "防火安全",
                        "question": f"所有防火墙穿透件是否按 {title} 进行了保护？",
                        "evidence_required": "穿透件保护设计图纸"
                    }
                ])
            elif domain == "结构":
                review_questions.extend([
                    {
                        "clause": title,
                        "category": "结构强度",
                        "question": f"结构设计是否满足 {title} 的强度要求？",
                        "evidence_required": "应力分析报告"
                    },
                    {
                        "clause": title,
                        "category": "结构强度",
                        "question": f"是否进行了 {title} 要求的疲劳分析？",
                        "evidence_required": "疲劳寿命分析报告"
                    }
                ])
            elif domain == "OEI":
                review_questions.extend([
                    {
                        "clause": title,
                        "category": "性能",
                        "question": f"发动机是否满足 {title} 的OEI功率要求？",
                        "evidence_required": "台架试车数据"
                    }
                ])
            elif domain == "安全分析":
                review_questions.extend([
                    {
                        "clause": title,
                        "category": "安全性",
                        "question": f"是否按 {title} 进行了安全分析？",
                        "evidence_required": "FMEA/FHA报告"
                    }
                ])
            else:
                # 通用问题
                review_questions.append({
                    "clause": title,
                    "category": domain or "通用",
                    "question": f"设计是否符合 {title} 的要求？",
                    "evidence_required": "符合性说明文档"
                })

        # 按类别组织
        by_category = {}
        for q in review_questions:
            cat = q["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(q)

        return {
            "improvements": [f"生成 {len(review_questions)} 个设计评审问题"],
            "total_questions": len(review_questions),
            "categories": list(by_category.keys()),
            "review_checklist": by_category
        }


__all__ = ['EnhancedDeepInterpretationAgent']
