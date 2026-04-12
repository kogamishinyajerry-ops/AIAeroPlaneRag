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

# 涡轮冷却系统术语 (T4.1 新增)
TURBINE_COOLING_TERMS = {
    "气膜冷却": ["film cooling", "冷却气膜", "薄膜冷却", "film coolant"],
    "冲击冷却": ["impingement cooling", "射流冷却", "冲击射流"],
    "对流冷却": ["convection cooling", "内部冷却", "convective cooling"],
    "发散冷却": ["transpiration cooling", "多孔冷却", "渗透冷却"],
    "涡轮叶片冷却": ["turbine blade cooling", "冷却叶片", "blade cooling"],
    "冷却空气": ["cooling air", "冷却气流", "冷却空气量", "cooling airflow"],
    "热障涂层": ["thermal barrier coating", "TBC", "隔热涂层", "ceramic coating"],
    "涡轮进口温度": ["Turbine Entry Temperature", "TET", "涡轮前温度", "T4"],
    "最高允许温度": ["maximum allowable temperature", "温度限值", "thermal limit"],
    "冷却效率": ["cooling effectiveness", "冷却效果", "η_c"],
    "热通量": ["heat flux", "热流密度", "热负荷"],
    "高压涡轮": ["high pressure turbine", "HPT", "高压涡轮级"],
    "低压涡轮": ["low pressure turbine", "LPT", "低压涡轮级"],
    "导向叶片": ["nozzle guide vane", "NGV", "静子叶片", "stator vane"],
    "转子叶片": ["rotor blade", "工作叶片", "动叶"],
    "叶冠": ["blade tip", "叶片顶部", "tip clearance"],
    "间隙控制": ["clearance control", "间隙管理", "tip clearance control"],
    "涡轮盘": ["turbine disc", "涡轮轮盘", "turbine disk"],
    "内部流道": ["internal cooling passage", "冷却通道", "cooling channel"],
    "蒸发效果": ["evaporative cooling", "蒸发冷却"],
}

# 材料缺陷与失效术语 (T4.1 新增)
MATERIAL_DEFECT_TERMS = {
    "蠕变": ["creep", "高温蠕变", "蠕变变形", "蠕变寿命"],
    "热疲劳": ["thermal fatigue", "热机疲劳", "温度循环疲劳"],
    "低循环疲劳": ["low cycle fatigue", "LCF", "低周疲劳"],
    "高循环疲劳": ["high cycle fatigue", "HCF", "高频疲劳", "高周疲劳"],
    "氧化": ["oxidation", "高温氧化", "抗氧化", "oxidation resistance"],
    "热腐蚀": ["hot corrosion", "硫化腐蚀", "type I hot corrosion", "type II hot corrosion"],
    "腐蚀疲劳": ["corrosion fatigue", "腐蚀裂纹扩展"],
    "裂纹扩展": ["crack propagation", "疲劳裂纹扩展", "crack growth", "da/dN"],
    "应力腐蚀": ["stress corrosion cracking", "SCC", "应力腐蚀开裂"],
    "蠕变断裂": ["creep rupture", "持久强度", "rupture life"],
    "微动磨损": ["fretting", "fretting fatigue", "微动疲劳"],
    "外物损伤": ["FOD", "foreign object damage", "外来物损伤"],
    "叶片损伤": ["blade damage", "叶片缺口", "blade nicks", "trailing edge damage"],
    "涂层失效": ["coating failure", "涂层脱落", "coating delamination"],
    "晶粒边界": ["grain boundary", "晶界", "intergranular"],
    "无损检测": ["NDT", "non-destructive testing", "无损探伤", "NDE"],
    "孔探检查": ["borescope inspection", "内窥镜检查", "borescope"],
    "荧光探伤": ["fluorescent penetrant inspection", "FPI", "液体渗透检测"],
    "超声检测": ["ultrasonic testing", "UT", "超声波检测"],
    "金属疲劳": ["metal fatigue", "材料疲劳", "fatigue failure"],
    "持久寿命": ["endurance life", "耐久寿命", "service life"],
    "退化": ["degradation", "性能衰退", "performance deterioration"],
}

# 维修工艺术语 (T4.1 新增)
MAINTENANCE_TERMS = {
    "寿命限制件": ["life limited part", "LLP", "寿命件", "限寿件"],
    "翻修": ["overhaul", "大修", "发动机翻修", "engine overhaul"],
    "车间修理": ["shop repair", "修理", "repair", "维修"],
    "定期检查": ["periodic inspection", "定期检查", "scheduled maintenance"],
    "视情维修": ["on-condition maintenance", "视情检查", "condition monitoring"],
    "孔探检查": ["borescope inspection", "内窥镜检查", "发动机孔探"],
    "热部件检查": ["hot section inspection", "HSI", "热部件寿命检查"],
    "翻修周期": ["overhaul interval", "TBO", "time between overhaul"],
    "循环寿命": ["cyclic life", "飞行循环", "cycle life", "cycles"],
    "飞行小时": ["flight hours", "飞行时间", "EFH", "engine flight hours"],
    "持续适航文件": ["continuing airworthiness documents", "ICA", "Instructions for Continued Airworthiness"],
    "维修手册": ["maintenance manual", "AMM", "发动机维修手册", "Engine Maintenance Manual"],
    "故障排除": ["troubleshooting", "故障隔离", "fault isolation"],
    "修理限制": ["repair limits", "修理范围", "damage limits"],
    "适航指令": ["airworthiness directive", "AD", "适航性通告"],
    "服务通告": ["service bulletin", "SB", "服务通知"],
    "使用寿命": ["service life", "使用寿期", "design life"],
    "地面测试": ["ground test", "试车", "engine ground run"],
    "性能恢复": ["performance restoration", "性能修复", "engine restoration"],
    "在翼维修": ["on-wing maintenance", "在翼检查", "on-wing repair"],
}

# 噪声与排放术语 (T4.1 新增)
NOISE_EMISSION_TERMS = {
    "噪声认证": ["noise certification", "声学认证", "acoustic certification"],
    "有效感觉噪声": ["EPNL", "effective perceived noise level", "有效感知噪声级"],
    "侧方噪声": ["lateral noise", "侧向噪声", "flyover noise"],
    "进近噪声": ["approach noise", "进近声级"],
    "氮氧化物": ["NOx", "nitrogen oxides", "氮氧化物排放"],
    "碳氢化合物": ["HC", "hydrocarbon", "未燃烃", "unburned hydrocarbon"],
    "一氧化碳": ["CO", "carbon monoxide", "一氧化碳排放"],
    "烟度": ["smoke", "smoke number", "排烟", "smoke emission"],
    "排放认证": ["emission certification", "排放合规", "ICAO emission standards"],
    "燃烧室排放": ["combustor emission", "燃烧排放", "combustion emission"],
    "CAEP标准": ["CAEP", "Committee on Aviation Environmental Protection", "ICAO噪声标准"],
    "声功率": ["acoustic power", "声功率级", "sound power level"],
    "粒子物质": ["particulate matter", "PM", "颗粒物排放"],
    "低排放燃烧室": ["low emission combustor", "贫油燃烧", "lean burn combustor"],
    "排气": ["exhaust", "排气流", "exhaust gas", "尾喷流"],
}

# 压气机/涡轮气动性能术语 (T4.1 新增 - 对 CFD 工程师关键)
AERODYNAMIC_PERFORMANCE_TERMS = {
    "喘振裕度": ["surge margin", "失速裕度", "stall margin", "SM"],
    "压比": ["pressure ratio", "总压比", "overall pressure ratio", "OPR"],
    "效率": ["efficiency", "多变效率", "等熵效率", "adiabatic efficiency", "isentropic efficiency"],
    "特性图": ["compressor map", "压气机特性图", "performance map"],
    "稳定工作裕度": ["stability margin", "喘振边界", "surge line"],
    "质量流量": ["mass flow rate", "空气流量", "corrected flow", "折合流量"],
    "转速": ["rotational speed", "转速", "corrected speed", "折合转速", "RPM"],
    "级负荷": ["stage loading", "叶片负荷", "diffusion factor"],
    "扩散因子": ["diffusion factor", "D因子", "blade loading"],
    "落压比": ["stage pressure ratio", "级压比"],
    "喘振": ["surge", "喘振现象", "compressor surge", "surge instability"],
    "旋转失速": ["rotating stall", "旋转分离", "stall cell"],
    "颤振": ["flutter", "叶片颤振", "aeroelastic flutter", "blade flutter"],
    "强迫响应": ["forced response", "共振响应", "vibration response"],
    "振动": ["vibration", "叶片振动", "发动机振动", "mechanical vibration"],
    "临界转速": ["critical speed", "共振转速", "resonance speed"],
    "坎贝尔图": ["Campbell diagram", "共振图", "frequency diagram"],
    "声速": ["sonic velocity", "马赫数", "Mach number", "临界马赫数"],
    "跨声速": ["transonic", "跨声速压气机", "transonic compressor"],
    "叶型": ["blade profile", "翼型", "airfoil", "blade geometry"],
    "攻角": ["angle of attack", "冲角", "incidence angle"],
    "离设计点运行": ["off-design operation", "非设计点", "off-design performance"],
    "节流": ["throttling", "节流运行", "throttle setting"],
}

# 燃烧室与燃油系统术语 (T4.1 新增)
COMBUSTOR_FUEL_TERMS = {
    "燃烧室": ["combustor", "燃烧器", "combustion chamber", "火焰筒"],
    "主燃区": ["primary zone", "主燃烧区", "primary combustion zone"],
    "二次风": ["secondary air", "掺混空气", "dilution air"],
    "燃油喷嘴": ["fuel nozzle", "喷油嘴", "fuel injector"],
    "引火区": ["pilot zone", "引燃区", "pilot flame"],
    "点火": ["ignition", "起动点火", "ignition system"],
    "贫油熄火": ["lean blowout", "LBO", "贫熄火", "lean extinction"],
    "富油熄火": ["rich blowout", "RBO", "rich extinction"],
    "再燃": ["relight", "高空再燃", "altitude relight"],
    "火焰稳定": ["flame stabilization", "燃烧稳定", "flame stability"],
    "热斑": ["hot streak", "温度分布不均", "hot spot", "temperature distortion"],
    "出口温度分布": ["exit temperature profile", "出口温度场", "temperature traverse factor", "OTDF", "RTDF"],
    "当量比": ["equivalence ratio", "当量油气比", "fuel-air ratio", "FAR"],
    "液态水滴": ["water droplet ingestion", "冰晶进水", "rain ingestion"],
    "燃油加热": ["fuel heating", "燃油冷却润滑油", "heat management"],
    "燃油控制": ["fuel control", "燃油计量", "fuel metering unit", "FMU"],
    "燃油总管": ["fuel manifold", "燃油分配管", "fuel distribution"],
}

# 适航符合性验证方法术语 (T4.1 新增)
COMPLIANCE_METHOD_TERMS = {
    "符合性方法": ["means of compliance", "MOC", "验证方法", "compliance method"],
    "分析法": ["analysis", "计算分析", "MOC2", "analytical substantiation"],
    "试验法": ["testing", "试验验证", "MOC4", "MOC5", "test demonstration"],
    "检查法": ["inspection", "检查验证", "MOC6"],
    "演示法": ["demonstration", "功能演示", "MOC7"],
    "模拟法": ["simulation", "数值模拟", "CFD", "computational analysis"],
    "等效安全": ["equivalent safety", "等效适航", "equivalent level of safety"],
    "特殊条件": ["special condition", "特殊适航条件", "SC"],
    "豁免条款": ["exemption", "豁免", "deviation"],
    "审定计划": ["certification plan", "CP", "型号合格计划"],
    "符合性文件": ["compliance document", "符合性报告", "conformity document"],
    "审定基础": ["certification basis", "型号合格基础", "certification specification"],
    "问题纪要": ["issue paper", "IP", "审定问题纪要"],
    "专用条件": ["special conditions", "专用适航条件"],
    "符合性声明": ["statement of compliance", "SOC", "符合声明"],
    "型号合格证": ["type certificate", "TC", "型号合格"],
    "补充型号合格证": ["supplemental type certificate", "STC"],
    "零件制造人批准书": ["PMA", "parts manufacturer approval"],
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
    # v0.4 新增词典
    **TURBINE_COOLING_TERMS,
    **MATERIAL_DEFECT_TERMS,
    **MAINTENANCE_TERMS,
    **NOISE_EMISSION_TERMS,
    **AERODYNAMIC_PERFORMANCE_TERMS,
    **COMBUSTOR_FUEL_TERMS,
    **COMPLIANCE_METHOD_TERMS,
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
            "turbine_cooling": [],
            "material_defects": [],
            "maintenance": [],
            "noise_emission": [],
            "aerodynamics": [],
            "combustor": [],
            "compliance": [],
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

        # v0.4 新增分类
        for term, synonyms in TURBINE_COOLING_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["turbine_cooling"].append(term)

        for term, synonyms in MATERIAL_DEFECT_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["material_defects"].append(term)

        for term, synonyms in MAINTENANCE_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["maintenance"].append(term)

        for term, synonyms in NOISE_EMISSION_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["noise_emission"].append(term)

        for term, synonyms in AERODYNAMIC_PERFORMANCE_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["aerodynamics"].append(term)

        for term, synonyms in COMBUSTOR_FUEL_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["combustor"].append(term)

        for term, synonyms in COMPLIANCE_METHOD_TERMS.items():
            if term.lower() in query_lower or any(s.lower() in query_lower for s in synonyms):
                terms_found["compliance"].append(term)

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
