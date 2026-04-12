import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

try:
    from src.settings import has_real_value
except ImportError:
    # fallback definition
    def has_real_value(value):
        return bool(value and "your" not in value.lower() and "placeholder" not in value.lower())

try:
    import chromadb
    from chromadb.utils import embedding_functions
    from dotenv import load_dotenv
except ImportError:
    chromadb = None
    embedding_functions = None
    load_dotenv = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def tokenize_text(text: str) -> List[str]:
    """通用分词（单字符中文 + 英文单词）"""
    tokens: List[str] = []
    buffer: List[str] = []

    def flush_buffer() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in (text or "").lower():
        if "\u4e00" <= char <= "\u9fff":
            flush_buffer()
            tokens.append(char)
        elif char.isalnum() or char == "_":
            buffer.append(char)
        else:
            flush_buffer()

    flush_buffer()
    return [token for token in tokens if token.strip()]


def tokenize_for_bm25(text: str) -> List[str]:
    """
    BM25专用分词：中文使用bigram（保留上下文），英文按单词分词
    例如: "压气机喘振裕度" -> ["压气", "气机", "机喘", "喘振", "振裕", "裕度"]
    """
    tokens: List[str] = []
    buffer: List[str] = []
    chinese_buffer: List[str] = []

    def flush_buffer() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    def flush_chinese() -> None:
        """输出中文bigram"""
        if chinese_buffer:
            # 输出单个字符
            for char in chinese_buffer:
                tokens.append(char)
            # 输出bigram
            for i in range(len(chinese_buffer) - 1):
                tokens.append(chinese_buffer[i] + chinese_buffer[i + 1])
            chinese_buffer.clear()

    for char in (text or "").lower():
        if "\u4e00" <= char <= "\u9fff":
            if buffer:
                flush_buffer()
            chinese_buffer.append(char)
        elif char.isalnum() or char == "_":
            if chinese_buffer:
                flush_chinese()
            buffer.append(char)
        else:
            if chinese_buffer:
                flush_chinese()
            flush_buffer()

    if chinese_buffer:
        flush_chinese()
    flush_buffer()

    # Deduplicate while preserving order (same as extract_phrase_candidates)
    return list(dict.fromkeys(token for token in tokens if token.strip()))


def extract_phrase_candidates(text: str) -> List[str]:
    phrases: List[str] = []
    for block in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_\-]{2,}", text or ""):
        if len(block) >= 2:
            phrases.append(block.lower())
    return list(dict.fromkeys(phrases))


# ============================================================
# 同义词扩展字典（中 ↔ 英）
# ============================================================
SYNONYM_DICT: Dict[str, List[str]] = {
    # 核心动力装置
    "发动机": ["engine", "motor", "propulsion", "powerplant", "引擎"],
    "engine": ["发动机", "motor", "propulsion", "powerplant", "引擎"],
    "motor": ["发动机", "engine", "propulsion", "powerplant"],
    "propulsion": ["推进", "发动机", "动力系统"],
    "powerplant": ["动力装置", "发动机", "发电厂"],
    "引擎": ["engine", "motor", "propulsion"],

    # 压气机/涡轮
    "compressor": ["压气机", "空气压缩机", "压缩机"],
    "压气机": ["compressor", "compressor rotor", "空气压缩机"],
    "空气压缩机": ["compressor", "压气机"],
    "turbine": ["涡轮", "涡轮机", "透平", "涡轮发动机"],
    "涡轮": ["turbine", "turbine wheel", "涡轮机"],
    "涡轮机": ["turbine", "透平"],
    "透平": ["turbine", "涡轮机"],
    "转子": ["rotor", "转子组件"],
    "定子": ["stator", "静子"],

    # 喘振/失速
    "喘振": ["surge", "气流分离", "压气机喘振"],
    "喘振裕度": ["surge margin", "stall margin", "防喘振裕度"],
    "surge": ["喘振", "气流分离"],
    "stall": ["失速", "喘振", "气流分离"],
    "失速": ["stall", "气流分离"],
    "气流分离": ["flow separation", "surge", "stall"],

    # 叶片/轮
    "叶片": ["blade", "vane", "bucket", "工作叶片"],
    "blade": ["叶片", "工作叶片"],
    "vane": ["叶片", "导叶", "导向叶片"],
    "bucket": ["叶片", "涡轮叶片"],
    "轮": ["wheel", "叶轮", "轮盘"],
    "叶轮": ["impeller", "wheel", "rotor wheel"],

    # 适航/认证
    "适航": ["airworthiness", "certification", "批准", "适航性"],
    "airworthiness": ["适航", "飞行适航性", "航空适航"],
    "certification": ["认证", "审定", "发证", "资质"],
    "审定": ["certification", "approval", "审定合格"],
    "符合性": ["compliance", "conformity", "符合"],
    "compliance": ["符合性", "一致性", "合规"],

    # 规范/标准
    "规范": ["regulation", "standard", "specification", "规程"],
    "regulation": ["规范", "规章", "条例", "法规", "规章体系"],
    "standard": ["标准", "规范", "规格"],
    "specification": ["规范", "规格", "技术条件"],
    "规章": ["regulation", "rule", "规章文件"],
    "法规": ["regulation", "law", "法规文件"],

    # 材料/工艺
    "材料": ["material", "alloy", "component", "材质"],
    "material": ["材料", "材质", "原材料"],
    "alloy": ["合金", "金属材料"],
    "材质": ["material", "material property"],
    "工艺": ["process", "manufacturing process", "工艺方法"],
    "制造": ["manufacture", "manufacturing", "生产"],

    # 热力参数
    "温度": ["temperature", "thermal", "heat", "temperature limit"],
    "pressure": ["压力", "压强", "气压"],
    "压力": ["pressure", "压强", "气压"],
    "压强": ["pressure", "压力"],
    "转速": ["rotational speed", "rpm", "speed", "转速限制"],
    "rpm": ["转速", "转/分", "revolutions per minute"],
    "推力": ["thrust", "propulsive force", "推力值"],
    "thrust": ["推力", "推进力"],

    # 维修/检修
    "维修": ["maintenance", "repair", "overhaul", "service"],
    "maintenance": ["维修", "维护", "保养"],
    "repair": ["修理", "维修", "修复"],
    "overhaul": ["大修", "翻修", "全面检修"],
    "检修": ["inspection", "overhaul", "maintenance"],

    # 性能/寿命
    "性能": ["performance", "rating", "output", "特性"],
    "performance": ["性能", "表现", "运行性能"],
    "寿命": ["life", "durability", "longevity", "使用期限"],
    "life": ["寿命", "使用期限", "工作寿命"],
    " durability": ["耐久性", "寿命", "持久性"],

    # 测试/验证
    "测试": ["test", "testing", "试验", "检验"],
    "test": ["测试", "试验", "检测"],
    "testing": ["测试", "试验", "测试中"],
    "验证": ["verification", "validation", "proof", "确认"],
    "verification": ["验证", "核实", "证明"],
    "validation": ["验证", "确认", "有效性验证"],
    "试验": ["test", "testing", "实验"],

    # 安全/可靠性
    "安全": ["safety", "safe", "security", "可靠性"],
    "safety": ["安全", "安全性"],
    "reliability": ["可靠性", "可靠度", "可信性"],
    "可靠性": ["reliability", "dependability"],

    # 航空特定术语
    "航空": ["aviation", "aeronautics", "aircraft"],
    "aviation": ["航空", "航空学"],
    "aeronautics": ["航空学", "航空"],
    "飞机": ["aircraft", "airplane", "aeroplane"],
    "aircraft": ["飞机", "航空器", "飞行器"],
    "民航": ["civil aviation", "commercial aviation"],
    "民用航空": ["civil aviation", "公众航空"],

    # 发动机构型
    "涡轮风扇": ["turbofan", "turbo-fan", "fanj"],
    "turbofan": ["涡轮风扇", "turbo-fan"],
    "涡轮喷气": ["turbojet", "jet engine"],
    "turbojet": ["涡轮喷气", "喷气发动机"],
    "涡桨": ["turboprop", "propeller engine"],
    "turboprop": ["涡桨", "螺旋桨发动机"],
    "涡轴": ["turboshaft", "shaft turbine"],
    "turboshaft": ["涡轴", "轴发动机"],

    # 系统组件
    "燃油系统": ["fuel system", "燃油供给系统"],
    "fuel system": ["燃油系统", "燃料系统"],
    "润滑系统": ["lubrication system", "lubricating system"],
    "冷却系统": ["cooling system", "热管理系统"],
    "点火系统": ["ignition system", "点燃系统"],
    "启动系统": ["starting system", "起动系统"],
    "控制系统": ["control system", "调控系统", "FADEC"],
    "FADEC": ["全权数字式发动机控制", "FADEC系统", "digital engine control"],

    # 关键部件
    "燃烧室": ["combustion chamber", "燃烧器", " combustor"],
    "combustion chamber": ["燃烧室", "燃烧室组件"],
    "排气": ["exhaust", "exhaust system", "排气系统"],
    "exhaust": ["排气", "废气", "排气口"],
    "尾喷": ["nozzle", "exhaust nozzle", "喷管"],
    "nozzle": ["喷管", "尾喷", "排气口"],

    # 强度/疲劳
    "疲劳": ["fatigue", "endurance", "疲劳寿命"],
    "fatigue": ["疲劳", "疲劳强度"],
    "强度": ["strength", "intensity", "强度极限"],
    "stress": ["应力", "压力", "强度"],
    "strain": ["应变", "形变", "扭曲"],

    # 污染/排放
    "排放": ["emission", "exhaust emission", "排气"],
    "emission": ["排放", "排放物"],
    "污染": ["pollution", "contamination", "emission"],

    # 噪声/振动
    "噪声": ["noise", "sound level", "噪音"],
    "noise": ["噪声", "噪音", "声音"],
    "振动": ["vibration", "oscillation", "颤振"],
    "vibration": ["振动", "震动", "颤动"],

    # 附件/仪表
    "附件": ["accessory", "auxiliary", "配件"],
    "仪表": ["instrument", "gauge", "meter"],
    "传感器": ["sensor", "transducer", "探头"],

    # 型号/批次
    "型号": ["model", "type", "版本"],
    "批次": ["batch", "lot", "生产批次"],
    "构型": ["configuration", "arrangement", "配置"],

    # 复合术语（跨语言召回关键词）
    "涡轮叶片": ["turbine blade", "turbine vane", "blade", "叶片"],
    "turbine blade": ["涡轮叶片", "叶片", "turbine vane"],
    "turbine wheel": ["涡轮轮盘", "涡轮盘", "wheel"],
    "涡轮轮盘": ["turbine wheel", "turbine disk", "轮盘"],
    "温度范围": ["temperature range", "operating temperature", "温度限制"],
    "temperature range": ["温度范围", "温度限制", "operating temperature"],
    "适航审定": ["airworthiness certification", "type certification", "审定"],
    "airworthiness certification": ["适航审定", "型号合格审定", "certification"],
    "疲劳寿命": ["fatigue life", "fatigue", "life limit", "寿命"],
    "fatigue life": ["疲劳寿命", "疲劳", "life", "endurance"],
    "振动试验": ["vibration test", "vibration testing", "振动"],
    "vibration test": ["振动试验", "振动测试", "vibration"],
    "排放标准": ["emission standard", "emission limit", "排放"],
    "emission standard": ["排放标准", "排放限值", "emission"],
    "噪声审定": ["noise certification", "noise standard", "噪声"],
    "noise certification": ["噪声审定", "噪声认证", "noise"],
    "维修检查": ["maintenance inspection", "inspection", "维修"],
    "maintenance inspection": ["维修检查", "检查", "inspection"],
    "surge margin": ["喘振裕度", "stall margin", "防喘振裕度"],
    "stall margin": ["喘振裕度", "surge margin", "失速裕度"],
    "fuel system": ["燃油系统", "燃料系统", "fuel"],
    "compressor surge": ["压气机喘振", "喘振", "surge"],
    "压气机喘振": ["compressor surge", "喘振", "surge"],
    "bird ingestion": ["鸟撞", "吸鸟", "ingestion"],
    "鸟撞": ["bird ingestion", "bird strike", "吸鸟"],
    "overspeed": ["超速", "转速超限"],
    "超速": ["overspeed", "转速超限"],
    "containment": ["包容", "包容性"],
    "包容": ["containment", "包容性"],

    # 涡轮冷却系统
    "冷却": ["cooling", "thermal management", "heat transfer"],
    "cooling": ["冷却", "散热", "热管理"],
    "冷却气": ["cooling air", "cooling flow", "冷却空气"],
    "cooling air": ["冷却气", "冷却空气", "cooling flow"],
    "热障涂层": ["thermal barrier coating", "TBC", "隔热涂层"],
    "thermal barrier coating": ["热障涂层", "TBC", "隔热涂层"],
    "TBC": ["热障涂层", "thermal barrier coating"],
    "气膜冷却": ["film cooling", "冷却膜", "气膜"],
    "film cooling": ["气膜冷却", "冷却膜", "film"],
    "对流冷却": ["convection cooling", "内冷", "convective cooling"],
    "convection cooling": ["对流冷却", "内冷"],
    "涡轮进口温度": ["turbine inlet temperature", "TIT", "T4"],
    "turbine inlet temperature": ["涡轮进口温度", "TIT", "T4"],
    "TIT": ["涡轮进口温度", "turbine inlet temperature"],
    "排气温度": ["exhaust gas temperature", "EGT", "排温"],
    "exhaust gas temperature": ["排气温度", "EGT", "排温"],
    "EGT": ["排气温度", "exhaust gas temperature", "排温"],

    # 材料缺陷与无损检测
    "裂纹": ["crack", "fracture", "裂缝"],
    "crack": ["裂纹", "裂缝", "fracture"],
    "缺陷": ["defect", "flaw", "imperfection", "缺陷检测"],
    "defect": ["缺陷", "瑕疵", "flaw"],
    "无损检测": ["non-destructive testing", "NDT", "无损探伤"],
    "NDT": ["无损检测", "non-destructive testing", "无损探伤"],
    "non-destructive testing": ["无损检测", "NDT", "无损探伤"],
    "超声检测": ["ultrasonic testing", "UT", "超声波检测"],
    "ultrasonic testing": ["超声检测", "UT", "超声波"],
    "荧光检测": ["fluorescent penetrant inspection", "FPI", "渗透检测"],
    "FPI": ["荧光检测", "fluorescent penetrant inspection"],
    "磁粉检测": ["magnetic particle inspection", "MPI", "磁探"],
    "MPI": ["磁粉检测", "magnetic particle inspection"],
    "X射线检测": ["X-ray inspection", "radiographic testing", "RT"],
    "腐蚀": ["corrosion", "oxidation", "erosion", "腐蚀损伤"],
    "corrosion": ["腐蚀", "氧化", "侵蚀"],
    "氧化": ["oxidation", "corrosion", "高温氧化"],
    "oxidation": ["氧化", "corrosion", "高温氧化"],
    "蠕变": ["creep", "高温蠕变", "蠕变变形"],
    "creep": ["蠕变", "高温蠕变", "creep deformation"],
    "高周疲劳": ["high cycle fatigue", "HCF", "高频疲劳"],
    "HCF": ["高周疲劳", "high cycle fatigue"],
    "high cycle fatigue": ["高周疲劳", "HCF"],
    "低周疲劳": ["low cycle fatigue", "LCF", "低频疲劳"],
    "LCF": ["低周疲劳", "low cycle fatigue"],
    "low cycle fatigue": ["低周疲劳", "LCF"],

    # 维修工艺
    "翻修": ["overhaul", "大修", "全面检修"],
    "寿命限制件": ["life limited part", "LLP", "寿命件"],
    "LLP": ["寿命限制件", "life limited part"],
    "life limited part": ["寿命限制件", "LLP"],
    "孔探": ["borescope inspection", "内窥镜检查", "孔探检查"],
    "borescope": ["孔探", "内窥镜", "borescope inspection"],
    "borescope inspection": ["孔探", "内窥镜检查"],
    "热端部件": ["hot section", "hot section component", "高温部件"],
    "hot section": ["热端部件", "高温部件", "热端"],
    "冷端部件": ["cold section", "cold section component", "低温部件"],
    "修理方案": ["repair scheme", "repair procedure", "修理程序"],
    "repair": ["修理", "维修", "修复"],
    "发动机手册": ["engine manual", "AMM", "维修手册"],
    "AMM": ["发动机手册", "aircraft maintenance manual", "维修手册"],
    "持续适航": ["continued airworthiness", "持续适航文件"],
    "continued airworthiness": ["持续适航", "持续适航文件"],

    # 噪声与排放
    "噪声": ["noise", "sound level", "噪音"],
    "noise": ["噪声", "噪音", "声音"],
    "声压级": ["sound pressure level", "SPL", "噪声级"],
    "SPL": ["声压级", "sound pressure level"],
    "有效感觉噪声级": ["effective perceived noise level", "EPNL", "感觉噪声"],
    "EPNL": ["有效感觉噪声级", "effective perceived noise level"],
    "NOx": ["氮氧化物", "nitrogen oxide", "氮氧化合物"],
    "氮氧化物": ["NOx", "nitrogen oxide"],
    "CO": ["一氧化碳", "carbon monoxide"],
    "一氧化碳": ["CO", "carbon monoxide"],
    "碳氢化合物": ["hydrocarbon", "HC", "未燃碳氢"],
    "hydrocarbon": ["碳氢化合物", "HC"],
    "烟雾": ["smoke", "soot", "烟"],
    "smoke": ["烟雾", "soot", "烟"],
    "排放指数": ["emission index", "EI", "排放因子"],
    "emission index": ["排放指数", "EI"],
    "ICAO": ["国际民航组织", "International Civil Aviation Organization"],
    "国际民航组织": ["ICAO", "International Civil Aviation Organization"],

    # 结构强度
    "极限载荷": ["ultimate load", "极限强度", "极限力"],
    "ultimate load": ["极限载荷", "极限强度"],
    "限制载荷": ["limit load", "限制力", "设计载荷"],
    "limit load": ["限制载荷", "限制力"],
    "安全系数": ["safety factor", "factor of safety", "安全裕度"],
    "safety factor": ["安全系数", "factor of safety"],
    "factor of safety": ["安全系数", "safety factor"],
    "屈服强度": ["yield strength", "屈服极限"],
    "yield strength": ["屈服强度", "屈服极限"],
    "抗拉强度": ["tensile strength", "极限抗拉强度"],
    "tensile strength": ["抗拉强度", "极限抗拉强度"],
    "断裂韧性": ["fracture toughness", "断裂韧度"],
    "fracture toughness": ["断裂韧性", "断裂韧度"],

    # 气动性能
    "效率": ["efficiency", "热效率", "绝热效率"],
    "efficiency": ["效率", "热效率"],
    "压比": ["pressure ratio", "总压比", "增压比"],
    "pressure ratio": ["压比", "总压比", "增压比"],
    "流量": ["flow rate", "mass flow", "空气流量"],
    "flow rate": ["流量", "质量流量"],
    "mass flow": ["质量流量", "流量", "空气流量"],
    "推重比": ["thrust-to-weight ratio", "TWR", "比推力"],
    "thrust-to-weight ratio": ["推重比", "TWR"],
    "耗油率": ["specific fuel consumption", "SFC", "燃油消耗率"],
    "SFC": ["耗油率", "specific fuel consumption"],
    "specific fuel consumption": ["耗油率", "SFC", "燃油消耗率"],

    # ── v0.7: 通用定义类术语 (提升 general 问题召回) ──────────────────────
    # 核心机 / Gas core
    "核心机": ["gas core", "core engine", "燃气发生器", "gas generator", "HP core",
               "engine core", "hot section"],
    "gas core": ["核心机", "core engine", "燃气发生器", "gas generator"],
    "core engine": ["核心机", "gas core", "engine core"],
    "燃气发生器": ["gas generator", "核心机", "core engine", "gas core"],
    "gas generator": ["燃气发生器", "核心机", "core engine"],

    # FADEC
    "FADEC": ["Full Authority Digital Engine Control", "全权限数字发动机控制",
              "发动机控制系统", "电子发动机控制", "EEC", "ECU",
              "digital engine control", "engine electronic control",
              "数字电子控制器", "engine control unit"],
    "fadec": ["Full Authority Digital Engine Control", "全权限数字发动机控制",
              "EEC", "ECU", "digital engine control"],
    "Full Authority Digital Engine Control": ["FADEC", "全权限数字发动机控制"],
    "full authority digital engine control": ["FADEC", "fadec", "EEC", "ECU"],
    "EEC": ["FADEC", "engine electronic control", "发动机电子控制"],
    "发动机控制系统": ["FADEC", "EEC", "engine control", "engine management system"],

    # 活塞式发动机 vs 燃气涡轮
    "活塞": ["piston", "reciprocating", "往复", "活塞式"],
    "piston": ["活塞", "reciprocating", "piston engine"],
    "往复式": ["reciprocating", "piston", "活塞式"],
    "活塞式发动机": ["piston engine", "reciprocating engine", "往复式发动机"],
    "piston engine": ["活塞式发动机", "reciprocating engine", "往复式发动机", "活塞"],
    "reciprocating engine": ["活塞式发动机", "piston engine", "往复式发动机"],
    "燃气涡轮发动机": ["gas turbine engine", "jet engine", "涡轮发动机",
                    "gas turbine", "turbojet", "turbofan", "turboprop"],
    "gas turbine engine": ["燃气涡轮发动机", "涡轮发动机", "jet engine", "gas turbine"],
    "gas turbine": ["燃气涡轮发动机", "涡轮发动机", "燃气轮机"],

    # 型号合格证
    "型号合格证": ["Type Certificate", "TC", "type certification", "type approval"],
    "type certificate": ["型号合格证", "TC", "type approval"],
    "TC": ["型号合格证", "type certificate", "type certification"],
}

# ============================================================
# 查询意图模式
# ============================================================
INTENT_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "regulatory": {
        "zh": ["要求", "规定", "必须", "应当", "限制", "标准", "规范", "批准", "符合性", "偏离", "豁免", "审定"],
        "en": ["require", "requirement", "standard", "shall", "must", "compliance", "deviation", "exemption"],
    },
    "method": {
        "zh": ["如何", "怎么", "方法", "步骤", "流程", "操作", "检测", "计算", "验证", "试验", "测试", "安装", "检查", "工作原理"],
        "en": ["how", "method", "procedure", "step", "process", "calculate", "determine", "verify", "test", "install", "inspect"],
    },
    "comparison": {
        "zh": ["区别", "差异", "比较", "对比", "不同", "优缺点", "哪一个更好", "异同", "有何不同", "差异大吗"],
        "en": ["difference", "compare", "comparison", "versus", "vs", "between", "advantage", "disadvantage"],
    },
    "definition": {
        "zh": ["什么是", "定义", "含义", "概念", "解释", "说明", "是指", "包括哪些", "工作原理", "什么意思", "含义是"],
        "en": ["what is", "definition", "meaning", "concept", "explain", "describe", "define", "include"],
    },
    "numerical": {
        "zh": ["多少", "数值", "范围", "最小", "最大", "极限", "限制值", "阈值", "温度", "压力", "转速", "飞行小时", "摄氏"],
        "en": ["how many", "how much", "value", "range", "minimum", "maximum", "limit", "threshold", "temperature", "pressure", "rpm"],
    },
    "cross_reference": {
        "zh": ["对应条款", "等效条款", "对应", "等效", "相当于", "与...对应", "交叉", "交叉点"],
        "en": ["corresponds to", "correspond to", "equivalent to", "equivalent regulation", "correspondence"],
    },
}

# ============================================================
# 权威来源优先级
# ============================================================
AUTHORITY_SCORES: Dict[str, float] = {
    "CCAR": 10.0, "CAAC": 8.0,
    "FAA": 9.0, "FAR": 9.0, "14 CFR": 8.5, "AC": 7.0,
    "EASA": 9.0, "CS": 8.0, "AMC": 6.0,
    "SAE": 6.0, "ISO": 5.0, "ASTM": 5.0,
}


def expand_synonyms(text: str) -> List[str]:
    """扩展查询文本的同义词 - 优先提取中文短语再扩展"""
    if not text:
        return []
    # 先提取短语（2+字符的中文词或英文词）
    phrases = extract_phrase_candidates(text.lower())
    expanded = set(phrases)
    for phrase in phrases:
        if phrase in SYNONYM_DICT:
            expanded.update(SYNONYM_DICT[phrase])
            for syn in SYNONYM_DICT[phrase]:
                if syn in SYNONYM_DICT:
                    expanded.update(SYNONYM_DICT[syn])
    return list(expanded)


def expand_mixed_query(query: str) -> List[str]:
    """
    多语言混合查询增强：分别处理中文和英文部分，合并同义词扩展。

    支持场景：
    - 纯中文：  "压气机喘振裕度"
    - 纯英文：  "compressor surge margin"
    - 中英混合："compressor 压气机 喘振"

    返回去重后的增强查询词列表（含原始词和同义词）。
    """
    if not query:
        return []

    import re as _re

    # 分离中文和英文部分
    zh_parts = _re.findall(r'[\u4e00-\u9fff]+', query)
    en_parts = _re.findall(r'[a-zA-Z][a-zA-Z0-9\-]*', query)

    terms: set = set()

    # 处理中文部分：提取短语并扩展
    # 同时做滑动 n-gram 切分（2-5字），以命中 SYNONYM_DICT 中的子词条
    # 例如 "什么是燃气涡轮发动机的核心机" → 还会尝试 "核心机"/"燃气涡轮"/"发动机" 等
    for zh in zh_parts:
        terms.add(zh)
        terms.update(expand_synonyms(zh))
        # n-gram 子词扩展（仅当整串长度 > 4 时才值得切分）
        if len(zh) > 4:
            for n in (2, 3, 4, 5):
                for start in range(len(zh) - n + 1):
                    sub = zh[start:start + n]
                    if sub in SYNONYM_DICT:
                        terms.add(sub)
                        terms.update(SYNONYM_DICT[sub])

    # 处理英文部分：单词 + 相邻双词组合 + 扩展
    for en in en_parts:
        terms.add(en.lower())
        terms.update(expand_synonyms(en.lower()))

    # 尝试英文相邻词组合（bigram phrases）
    if len(en_parts) >= 2:
        for i in range(len(en_parts) - 1):
            phrase = f"{en_parts[i].lower()} {en_parts[i+1].lower()}"
            terms.add(phrase)
            terms.update(expand_synonyms(phrase))

    # 保留原始完整查询
    terms.add(query)

    return [t for t in terms if t.strip()]


# Public alias used by T5.3 acceptance tests and external callers.
expand_query_multilingual = expand_mixed_query


def detect_query_intent(query: str) -> Dict[str, float]:
    """检测查询意图及置信度 - 增强版"""
    query_lower = query.lower()
    tokens = tokenize_text(query_lower)
    scores = {intent: 0.0 for intent in INTENT_PATTERNS.keys()}

    for intent, patterns in INTENT_PATTERNS.items():
        for lang, pattern_list in patterns.items():
            for pattern in pattern_list:
                # 精确匹配权重更高
                if pattern in query_lower:
                    scores[intent] += 3.0
                # token级别匹配
                pattern_tokens = tokenize_text(pattern)
                for pt in pattern_tokens:
                    if pt in tokens:
                        scores[intent] += 0.5
                        break

    # 位置加权：意图词在查询开头权重更高
    for intent, patterns in INTENT_PATTERNS.items():
        for lang, pattern_list in patterns.items():
            for pattern in pattern_list:
                idx = query_lower.find(pattern)
                if idx >= 0 and idx < 5:  # 在前5个字符
                    scores[intent] += 2.0

    # 长度归一化
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    # 意图组合检测：如果是法规+方法混合查询，赋予中间值
    if scores.get("regulatory", 0) > 0.3 and scores.get("method", 0) > 0.2:
        combined = (scores["regulatory"] + scores["method"]) / 2
        scores["regulatory"] = combined * 0.6
        scores["method"] = combined * 0.6

    return scores


def get_primary_intent(query: str) -> str:
    """获取主要意图类型"""
    intent_scores = detect_query_intent(query)
    return max(intent_scores, key=intent_scores.get)


def get_authority_score(metadata: Dict) -> float:
    """计算文档权威性分数"""
    source = metadata.get("source", "")
    doc_type = metadata.get("document_type", "")
    score = 0.0
    source_upper = source.upper()
    doc_type_upper = doc_type.upper()
    for authority, weight in AUTHORITY_SCORES.items():
        if authority.upper() in source_upper or authority.upper() in doc_type_upper:
            score = max(score, weight)
    if metadata.get("chapter") and any(c.isdigit() for c in metadata.get("chapter", "")):
        score += 1.0
    return score


class SimpleHashEmbeddingFunction:
    """Offline-safe embedding fallback for local development."""

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in input:
            vector = [0.0] * self.dimension
            tokens = tokenize_text(text)
            if not tokens:
                embeddings.append(vector)
                continue

            for token in tokens:
                slot = hash(token) % self.dimension
                vector[slot] += 1.0

            norm = sum(value * value for value in vector) ** 0.5 or 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "simple_hash"

    @staticmethod
    def build_from_config(config):
        return SimpleHashEmbeddingFunction(dimension=config.get("dimension", 256))

    def get_config(self):
        return {"dimension": self.dimension}


class JinaEmbeddingFunction:
    """Jina AI embedding - free, supports Chinese and English."""

    def __init__(self, api_key: str = None, model: str = "jina-embeddings-v3"):
        self.api_key = api_key or os.getenv("JINA_API_KEY", "")
        self.model = model
        self.dimension = 1024  # jina-embeddings-v3 output dimension

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not self.api_key:
            logger.warning("JINA_API_KEY not set, using hash fallback")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)

        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "input": input
            }
            response = requests.post(
                "https://api.jina.ai/v1/embeddings",
                headers=headers,
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                return [item["embedding"] for item in data["data"]]
            else:
                logger.warning(f"Jina API error: {response.status_code}, using hash fallback")
                return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)
        except Exception as e:
            logger.warning(f"Jina embedding failed: {e}, using hash fallback")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "jina"

    def get_config(self):
        return {"model": self.model, "dimension": self.dimension}


class MinimaxEmbeddingFunction:
    """Minimax embedding via OpenAI-compatible API."""

    def __init__(self, api_key: str = None, base_url: str = "https://api.minimax.chat/v1"):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self.base_url = base_url
        self.dimension = 1536  # default dimension for minimax embedding

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not self.api_key:
            logger.warning("MINIMAX_API_KEY not set, using hash fallback")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)

        try:
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "embo-01",
                "texts": input  # Minimax uses "texts" not "input"
            }
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if "vectors" in data and data["vectors"]:
                    return data["vectors"]
                elif "data" in data and data["data"]:
                    return [item["embedding"] for item in data["data"]]
            logger.warning(f"Minimax API error: {response.status_code} - {response.text[:200]}")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)
        except Exception as e:
            logger.warning(f"Minimax embedding failed: {e}, using hash fallback")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "minimax"

    def get_config(self):
        return {"dimension": self.dimension}


class OllamaEmbeddingFunction:
    """Local Ollama embedding using nomic-embed-text."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "nomic-embed-text"
        self.dimension = 768  # nomic-embed-text output dimension

    def __call__(self, input: List[str]) -> List[List[float]]:
        try:
            import requests
            headers = {"Content-Type": "application/json"}
            embeddings = []
            for text in input:
                payload = {"model": self.model, "prompt": text}
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if response.status_code == 200:
                    data = response.json()
                    embeddings.append(data.get("embedding", []))
                else:
                    logger.warning(f"Ollama embedding failed: {response.status_code}")
                    embeddings.append([0.0] * self.dimension)

            if not embeddings or all(len(e) == 0 for e in embeddings):
                logger.warning("Ollama returned no embeddings, using hash fallback")
                return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)
            return embeddings
        except Exception as e:
            logger.warning(f"Ollama embedding failed: {e}, using hash fallback")
            return SimpleHashEmbeddingFunction(dimension=self.dimension).__call__(input)

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "ollama"

    def get_config(self):
        return {"model": self.model, "dimension": self.dimension}


# ============================================================
# BM25 关键词检索器
# ============================================================
import math
from collections import Counter


class BM25:
    """
    BM25 关键词检索算法
    用于混合检索中的关键词匹配
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avgdl = 0
        self.doc_freqs = {}  # term -> doc_freq
        self.doc_len = {}    # doc_id -> term count
        self.doc_texts = {}  # doc_id -> text

    def index(self, documents: List[Dict]) -> None:
        """建立BM25索引"""
        self.doc_count = len(documents)
        self.doc_len = {}
        self.doc_texts = {}
        term_doc_freq = Counter()

        for idx, doc in enumerate(documents):
            doc_id = doc.get("id", f"doc_{idx}")
            text = doc.get("text", "")
            tokens = tokenize_for_bm25(text.lower())

            self.doc_texts[doc_id] = tokens
            self.doc_len[doc_id] = len(tokens)

            for term in set(tokens):
                term_doc_freq[term] += 1

        self.doc_freqs = dict(term_doc_freq)
        self.avgdl = sum(self.doc_len.values()) / self.doc_count if self.doc_count > 0 else 0
        logger.info(f"[BM25] Indexed {self.doc_count} documents, vocab size: {len(self.doc_freqs)}")

    def search(self, query: str, top_k: int = 10) -> List[tuple[str, float]]:
        """
        BM25检索
        返回: List[(doc_id, score)]
        """
        if not self.doc_count:
            return []

        query_tokens = tokenize_for_bm25(query.lower())
        if not query_tokens:
            return []

        doc_scores = {}

        for doc_id, tokens in self.doc_texts.items():
            if not tokens:
                continue

            doc_len = self.doc_len[doc_id]
            score = 0.0

            # 计算BM25分数
            for term in query_tokens:
                if term not in self.doc_freqs:
                    continue

                df = self.doc_freqs[term]
                if df == 0:
                    continue

                tf = tokens.count(term)
                if tf == 0:
                    continue

                # BM25公式
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
                tf_component = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))

                score += idf * tf_component

            if score > 0:
                doc_scores[doc_id] = score

        # 按分数排序
        sorted_scores = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]


def reciprocal_rank_fusion(
    vector_results: List[tuple[str, float]],
    bm25_results: List[tuple[str, float]],
    k: float = 60
) -> List[tuple[str, float]]:
    """
    Reciprocal Rank Fusion (RRF) - 融合多个检索结果

    Args:
        vector_results: 向量检索结果 [(doc_id, score)]
        bm25_results: BM25检索结果 [(doc_id, score)]
        k: RRF参数，默认60

    Returns:
        融合后的结果 [(doc_id, combined_score)]
    """
    rrf_scores = {}

    # 向量检索结果打分
    for rank, (doc_id, _) in enumerate(vector_results):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)

    # BM25结果打分
    for rank, (doc_id, _) in enumerate(bm25_results):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)

    # 按融合分数排序
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


class VectorStoreEngine:
    """
    Handles indexing of document chunks into a vector database for semantic retrieval.
    """

    # 缓存大小限制
    MAX_INDEXED_CACHE = 1000
    MAX_QUERY_CACHE = 500

    def __init__(self, db_dir: str = "./data/processed/chroma_db", collection_name: str = "regulations"):
        if load_dotenv:
            load_dotenv()

        configured_dir = os.getenv("CHROMA_DB_DIR", db_dir)
        self.db_dir = str(Path(configured_dir).resolve())
        self.collection_name = collection_name
        self._indexed_cache: Dict[str, Dict] = {}
        self._query_cache: Dict[tuple[str, int], List[Dict]] = {}

        # BM25索引（用于混合检索）
        self._bm25_index: BM25 = None
        self._bm25_indexed = False

        if not chromadb:
            logger.warning("chromadb is not installed. Running in mock mode.")
            self.collection = None
            return

        self._repair_broken_store()
        self.client = chromadb.PersistentClient(path=self.db_dir)

        embedding_function = None
        # Embedding服务优先级：EMBEDDING_API_KEY > JINA_API_KEY > OLLAMA > MINIMAX > 离线hash
        if has_real_value(os.getenv("EMBEDDING_API_KEY")):
            logger.info("Using OpenAI embeddings (text-embedding-3-small).")
            embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("EMBEDDING_API_KEY"),
                model_name="text-embedding-3-small",
            )
        elif has_real_value(os.getenv("JINA_API_KEY")):
            logger.info("Using Jina AI embeddings (jina-embeddings-v3).")
            embedding_function = JinaEmbeddingFunction(api_key=os.getenv("JINA_API_KEY"))
        elif os.getenv("OLLAMA_API_KEY") == "available":
            logger.info("Using local Ollama embeddings (nomic-embed-text).")
            embedding_function = OllamaEmbeddingFunction()
        elif has_real_value(os.getenv("MINIMAX_API_KEY")):
            logger.info("Using Minimax embeddings (embo-01).")
            embedding_function = MinimaxEmbeddingFunction(api_key=os.getenv("MINIMAX_API_KEY"))
        else:
            logger.info("No embedding API key configured. Using offline hash embeddings.")
            embedding_function = SimpleHashEmbeddingFunction()
        self.embedding_function = embedding_function

        self.collection = self.client.get_or_create_collection(name=self.collection_name, embedding_function=embedding_function)
        logger.info("Initialized ChromaDB collection: %s", self.collection_name)

    def _repair_broken_store(self) -> None:
        db_path = Path(self.db_dir)
        db_path.mkdir(parents=True, exist_ok=True)

        sqlite_file = db_path / "chroma.sqlite3"
        journal_file = db_path / "chroma.sqlite3-journal"
        if sqlite_file.exists() and sqlite_file.stat().st_size == 0:
            logger.warning("Detected a zero-byte Chroma sqlite file. Rebuilding store directory.")
            sqlite_file.unlink(missing_ok=True)
            journal_file.unlink(missing_ok=True)

    def _make_chunk_id(self, chunk: Dict, index: int) -> str:
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "unknown")
        chapter = metadata.get("chapter", "")
        section = metadata.get("section", "")
        text = chunk.get("original_text") or chunk.get("text", "")
        stable_input = f"{source}|{chapter}|{section}|{text[:256]}|{index}"
        digest = hashlib.sha1(stable_input.encode("utf-8")).hexdigest()[:16]
        return f"{Path(source).stem}:{digest}"

    def index_chunks(self, chunks: List[Dict]) -> None:
        if not self.collection:
            logger.info("Mock Indexing: Would have indexed %s chunks.", len(chunks))
            return

        if not chunks:
            logger.warning("No chunks provided to index.")
            return

        normalized_chunks: List[Dict] = []
        seen_ids = set()
        for index, chunk in enumerate(chunks):
            chunk_id = chunk.get("metadata", {}).get("chunk_id") or self._make_chunk_id(chunk, index)
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)

            metadata = dict(chunk.get("metadata", {}))
            metadata["chunk_id"] = chunk_id
            normalized_chunks.append(
                {
                    "id": chunk_id,
                    "text": chunk.get("text", ""),
                    "original_text": chunk.get("original_text", ""),
                    "metadata": metadata,
                }
            )

        documents = [chunk["text"] for chunk in normalized_chunks]
        metadatas = [chunk["metadata"] for chunk in normalized_chunks]
        ids = [chunk["id"] for chunk in normalized_chunks]

        logger.info("Indexing %s document chunks into the database...", len(normalized_chunks))
        if hasattr(self.collection, "upsert"):
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        else:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

        self._indexed_cache = {chunk["id"]: chunk for chunk in normalized_chunks}
        self._bm25_index = None
        self._bm25_indexed = False
        self._query_cache.clear()
        self._evict_caches_if_needed()
        logger.info("Indexing complete.")

    def _evict_caches_if_needed(self) -> None:
        """缓存上限保护：超过限制时淘汰最旧条目"""
        if len(self._indexed_cache) > self.MAX_INDEXED_CACHE:
            # 淘汰最早的1/4
            keys_to_remove = list(self._indexed_cache.keys())[:self.MAX_INDEXED_CACHE // 4]
            for k in keys_to_remove:
                del self._indexed_cache[k]
            logger.info("Evicted %d entries from indexed_cache", len(keys_to_remove))

        if len(self._query_cache) > self.MAX_QUERY_CACHE:
            keys_to_remove = list(self._query_cache.keys())[:self.MAX_QUERY_CACHE // 4]
            for k in keys_to_remove:
                del self._query_cache[k]
            logger.info("Evicted %d entries from query_cache", len(keys_to_remove))

    def add_chunks(self, chunks: List[Dict]) -> None:
        """
        Add chunks to existing collection without recreating it.
        Useful for incremental updates.
        """
        if not self.collection:
            logger.info("Mock Add: Would have added %s chunks.", len(chunks))
            return

        if not chunks:
            logger.warning("No chunks provided to add.")
            return

        normalized_chunks: List[Dict] = []
        seen_ids = set()
        for index, chunk in enumerate(chunks):
            chunk_id = chunk.get("metadata", {}).get("chunk_id") or self._make_chunk_id(chunk, index)
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)

            metadata = dict(chunk.get("metadata", {}))
            metadata["chunk_id"] = chunk_id
            normalized_chunks.append(
                {
                    "id": chunk_id,
                    "text": chunk.get("text", ""),
                    "original_text": chunk.get("original_text", ""),
                    "metadata": metadata,
                }
            )

        documents = [chunk["text"] for chunk in normalized_chunks]
        metadatas = [chunk["metadata"] for chunk in normalized_chunks]
        ids = [chunk["id"] for chunk in normalized_chunks]

        logger.info("Adding %s document chunks to existing collection...", len(normalized_chunks))
        if hasattr(self.collection, "upsert"):
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        else:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

        # Update cache
        for chunk in normalized_chunks:
            self._indexed_cache[chunk["id"]] = chunk
        self._bm25_index = None
        self._bm25_indexed = False
        self._query_cache.clear()
        self._evict_caches_if_needed()
        logger.info("Add complete.")

    def _recreate_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
        )
        self._indexed_cache.clear()
        self._query_cache.clear()
        self._bm25_index = None
        self._bm25_indexed = False

    def _hydrate_item(self, doc_id: str) -> Dict | None:
        cached = self._indexed_cache.get(doc_id)
        if cached:
            return {
                "id": doc_id,
                "text": cached.get("text", ""),
                "original_text": cached.get("original_text", ""),
                "metadata": dict(cached.get("metadata", {})),
            }

        if not self.collection or not hasattr(self.collection, "get"):
            return None

        try:
            data = self.collection.get(ids=[doc_id])
        except Exception as exc:
            logger.warning("[Hybrid] Failed to hydrate BM25-only doc %s: %s", doc_id, exc)
            return None

        if not data or not data.get("ids"):
            return None

        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        item = {
            "id": data["ids"][0],
            "text": documents[0] if documents else "",
            "metadata": metadatas[0] if metadatas else {},
        }
        return item

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """混合检索：向量检索 + BM25 融合"""
        if not self.collection:
            logger.info("Mock Search Execution for query: '%s'", query)
            return [{"text": "Mock retrieved document segment", "metadata": {"source": "CCAR-33_mock"}}]

        cache_key = ((query or "").strip().lower(), top_k)
        if cache_key in self._query_cache:
            logger.info("[Cache HIT] query='%s' top_k=%d cached_results=%d",
                query, top_k, len(self._query_cache[cache_key]))
            return list(self._query_cache[cache_key])

        logger.info("[Cache MISS] query='%s' top_k=%d", query, top_k)

        # 使用更大的候选集用于混合检索
        candidate_count = max(top_k * 4, 20)

        # 1. 向量检索
        logger.info("Executing hybrid search for: '%s'", query)
        vector_results = self.collection.query(query_texts=[query], n_results=candidate_count)

        vector_items: List[Dict] = []
        vector_scores: List[tuple[str, float]] = []
        if vector_results and vector_results.get("documents"):
            for idx in range(len(vector_results["documents"][0])):
                item = {
                    "text": vector_results["documents"][0][idx],
                    "metadata": vector_results["metadatas"][0][idx],
                    "id": vector_results["ids"][0][idx],
                }
                cached = self._indexed_cache.get(item["id"])
                if cached and cached.get("original_text"):
                    item["original_text"] = cached["original_text"]
                vector_items.append(item)
                vector_scores.append((item["id"], 1.0 - idx * 0.05))  # 模拟相似度分数

        # 2. BM25检索（懒加载索引 + 同义词扩展）
        self._ensure_bm25_indexed()
        bm25_scores: List[tuple[str, float]] = []
        if self._bm25_index:
            # 主查询检索
            bm25_scores = self._bm25_index.search(query, top_k=candidate_count)

            # 同义词扩展检索：使用混合查询增强（支持中英混合）
            expanded_terms = expand_mixed_query(query)
            synonym_scores_map: Dict[str, float] = {}
            for syn_term in expanded_terms:
                if syn_term.lower() != query.lower() and len(syn_term) > 1:
                    syn_results = self._bm25_index.search(syn_term, top_k=candidate_count)
                    for doc_id, score in syn_results:
                        # 同义词结果权重降低（0.3），避免喧宾夺主
                        synonym_scores_map[doc_id] = synonym_scores_map.get(doc_id, 0.0) + score * 0.3

            # 合并同义词分数到主分数
            if synonym_scores_map:
                combined_scores: Dict[str, float] = dict(bm25_scores)
                for doc_id, syn_score in synonym_scores_map.items():
                    combined_scores[doc_id] = combined_scores.get(doc_id, 0.0) + syn_score
                bm25_scores = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:candidate_count]

            logger.info(f"[BM25] Retrieved {len(bm25_scores)} results (expanded with {len(expanded_terms)} synonyms)")

        # 3. 融合检索结果
        if vector_scores and bm25_scores:
            fused_ids = reciprocal_rank_fusion(vector_scores, bm25_scores, k=60)
            # 按融合顺序重排
            id_to_item = {item["id"]: item for item in vector_items}
            fused_items = []
            for doc_id, _ in fused_ids:
                if doc_id in id_to_item:
                    fused_items.append(id_to_item[doc_id])
            # 添加BM25独有的结果
            seen_ids = set(item["id"] for item in fused_items)
            for doc_id, score in bm25_scores:
                if doc_id not in seen_ids and len(fused_items) < candidate_count:
                    hydrated = id_to_item.get(doc_id) or self._hydrate_item(doc_id)
                    if hydrated:
                        fused_items.append(hydrated)
                        seen_ids.add(doc_id)
            retrieved_items = fused_items
            logger.info(f"[Hybrid] Fused {len(vector_items)} vector + {len(bm25_scores)} BM25 -> {len(retrieved_items)} results")
        else:
            retrieved_items = vector_items

        # 4. 关键词重排
        reranked = self._rerank_by_keywords(query, retrieved_items, top_k)
        final_items = reranked[:top_k] if reranked else retrieved_items[:top_k]

        self._query_cache[cache_key] = list(final_items)
        self._evict_caches_if_needed()
        return final_items

    async def async_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        异步混合检索：使用 asyncio.to_thread 将同步搜索操作卸到线程池，
        避免阻塞事件循环。
        """
        import asyncio
        return await asyncio.to_thread(self.search, query, top_k)

    def _ensure_bm25_indexed(self) -> None:
        """懒加载BM25索引"""
        if self._bm25_indexed:
            return

        if not self.collection:
            self._bm25_indexed = True
            return

        try:
            # 获取所有已索引的文档用于BM25
            all_data = self.collection.get()
            if all_data and all_data.get("documents"):
                docs_for_bm25 = []
                for idx in range(len(all_data["documents"])):
                    docs_for_bm25.append({
                        "id": all_data["ids"][idx],
                        "text": all_data["documents"][idx],
                        "metadata": all_data.get("metadatas", [{}])[idx] if all_data.get("metadatas") else {}
                    })
                self._bm25_index = BM25()
                self._bm25_index.index(docs_for_bm25)
                logger.info(f"[BM25] Built index with {len(docs_for_bm25)} documents")
        except Exception as e:
            logger.warning(f"[BM25] Failed to build index: {e}")

        self._bm25_indexed = True

    def _rerank_by_keywords(self, query: str, items: List[Dict], top_k: int) -> List[Dict]:
        """增强rerank算法：同义词扩展 + 权威来源优先 + 意图匹配 + 结构加权"""
        if not items:
            return []

        expanded_tokens = expand_mixed_query(query)
        query_tokens = [t for t in tokenize_text(query.lower()) if len(t) > 1 or "\u4e00" <= t <= "\u9fff"]
        phrase_candidates = extract_phrase_candidates(query)[:8]

        if not query_tokens and not phrase_candidates and not expanded_tokens:
            return items[:top_k]

        intent_scores = detect_query_intent(query)

        scored: List[tuple[float, Dict]] = []
        for item in items[: max(top_k * 3, 12)]:
            metadata = item.get("metadata", {})
            searchable_parts = [
                metadata.get("chapter", ""),
                metadata.get("section", ""),
                metadata.get("document", ""),
                metadata.get("title", ""),
                item.get("text", "")[:1000],
            ]
            haystack = " ".join(searchable_parts).lower()
            score = 0.0

            # ===== 关键词匹配 =====
            for token in query_tokens:
                if token in haystack:
                    score += 4 if len(token) > 1 else 2
                # 英文大小写不敏感匹配
                if token.upper() in haystack.upper():
                    score += 1

            # ===== 同义词匹配 =====
            for token in expanded_tokens:
                if token.lower() not in [t.lower() for t in query_tokens]:
                    if token.lower() in haystack:
                        score += 2

            # ===== 短语匹配 (最高优先级) =====
            section_text = f"{metadata.get('chapter', '')} {metadata.get('section', '')}".lower()
            title_text = metadata.get("title", "").lower()
            for phrase in phrase_candidates:
                if phrase in section_text:
                    score += 15  # 章节匹配最高
                elif phrase in title_text:
                    score += 12
                elif phrase in haystack:
                    score += 6

            # ===== 条款号精确匹配 =====
            import re
            clause_numbers = re.findall(r'\d+\.\d+', query)
            item_text = item.get("text", "")
            for cn in clause_numbers:
                if cn in item_text[:200]:  # 在开头找到
                    score += 10
                elif cn in haystack:
                    score += 5

            # ===== 权威来源加成 =====
            score += get_authority_score(metadata)

            # ===== 意图加成 =====
            text_lower = item.get("text", "").lower()

            # 法规意图
            if intent_scores.get("regulatory", 0) > 0.4:
                if any(m in text_lower for m in ["要求", "规定", "必须", "应当", "shall", "must", "require", "compliance"]):
                    score += 6.0

            # 方法意图
            if intent_scores.get("method", 0) > 0.4:
                if any(m in text_lower for m in ["步骤", "流程", "方法", "step", "procedure", "检测", "验证"]):
                    score += 5.0

            # 比较意图
            if intent_scores.get("comparison", 0) > 0.4:
                if any(m in text_lower for m in ["比较", "差异", "compare", "versus", "vs", "区别"]):
                    score += 5.0

            # 定义意图
            if intent_scores.get("definition", 0) > 0.4:
                if any(m in text_lower for m in ["定义", "概念", "包括", "definition", "means", "include"]):
                    score += 4.0

            # 数值意图
            if intent_scores.get("numerical", 0) > 0.4:
                if re.search(r'\d+[\.\d]*\s*(°C|MPa|kg|rpm|kN|Nm|℃|帕|兆帕)', text_lower):
                    score += 5.0
                if any(m in text_lower for m in ["最小", "最大", "极限", "minimum", "maximum", "limit"]):
                    score += 3.0

            # ===== 结构位置加权 =====
            if phrase_candidates and any(p in title_text for p in phrase_candidates):
                score += 8.0
            if any(p in item.get("text", "")[:150].lower() for p in phrase_candidates):
                score += 4.0

            # ===== 条款标题精确匹配奖励 =====
            title_match_count = sum(1 for t in query_tokens if t in title_text)
            if title_match_count >= len(query_tokens) * 0.6:
                score += 10.0  # 60%以上token在标题中

            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        positive = [item for score, item in scored if score > 0]
        return positive[:top_k] if positive else [item for _, item in scored[:top_k]]


if __name__ == "__main__":
    from semantic_chunker import StructuralChunker

    chunker = StructuralChunker(processed_dir="../../data/processed")
    chunks = chunker.chunk_markdown("CCAR-33.md")

    engine = VectorStoreEngine(db_dir="../../data/processed/chroma_db")
    engine.index_chunks(chunks)

    results = engine.search("压气机的喘振裕度要求是什么？")
    print("\n--- Search Results for '压气机的喘振裕度要求是什么？' ---")
    for item in results:
        print(f"Source: {item['metadata']}")
        print(f"Content Outline: {item['text'][:100]}...\n")

def collect_indexable_chunks() -> list:
    """
    Collect all indexable chunks from processed data sources.

    Priority (highest wins, no duplicate source):
      1. Pre-processed ``*_chunks.json`` files in PROCESSED_DATA_DIR
         (fine-grained AC chunks produced by the ingestion pipeline)
      2. Structural re-chunking of ``*.md`` files that have NO pre-processed JSON
      3. EASA CS-E chunks from ``easa_cse/chunks_full.json``

    This ensures AC documents like AC_33.87-1A (142 pre-processed chunks)
    are indexed at full granularity rather than as a single monolithic blob.
    """
    import json
    import logging
    from typing import Any
    from src.settings import PROCESSED_DATA_DIR
    from src.rag.semantic_chunker import StructuralChunker
    logger = logging.getLogger(__name__)

    chunks: list[dict[str, Any]] = []
    # Track which source stems have already been loaded via JSON to avoid duplicates
    json_loaded_sources: set[str] = set()

    # ── Step 1: load pre-processed *_chunks.json files ────────────────────────
    for chunks_file in sorted(PROCESSED_DATA_DIR.glob("*_chunks.json")):
        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                pre_chunks = json.load(f)
            if not pre_chunks:
                continue
            for item in pre_chunks:
                chunks.append({
                    "text": item.get("text", ""),
                    "metadata": item.get("metadata", {}),
                })
            # Derive the stem name used to match markdown files (e.g. "AC_33.87-1A_Endurance_Test")
            stem = chunks_file.stem.replace("_chunks", "")
            json_loaded_sources.add(stem)
            logger.info("Loaded %d pre-processed chunks from %s", len(pre_chunks), chunks_file.name)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", chunks_file.name, exc)

    # ── Step 2: structural chunking for markdown files NOT covered by JSON ────
    chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))
    for markdown_file in sorted(PROCESSED_DATA_DIR.glob("*.md")):
        if markdown_file.name.endswith("_analysis_report.md"):
            continue
        # Skip if a pre-processed JSON already covers this source.
        # Match both exact stem ("AC_33.87-1A_Endurance_Test") and prefix-extended stems
        # ("FAR-33_Full" is covered by json_loaded_source "FAR-33").
        stem = markdown_file.stem
        if stem in json_loaded_sources or any(stem.startswith(s) for s in json_loaded_sources):
            logger.debug("Skipping %s — already loaded from *_chunks.json", markdown_file.name)
            continue
        md_chunks = chunker.chunk_markdown(markdown_file.name)
        chunks.extend(md_chunks)
        logger.info("Structural chunking %s → %d chunks", markdown_file.name, len(md_chunks))

    # ── Step 3: EASA CS-E chunks ──────────────────────────────────────────────
    easa_chunks_path = PROCESSED_DATA_DIR / "easa_cse" / "chunks_full.json"
    if easa_chunks_path.exists():
        with open(easa_chunks_path, "r", encoding="utf-8") as f:
            easa_data = json.load(f)
        for item in easa_data:
            chunks.append({
                "text": item.get("text", ""),
                "metadata": item.get("metadata", {}),
            })
        logger.info("Loaded %d EASA CS-E chunks from JSON", len(easa_data))

    # ── Step 4: Aviation terminology definitions (v0.7) ──────────────────────
    defs_path = PROCESSED_DATA_DIR / "aviation_definitions_chunks.json"
    if defs_path.exists():
        try:
            with open(defs_path, "r", encoding="utf-8") as f:
                defs_data = json.load(f)
            for item in defs_data:
                chunks.append({
                    "text": item.get("text", ""),
                    "metadata": item.get("metadata", {}),
                })
            logger.info("Loaded %d aviation definition chunks from %s", len(defs_data), defs_path.name)
        except Exception as exc:
            logger.warning("Failed to load aviation_definitions_chunks.json: %s", exc)

    logger.info("collect_indexable_chunks: %d total chunks from %d JSON-sources + markdown fallback",
                len(chunks), len(json_loaded_sources))
    return chunks
