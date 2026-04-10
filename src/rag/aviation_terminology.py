"""
民航专业术语词典
用于优化专业术语理解和同义词扩展
"""

# 防火专业术语
FIRE_PROTECTION_TERMS = {
    "防火": ["防火墙", "防火隔离", "阻燃", "耐火", "防火材料"],
    "防火墙": [" Firewall", "防火隔断", "firewall", "阻火墙"],
    "穿透性": ["penetration", "穿透", "开口", "通过"],
    "阻燃": ["flame resistant", "耐火", "抗燃"],
    "耐火": ["fire resistant", "耐高温", "防火"],
    "防火材料": ["防火材料", "阻燃材料", "耐火材料"],
    "APU防火": ["辅助动力装置防火", "APU fire protection", "辅助动力防火"],
}

# 动力装置术语
PROPULSION_TERMS = {
    "发动机": ["Engine", "动力装置", "发动机", "引擎", "动力系统"],
    "安全分析": ["Safety analysis", "安全性评估", "风险评估", "safety assessment"],
    "台架试验": ["bench test", "地面试验", "台架测试", "试车"],
    "OEI": ["One Engine Inoperative", "单发失效", "一发失效", "单发停车", "发动机不工作"],
    "单发失效": ["OEI", "One Engine Inoperative", "一发不工作", "发动机失效"],
    "持续适航": ["Continuing Airworthiness", "持续适航", "适航性保持"],
    "30秒OEI": ["30-second OEI", "30秒一发不工作", "30秒单发", "30秒一台发动机不工作"],
    "2.5分钟OEI": ["2.5-minute OEI", "2.5分钟一发不工作"],
    "最大连续": ["Maximum Continuous", "MCP", "最大推力"],
    "起飞": ["Takeoff", "起飞", "起飞推力"],
    "静推力": ["Static thrust", "静态推力"],
    "涡轮发动机": ["Turbine engine", "燃气涡轮", "涡喷", "涡扇", "turbine"],
}

# 结构强度术语
STRUCTURES_TERMS = {
    "结构强度": ["Structural strength", "结构完整性", "强度要求"],
    "载荷": ["Load", "负载", "受力", "负荷"],
    "飞行载荷": ["Flight load", "空中载荷", "气动载荷"],
    "地面载荷": ["Ground load", "地面载荷", "着陆载荷"],
    "疲劳": ["Fatigue", "疲劳寿命", "疲劳强度"],
    "损伤容限": ["Damage tolerance", "损伤容限", "破损安全"],
    "极限载荷": ["Limit load", "使用载荷", "极限载荷"],
    "安全系数": ["Safety factor", "安全裕度", "设计系数"],
    "材料强度": ["Material strength", "材料性能", "材料特性"],
    "验证试验": ["Verification test", "验证试验", "强度试验"],
}

# 系统设计术语
SYSTEMS_TERMS = {
    "空调": ["Air conditioning", "环境控制", "ECS", "环控", "空调系统", "环控系统"],
    "排液": ["Drainage", "排放", "液体排放", "排液系统", "排放系统"],
    "液压": ["Hydraulic", "液压系统", "液压驱动", "液体压力"],
    "系统集成": ["System integration", "综合系统", "系统协调", "系统综合"],
    "可靠性": ["Reliability", "可靠度", "可靠性设计", "系统可靠"],
    "安全性": ["Safety", "安全设计", "故障安全", "fail-safe"],
    "燃油系统": ["Fuel system", "油箱", "供油", "燃油管理", "fuel"],
    "防撞性": ["Crashworthiness", "防撞", "撞击保护", "crash resistance"],
    "操纵系统": ["Control system", "操纵", "飞行控制", "control"],
}

# 适航管理术语
AIRWORTHINESS_TERMS = {
    "适航": ["Airworthiness", "适航性", "适航标准"],
    "符合性": ["Compliance", "符合", "合规", "符合性验证"],
    "设计保证": ["Design assurance", "设计质量", "设计保证体系"],
    "持续适航": ["Continuing airworthiness", "适航保持", "持续适航管理"],
    "适航文件": ["Airworthiness document", "适航资料", "手册"],
    "审定": ["Certification", "型号合格", "适航审定"],
    "设计要求": ["Design requirements", "设计标准", "设计规范"],
}

# CCAR 部号别名
CCAR_ALIASES = {
    "CCAR-25": ["运输类飞机", "25部", "CCAR25", "大飞机"],
    "CCAR-29": ["运输类旋翼航空器", "29部", "CCAR29", "直升机"],
    "CCAR-33": ["航空发动机", "33部", "CCAR33", "发动机"],
    "CCAR-23": ["正常类飞机", "23部", "CCAR23", "小飞机"],
    "CCAR-27": ["正常类旋翼航空器", "27部", "CCAR27"],
    "CCAR-36": ["航空器噪声", "36部", "CCAR36", "噪声"],
    "CCAR-91": ["运行规范", "91部", "CCAR91", "运行"],
    "CCAR-93TM": ["民航目视飞行", "93TM", "航图"],
}

# FAA 规章别名
FAA_ALIASES = {
    "FAR-25": ["14 CFR 25", "FAR25", "Transport Category Airplanes", "运输类飞机"],
    "FAR-33": ["14 CFR 33", "FAR33", "Aircraft Engines", "航空发动机"],
    "FAR-29": ["14 CFR 29", "FAR29", "Transport Category Rotorcraft", "运输类旋翼机"],
    "FAR-23": ["14 CFR 23", "FAR23", "Normal Category Airplanes", "正常类飞机"],
    "FAR-27": ["14 CFR 27", "FAR27", "Normal Category Rotorcraft", "正常类旋翼机"],
    "§": ["Section", "section", "条款", "条"],
}

# EASA 规章别名
EASA_ALIASES = {
    "CS-25": ["Certification Specifications 25", "CS25", "Large Aeroplanes", "大型飞机"],
    "CS-E": ["Certification Specifications E", "CSE", "Engines", "发动机"],
    "CS-23": ["Certification Specifications 23", "CS23", "Normal Category Aeroplanes"],
    "CS-27": ["Certification Specifications 27", "CS27", "Normal Category Rotorcraft"],
    "CS-29": ["Certification Specifications 29", "CS29", "Large Rotorcraft"],
    "AMC": ["Acceptable Means of Compliance", "可接受的符合性方法", "符合性说明"],
    "ETOPS": ["Extended Range Twin Operations", "延伸航程运行", "双发延伸航程"],
}

# 跨机构对应术语
CROSS_AGENCY_TERMS = {
    "运输类飞机": ["CCAR-25", "FAR-25", "CS-25", "Transport Category", "Large Aeroplanes"],
    "发动机": ["CCAR-33", "FAR-33", "CS-E", "Engine", "Aircraft Engines"],
    "正常类飞机": ["CCAR-23", "FAR-23", "CS-23", "Normal Category"],
    "运输类旋翼机": ["CCAR-29", "FAR-29", "CS-29", "Transport Category Rotorcraft"],
    "旋翼机": ["Rotorcraft", "直升机", "Helicopter"],
    "涡轮发动机": ["Turbine engine", "燃气涡轮", "涡喷", "涡扇", "Turboprop"],
    "活塞发动机": ["Piston engine", "Reciprocating engine", "活塞式"],
    "适航标准": ["Airworthiness Standards", "Certification Specifications", "适航规范"],
    "符合性": ["Compliance", "符合", "合规", "Show compliance"],
    "审定": ["Certification", "型号合格", "Type Certification", "适航审定"],
}

# 合并所有术语
ALL_TERMINOLOGY = {
    **FIRE_PROTECTION_TERMS,
    **PROPULSION_TERMS,
    **STRUCTURES_TERMS,
    **SYSTEMS_TERMS,
    **AIRWORTHINESS_TERMS,
    **CCAR_ALIASES,
    **FAA_ALIASES,
    **EASA_ALIASES,
    **CROSS_AGENCY_TERMS,
}

# 反向映射（从同义词到标准词）
REVERSE_TERMINOLOGY = {}
for standard_term, synonyms in ALL_TERMINOLOGY.items():
    for synonym in synonyms:
        REVERSE_TERMINOLOGY[synonym.lower()] = standard_term

# 添加标准词自身的映射
for term in ALL_TERMINOLOGY.keys():
    REVERSE_TERMINOLOGY[term.lower()] = term


class AviationTerminology:
    """民航专业术语处理器"""

    @staticmethod
    def normalize_term(term: str) -> str:
        """将同义词标准化"""
        term_lower = term.lower().strip()
        return REVERSE_TERMINOLOGY.get(term_lower, term)

    @staticmethod
    def expand_synonyms(query: str) -> list:
        """扩展查询同义词"""
        expanded_terms = [query]
        query_lower = query.lower()

        # 检查是否包含已知术语
        for standard_term, synonyms in ALL_TERMINOLOGY.items():
            if standard_term.lower() in query_lower:
                expanded_terms.extend(synonyms)
            # 检查同义词
            for synonym in synonyms:
                if synonym.lower() in query_lower and standard_term not in expanded_terms:
                    expanded_terms.append(standard_term)

        return list(set(expanded_terms))

    @staticmethod
    def extract_professional_terms(query: str) -> dict:
        """提取专业术语并分类"""
        terms_found = {
            "fire_protection": [],
            "propulsion": [],
            "structures": [],
            "systems": [],
            "airworthiness": [],
            "ccar_refs": [],
            "faa_refs": [],
            "easa_refs": [],
        }

        query_lower = query.lower()

        # 检查各类术语
        for term, synonyms in FIRE_PROTECTION_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["fire_protection"].append(term)

        for term, synonyms in PROPULSION_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["propulsion"].append(term)

        for term, synonyms in STRUCTURES_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["structures"].append(term)

        for term, synonyms in SYSTEMS_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["systems"].append(term)

        for term, synonyms in AIRWORTHINESS_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["airworthiness"].append(term)

        for term, synonyms in CCAR_ALIASES.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["ccar_refs"].append(term)

        for term, synonyms in FAA_ALIASES.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["faa_refs"].append(term)

        for term, synonyms in EASA_ALIASES.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["easa_refs"].append(term)

        for term, synonyms in CROSS_AGENCY_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                # Add to appropriate category
                if "engine" in term.lower():
                    if term not in terms_found["propulsion"]:
                        terms_found["propulsion"].append(term)
                elif "fire" in term.lower():
                    if term not in terms_found["fire_protection"]:
                        terms_found["fire_protection"].append(term)

        return terms_found

    @staticmethod
    def get_related_terms(term: str) -> list:
        """获取相关术语（用于扩展查询）"""
        related = []
        term_lower = term.lower()

        # 直接匹配
        if term_lower in REVERSE_TERMINOLOGY:
            standard = REVERSE_TERMINOLOGY[term_lower]
            if standard in ALL_TERMINOLOGY:
                related.extend(ALL_TERMINOLOGY[standard])

        # 部分匹配
        for standard, synonyms in ALL_TERMINOLOGY.items():
            if term_lower in standard.lower() or standard.lower() in term_lower:
                related.append(standard)
                related.extend(synonyms)
            for syn in synonyms:
                if term_lower in syn.lower() or syn.lower() in term_lower:
                    related.append(standard)
                    related.extend(synonyms)

        return list(set(related))


# 导出便捷函数
def expand_query_with_synonyms(query: str) -> list:
    """使用同义词扩展查询"""
    return AviationTerminology.expand_synonyms(query)


def normalize_professional_query(query: str) -> str:
    """标准化专业查询"""
    # 提取术语分类
    terms = AviationTerminology.extract_professional_terms(query)

    # 替换同义词为标准术语
    normalized = query
    for category, term_list in terms.items():
        for term in term_list:
            if term in CCAR_ALIASES:
                continue  # 跳过 CCAR 引用
            # 将同义词替换为标准术语
            standard = AviationTerminology.normalize_term(term)
            if standard != term:
                normalized = normalized.replace(term, standard)

    return normalized


if __name__ == "__main__":
    # 测试
    test_queries = [
        "发动机的防火墙穿透性要求",
        "单发失效时的30秒OEI测试",
        "机身结构强度和载荷分析",
        "空调系统的设计和安装",
        "CCAR-25 部的适航符合性",
    ]

    print("="*60)
    print("民航专业术语处理测试")
    print("="*60)

    for query in test_queries:
        print(f"\n原始查询: {query}")
        print(f"标准化: {normalize_professional_query(query)}")

        terms = AviationTerminology.extract_professional_terms(query)
        for category, term_list in terms.items():
            if term_list:
                print(f"  {category}: {', '.join(term_list)}")

        expanded = expand_query_with_synonyms(query)
        print(f"扩展查询: {expanded[:5]}")  # 只显示前5个
