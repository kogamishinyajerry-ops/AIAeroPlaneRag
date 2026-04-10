#!/usr/bin/env python3
"""
民航飞机设计师专家团队知识图谱评测系统
深度评估知识图谱的使用价值、准确性、完整性和可靠性
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib

# 导入知识库
from src.rag.multi_ccar_knowledge_base import MultiCCARKnowledgeBase

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


@dataclass
class ExpertProfile:
    """专家档案"""
    name: str
    title: str
    expertise: List[str]
    responsibilities: List[str]
    years_experience: int
    strictness: str  # "严格", "中等", "宽容"


@dataclass
class TestScenario:
    """测试场景"""
    scenario_id: str
    scenario_name: str
    expert_domain: str
    test_queries: List[str]
    expected_standards: List[str]
    critical_level: str  # "critical", "important", "normal"


@dataclass
class EvaluationResult:
    """评测结果"""
    expert_name: str
    domain: str
    test_queries: List[str]
    accuracy_score: float
    completeness_score: float
    hallucination_score: float  # 0 = 无幻觉, 1 = 严重幻觉
    usability_score: float
    confidence_score: float
    specific_feedback: List[str]
    recommendations: List[str]
    overall_assessment: str


class AviationExpertTeam:
    """民航飞机设计师专家团队"""

    def __init__(self):
        self.knowledge_base = MultiCCARKnowledgeBase('/Users/Zhuanz/AIAeroPlaneRag/data/processed')
        self.experts = self._create_expert_team()
        self.test_scenarios = self._create_test_scenarios()
        self.evaluation_results = []

    def _create_expert_team(self) -> List[ExpertProfile]:
        """创建专家团队"""
        return [
            ExpertProfile(
                name="张建明",
                title="总设计师",
                expertise=["机身总体", "设计要求", "适航标准"],
                responsibilities=["整体设计方案审核", "关键技术决策"],
                years_experience=35,
                strictness="严格"
            ),
            ExpertProfile(
                name="李文静",
                title="防火系统总师",
                expertise=["防火设计", "防火材料", "防火试验"],
                responsibilities=["防火要求符合性", "防火方案评审"],
                years_experience=28,
                strictness="严格"
            ),
            ExpertProfile(
                name="王国庆",
                title="动力装置总师",
                expertise=["发动机设计", "APU系统", "动力安装"],
                responsibilities=["推进系统设计", "发动机适航"],
                years_experience=32,
                strictness="严格"
            ),
            ExpertProfile(
                name="赵明珠",
                title="结构强度总师",
                expertise=["结构强度", "载荷分析", "疲劳寿命"],
                responsibilities=["结构完整性", "强度验证"],
                years_experience=30,
                strictness="严格"
            ),
            ExpertProfile(
                name="刘建国",
                title="系统总师",
                expertise=["空调系统", "排液系统", "液压系统"],
                responsibilities=["系统设计集成", "系统安全"],
                years_experience=25,
                strictness="中等"
            ),
            ExpertProfile(
                name="孙志远",
                title="项目经理",
                expertise=["项目管理", "需求分析", "进度控制"],
                responsibilities=["项目协调", "需求验证"],
                years_experience=20,
                strictness="中等"
            ),
        ]

    def _create_test_scenarios(self) -> List[TestScenario]:
        """创建专业测试场景"""
        return [
            # 防火系统测试
            TestScenario(
                scenario_id="FIRE_001",
                scenario_name="发动机防火墙穿透性要求",
                expert_domain="防火系统",
                test_queries=[
                    "发动机防火墙的穿透性要求是什么？",
                    "涡轮发动机防火材料的耐久性要求",
                    "发动机舱的防火隔离要求",
                    "APU防火设计的具体标准"
                ],
                expected_standards=[
                    "CCAR-33.17条 防火要求",
                    "CCAR-25.1183条 防火墙穿透性",
                    "具体的材料和试验要求"
                ],
                critical_level="critical"
            ),
            # 发动机测试
            TestScenario(
                scenario_id="ENGINE_001",
                scenario_name="发动机安全分析和试验要求",
                expert_domain="动力装置",
                test_queries=[
                    "第33.75条安全分析的具体内容和要求",
                    "发动机台架试验的程序和标准",
                    "涡轮发动机30秒OEI测试要求",
                    "发动机持续适航文件的编制要求"
                ],
                expected_standards=[
                    "CCAR-33.75条安全分析",
                    "CCAR-33.81条台架试验",
                    "具体的试验和文件要求"
                ],
                critical_level="critical"
            ),
            # 结构强度测试
            TestScenario(
                scenario_id="STRUCTURE_001",
                scenario_name="运输类飞机结构强度要求",
                expert_domain="结构强度",
                test_queries=[
                    "CCAR-25对机身结构强度的基本要求",
                    "飞行载荷的计算方法和标准",
                    "疲劳和损伤容限评估要求",
                    "材料强度和验证试验要求"
                ],
                expected_standards=[
                    "CCAR-25.301条载荷",
                    "CCAR-25.571条结构强度",
                    "具体的强度和试验标准"
                ],
                critical_level="critical"
            ),
            # 系统设计测试
            TestScenario(
                scenario_id="SYSTEM_001",
                scenario_name="飞机系统设计综合要求",
                expert_domain="系统设计",
                test_queries=[
                    "空调系统的设计和安装要求",
                    "排液系统的设计和排放标准",
                    "液压系统的安全性和可靠性要求",
                    "多个系统集成的协调性要求"
                ],
                expected_standards=[
                    "CCAR-25相关系统要求",
                    "系统集成和安全标准",
                    "具体的系统设计要求"
                ],
                critical_level="important"
            ),
            # 机身总体测试
            TestScenario(
                scenario_id="OVERALL_001",
                scenario_name="机身总体设计和适航符合性",
                expert_domain="机身总体",
                test_queries=[
                    "运输类飞机的总体性能要求概述",
                    "不同类型航空器的适航标准对比",
                    "设计保证和质量体系要求",
                    "持续适航管理要求"
                ],
                expected_standards=[
                    "CCAR-25总体要求",
                    "设计保证系统",
                    "质量体系要求"
                ],
                critical_level="important"
            ),
        ]

    def simulate_expert_evaluation(self) -> Dict[str, Any]:
        """模拟专家团队评测"""
        print("="*80)
        print("🛩️  民航飞机设计师专家团队 - 知识图谱深度评测")
        print("="*80)
        print(f"评测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"参评专家: {len(self.experts)}位")
        print(f"测试场景: {len(self.test_scenarios)}个")
        print("="*80)

        # 显示专家团队
        self._display_expert_team()

        # 进行评测
        all_results = []
        for scenario in self.test_scenarios:
            print(f"\n{'='*80}")
            print(f"📋 场景测试: {scenario.scenario_name}")
            print(f"👤 专家领域: {scenario.expert_domain}")
            print(f"⚠️  关键级别: {scenario.critical_level}")
            print("="*80)

            # 找到对应专家
            expert = self._find_expert_for_domain(scenario.expert_domain)

            if expert:
                print(f"🧪 主审专家: {expert.name} ({expert.title})")
                print(f"📊 专业经验: {expert.years_experience}年")
                print(f"🎯 严格程度: {expert.strictness}")

                # 执行测试
                result = self._evaluate_scenario(scenario, expert)
                all_results.append(result)

                # 显示结果
                self._display_evaluation_result(result)

        # 生成综合报告
        return self._generate_comprehensive_report(all_results)

    def _display_expert_team(self):
        """显示专家团队"""
        print("\n👥 专家团队成员:")
        print("-" * 80)
        for i, expert in enumerate(self.experts, 1):
            print(f"{i}. {expert.name} - {expert.title}")
            print(f"   专业领域: {', '.join(expert.expertise)}")
            print(f"   工作经验: {expert.years_experience}年")
            print(f"   评审风格: {expert.strictness}")

    def _find_expert_for_domain(self, domain: str) -> Optional[ExpertProfile]:
        """根据领域查找对应专家"""
        domain_mapping = {
            "防火系统": "防火",
            "动力装置": "动力",
            "结构强度": "结构",
            "系统设计": "系统",
            "机身总体": "总体",
            "项目管理": "项目"
        }

        for expert in self.experts:
            for expertise in expert.expertise:
                if domain in expertise or any(keyword in expertise for keyword in
                      ["防火", "发动机", "结构", "系统", "总体", "项目"]):
                    return expert
        return self.experts[0]  # 默认返回总设计师

    def _evaluate_scenario(self, scenario: TestScenario, expert: ExpertProfile) -> EvaluationResult:
        """评测单个场景"""
        print(f"\n🔍 执行查询测试:")
        print("-" * 60)

        all_results = []
        hallucination_checks = []
        missing_info_checks = []

        for i, query in enumerate(scenario.test_queries, 1):
            print(f"\n查询 {i}: {query}")

            # 执行知识图谱查询
            kb_results = self.knowledge_base.search(query, top_k=3)

            if kb_results:
                print(f"  ✅ 找到 {len(kb_results)} 个结果")

                for j, result in enumerate(kb_results, 1):
                    metadata = result['metadata']
                    source = metadata['source']
                    title = metadata['title']
                    score = metadata['score']

                    print(f"    [{j}] {source}: {title[:60]}...")
                    print(f"        得分: {score:.1f} | 页码: {metadata['page']}")

                    # 检查准确性
                    accuracy = self._check_accuracy(result, scenario.expected_standards)
                    print(f"        准确性: {accuracy['status']}")

                    if accuracy['issues']:
                        hallucination_checks.extend(accuracy['issues'])

                    all_results.append({
                        'query': query,
                        'results': kb_results,
                        'accuracy': accuracy
                    })
            else:
                print(f"  ❌ 未找到结果")
                missing_info_checks.append(query)

        # 计算各项得分
        accuracy_score = self._calculate_accuracy_score(all_results, scenario)
        completeness_score = self._calculate_completeness_score(all_results, scenario)
        hallucination_score = self._calculate_hallucination_score(hallucination_checks)
        usability_score = self._calculate_usability_score(all_results)
        confidence_score = self._calculate_confidence_score(all_results)

        # 专家反馈
        feedback = self._generate_expert_feedback(expert, scenario, all_results,
                                                accuracy_score, completeness_score)
        recommendations = self._generate_recommendations(feedback)

        return EvaluationResult(
            expert_name=expert.name,
            domain=scenario.expert_domain,
            test_queries=scenario.test_queries,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            hallucination_score=hallucination_score,
            usability_score=usability_score,
            confidence_score=confidence_score,
            specific_feedback=feedback,
            recommendations=recommendations,
            overall_assessment=self._calculate_overall_assessment(accuracy_score, completeness_score,
                                                               hallucination_score, usability_score)
        )

    def _check_accuracy(self, result: Dict, expected_standards: List[str]) -> Dict:
        """检查结果准确性"""
        issues = []
        status = "✅ 准确"

        title = result['metadata']['title']
        source = result['metadata']['source']

        # 检查是否来自正确的规章
        for standard in expected_standards:
            if "CCAR-33" in standard and "CCAR-33" in source:
                status = "✅ 准确"
            elif "CCAR-25" in standard and "CCAR-25" in source:
                status = "✅ 准确"
            elif "CCAR-29" in standard and "CCAR-29" in source:
                status = "✅ 准确"

        # 检查标题是否相关
        text = result.get('text', '')
        if text and len(text) < 20:
            issues.append("结果内容过少，可能不完整")
            status = "⚠️  内容不足"

        # 检查是否是幻觉（完全不相关）
        if not any(keyword in title.lower() for keyword in ['要求', '设计', '标准', '规定', '条']):
            if not any(keyword in text for keyword in ['要求', '设计', '标准', '规定']):
                issues.append("结果内容可能与查询不相关")
                status = "❌ 可能幻觉"

        return {
            'status': status,
            'issues': issues
        }

    def _calculate_accuracy_score(self, results: List[Dict], scenario: TestScenario) -> float:
        """计算准确性得分"""
        if not results:
            return 0.0

        accurate_count = 0
        total_count = len(results)

        for result in results:
            accuracy = result['accuracy']
            if '✅' in accuracy['status']:
                accurate_count += 1
            elif '⚠️' in accuracy['status']:
                accurate_count += 0.5

        return (accurate_count / total_count) * 100 if total_count > 0 else 0

    def _calculate_completeness_score(self, results: List[Dict], scenario: TestScenario) -> float:
        """
        计算完整性得分 (0-100)

        综合考虑:
        1. 查询覆盖率 - 是否所有查询都有结果
        2. 结果数量 - 每个查询是否有足够的结果
        3. 相关性 - 结果的平均相关性
        """
        # 1. 查询覆盖率 (40%)
        queries_with_results = len([r for r in results if r.get('results')])
        query_coverage = (queries_with_results / len(scenario.test_queries)) * 40 if scenario.test_queries else 0

        # 2. 结果数量充足性 (30%)
        # 期望每个查询至少有3个结果
        total_results = sum(len(r.get('results', [])) for r in results)
        expected_results = len(scenario.test_queries) * 3
        result_adequacy = min((total_results / expected_results) * 30, 30) if expected_results > 0 else 0

        # 3. 结果质量 - 基于平均得分 (30%)
        avg_score = 0
        score_count = 0
        for result in results:
            for res in result.get('results', []):
                metadata = res.get('metadata', {})
                score = metadata.get('score', 0)
                # 将检索得分(0-100)转换为质量得分
                # 得分20以上就算是合格的
                quality = min((score / 20) * 30, 30)
                avg_score += quality
                score_count += 1

        quality_score = (avg_score / score_count) if score_count > 0 else 0

        # 总分 (最高100)
        total = min(query_coverage + result_adequacy + quality_score, 100)
        return round(total, 1)

    def _calculate_hallucination_score(self, issues: List[str]) -> float:
        """计算幻觉得分（0=无幻觉，1=严重幻觉）"""
        if not issues:
            return 0.0

        # 检查幻觉严重程度
        severe_issues = [i for i in issues if '幻觉' in i or '不相关' in i]
        if severe_issues:
            return 0.8
        else:
            return 0.3

    def _calculate_usability_score(self, results: List[Dict]) -> float:
        """
        计算可用性得分 (0-100)

        评估知识图谱在实际使用中的便利程度:
        1. 结果展示清晰度
        2. 引用完整性
        3. 信息可追溯性
        4. 交互体验
        """
        if not results:
            return 0.0

        usability_factors = {
            "result_clarity": 0,      # 结果清晰度 (30%)
            "citation_quality": 0,     # 引用质量 (30%)
            "traceability": 0,         # 可追溯性 (20%)
            "response_relevance": 0    # 响应相关性 (20%)
        }

        total_results = 0

        for result in results:
            for res in result.get('results', []):
                total_results += 1
                metadata = res.get('metadata', {})

                # 1. 结果清晰度 - 检查是否有完整的章节信息
                if metadata.get('section') and metadata.get('chapter'):
                    usability_factors["result_clarity"] += 30

                # 2. 引用质量 - 检查是否有文档路径和页码
                if metadata.get('source_path') or metadata.get('page'):
                    usability_factors["citation_quality"] += 30

                # 3. 可追溯性 - 检查是否有文档ID和版本
                if metadata.get('document_id') and metadata.get('document_version'):
                    usability_factors["traceability"] += 20

                # 4. 响应相关性 - 基于检索得分
                score = metadata.get('score', 0)
                # 得分 >= 20 认为是相关的
                if score >= 20:
                    usability_factors["response_relevance"] += 20

        # 归一化得分
        if total_results > 0:
            for factor in usability_factors:
                usability_factors[factor] = (usability_factors[factor] / total_results)

        # 总分 (最高100)
        total = sum(usability_factors.values())
        return round(min(total, 100), 1)

    def _calculate_confidence_score(self, results: List[Dict]) -> float:
        """
        计算可信度得分 (0-100)

        综合评估结果的可信程度:
        1. 查询成功率 - 有结果的比例
        2. 结果详细程度 - 内容长度
        3. 结果相关性 - 平均检索得分
        """
        if not results:
            return 0.0

        # 1. 查询成功率 (40%)
        queries_with_results = len([r for r in results if r.get('results')])
        query_success_rate = (queries_with_results / len(results)) * 40

        # 2. 结果详细程度 (30%)
        total_results = sum(len(r.get('results', [])) for r in results)
        detailed_results = 0
        for result in results:
            for res in result.get('results', []):
                text = res.get('text', '')
                # 内容长度超过100字认为是详细的
                if len(text) > 100:
                    detailed_results += 1

        detail_score = (detailed_results / total_results * 30) if total_results > 0 else 0

        # 3. 结果相关性 - 基于检索得分 (30%)
        total_score = 0
        score_count = 0
        for result in results:
            for res in result.get('results', []):
                metadata = res.get('metadata', {})
                score = metadata.get('score', 0)
                # 将检索得分(0-100)转换为相关性(0-30)
                relevance = min(score * 0.3, 30)
                total_score += relevance
                score_count += 1

        relevance_score = (total_score / score_count) if score_count > 0 else 0

        # 总分 (最高100)
        total = query_success_rate + detail_score + relevance_score
        return round(min(total, 100), 1)

    def _generate_expert_feedback(self, expert: ExpertProfile, scenario: TestScenario,
                                 all_results: List[Dict], accuracy: float,
                                 completeness: float) -> List[str]:
        """生成专家反馈"""
        feedback = []

        # 基于专家严格程度的反馈
        if expert.strictness == "严格":
            if accuracy < 70:
                feedback.append(f"准确性不足{100-accuracy:.0f}%，需要改进")
            if completeness < 60:
                feedback.append(f"完整性不足，缺少关键信息")
        elif expert.strictness == "中等":
            if accuracy < 50:
                feedback.append(f"准确性需要提升")
            if completeness < 40:
                feedback.append(f"信息覆盖不完整")

        # 专业反馈
        if "防火" in scenario.expert_domain:
            feedback.append("防火要求的查询需要更精确的条款匹配")
        elif "发动机" in scenario.expert_domain:
            feedback.append("发动机相关查询结果较好，但需要更多技术细节")
        elif "结构" in scenario.expert_domain:
            feedback.append("结构强度查询需要覆盖更多载荷情况")

        return feedback

    def _generate_recommendations(self, feedback: List[str]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        if any("准确性" in f for f in feedback):
            recommendations.append("建议增强关键词匹配算法")

        if any("完整性" in f for f in feedback):
            recommendations.append("建议扩充知识库覆盖范围")

        if any("精确" in f for f in feedback):
            recommendations.append("建议引入更智能的语义理解")

        if any("技术细节" in f for f in feedback):
            recommendations.append("建议增加条款内容的深度解析")

        return recommendations

    def _calculate_overall_assessment(self, accuracy: float, completeness: float,
                                   hallucination: float, usability: float) -> str:
        """计算总体评估"""
        avg_score = (accuracy + completeness + (100 - hallucination * 100) + usability) / 4

        if avg_score >= 80:
            return "优秀 - 可以作为主要参考工具"
        elif avg_score >= 70:
            return "良好 - 可以作为辅助参考工具"
        elif avg_score >= 60:
            return "中等 - 需要人工复核"
        else:
            return "较差 - 不建议用于实际应用"

    def _display_evaluation_result(self, result: EvaluationResult):
        """显示评测结果"""
        print(f"\n📊 专家评估结果:")
        print("-" * 60)
        print(f"准确性得分: {result.accuracy_score:.1f}/100")
        print(f"完整性得分: {result.completeness_score:.1f}/100")
        print(f"幻觉风险: {result.hallucination_score:.2f} (0=低风险, 1=高风险)")
        print(f"可用性得分: {result.usability_score:.1f}/100")
        print(f"可信度得分: {result.confidence_score:.1f}/100")
        print(f"\n总体评估: {result.overall_assessment}")

        if result.specific_feedback:
            print(f"\n💬 专家反馈:")
            for feedback in result.specific_feedback:
                print(f"  • {feedback}")

        if result.recommendations:
            print(f"\n💡 改进建议:")
            for rec in result.recommendations:
                print(f"  • {rec}")

    def _generate_comprehensive_report(self, results: List[EvaluationResult]) -> Dict:
        """生成综合报告"""
        total_accuracy = sum(r.accuracy_score for r in results) / len(results)
        total_completeness = sum(r.completeness_score for r in results) / len(results)
        total_hallucination = sum(r.hallucination_score for r in results) / len(results)
        total_usability = sum(r.usability_score for r in results) / len(results)

        critical_issues = []
        for result in results:
            if result.hallucination_score > 0.5:
                critical_issues.append(f"{result.domain}存在幻觉风险")
            if result.accuracy_score < 50:
                critical_issues.append(f"{result.domain}准确性不足")

        return {
            'overall_accuracy': total_accuracy,
            'overall_completeness': total_completeness,
            'overall_hallucination': total_hallucination,
            'overall_usability': total_usability,
            'critical_issues': critical_issues,
            'recommendations': [
                "建议优先解决幻觉风险问题",
                "扩充专业领域知识覆盖",
                "提升查询结果的相关性",
                "增强跨文档关联能力"
            ],
            'evaluation_date': datetime.now().isoformat(),
            'evaluator_count': len(self.experts),
            'scenario_count': len(self.test_scenarios)
        }


def main():
    """主程序"""
    team = AviationExpertTeam()
    report = team.simulate_expert_evaluation()

    print(f"\n{'='*80}")
    print(f"📋 专家团队综合评测报告")
    print("="*80)
    print(f"\n总体评分:")
    print(f"  准确性: {report['overall_accuracy']:.1f}/100")
    print(f"  完整性: {report['overall_completeness']:.1f}/100")
    print(f"  幻觉风险: {report['overall_hallucination']:.2f} (0=低风险, 1=高风险)")
    print(f"  可用性: {report['overall_usability']:.1f}/100")

    if report['critical_issues']:
        print(f"\n⚠️  关键问题:")
        for issue in report['critical_issues']:
            print(f"  • {issue}")

    print(f"\n💡 综合建议:")
    for rec in report['recommendations']:
        print(f"  • {rec}")

    print(f"\n🎯 最终结论:")
    avg_score = (report['overall_accuracy'] + report['overall_completeness'] +
                 (100 - report['overall_hallucination'] * 100) + report['overall_usability']) / 4

    if avg_score >= 70:
        print("  ✅ 知识图谱系统通过了专家团队评测")
        print(f"  📊 综合得分: {avg_score:.1f}/100 - 可以作为专业工具使用")
    else:
        print("  ⚠️  知识图谱系统需要进一步改进")
        print(f"  📊 综合得分: {avg_score:.1f}/100 - 建议优化后使用")


if __name__ == '__main__':
    main()
