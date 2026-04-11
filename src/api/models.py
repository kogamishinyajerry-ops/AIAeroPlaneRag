from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ConfidenceDimension(BaseModel):
    """单个置信度维度得分"""
    name: str
    label: str
    score: float
    weight: float
    weighted: float
    detail: str


class ConfidenceDetail(BaseModel):
    """7 维度置信度完整结果"""
    summary: float                              # 综合置信度 0-1
    query_type: str                             # 查询类型
    dimensions: Dict[str, ConfidenceDimension]  # 7 维度详细得分
    explanation: str                            # 人类可读说明
    uncertainty_markers: List[str]              # 改进建议

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    use_guardrail: bool = True
    include_graph_subgraph: bool = False
    use_pageindex: bool = False



class Citation(BaseModel):
    num: int
    source: str
    chapter: str
    section: str
    snippet: str
    highlight: str
    fullText: Optional[str] = None
    documentId: Optional[str] = None
    documentVersion: Optional[str] = None
    contentMode: Optional[str] = None
    sourcePath: Optional[str] = None



class GraphInsight(BaseModel):
    regulation: Optional[str] = None
    component: Optional[str] = None
    parameter: Optional[str] = None
    relationship: Optional[str] = None
    description: Optional[str] = None



class QueryResponse(BaseModel):
    query: str
    answer: str
    guardrail: Dict[str, Any]
    citations: List[Citation]
    graphInsights: List[GraphInsight]
    graphSubgraph: Optional[Dict[str, Any]] = None
    responseMode: str
    appVersion: str
    knowledgeBaseVersion: str
    promptVersion: str
    embeddingVersion: str
    graphVersion: str
    retrievalCount: int
    # 新增字段 - 性能优化
    confidenceScore: Optional[float] = None  # 答案置信度 (0-1)，与 confidenceDetail.summary 等价
    confidenceDetail: Optional[ConfidenceDetail] = None  # 7 维度置信度详情
    uncertaintyMarkers: List[str] = []  # 不确定陈述标记
    relatedClauses: List[Dict[str, str]] = []  # 相关条款
    visualizationData: Optional[Dict[str, Any]] = None  # 可视化数据
    # 新增字段 - 知识图谱
    knowledgeGraphNodes: List[Dict[str, Any]] = []  # 知识图谱相关节点
    semanticRelations: List[Dict[str, Any]] = []  # 语义关系
    # 新增字段 - 质量评分
    qualityMetrics: Optional[Dict[str, Any]] = None  # 完整的质量指标
    # 新增字段 - LLM思考过程
    thinkingProcess: Optional[str] = None  # LLM的思考过程
    reasoningSteps: List[str] = []  # 推理步骤
    llmProvider: Optional[str] = None  # LLM提供商 (mock/glm/minimax)
    llmModel: Optional[str] = None  # 使用的模型名称



