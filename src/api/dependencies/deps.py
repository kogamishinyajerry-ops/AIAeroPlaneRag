"""
API Dependencies - 依赖注入
提供全局服务的单例访问
"""
import os
import logging
from typing import Optional, Dict, Any

from src.settings import CHROMA_DB_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

def has_real_value(value: Optional[str]) -> bool:
    """检查环境变量是否有真实值"""
    if not value:
        return False
    return not any(
        placeholder in value.lower()
        for placeholder in ["your_", "placeholder", "xxx", "example", "password"]
    )

class ServiceContainer:
    """
    服务容器 - 替代主模块的 19+ 全局变量。
    支持懒加载或启动时通过 initialize() 方法 eager 初始化。
    """
    def __init__(self):
        # Engines and Stores
        self._vector_engine = None
        self._pageindex_engine = None
        self._graph_store = None
        
        # Catalogs
        self._source_catalog = None
        self._enhanced_kb = None
        
        # Agents & Guards
        self._guardrail = None
        self._metadata_extractor = None
        self._hallucination_guard = None
        self._hallucination_reducer = None
        self._safe_answer_builder = None
        self._enhanced_safe_answer_builder = None
        
        # Re-rankers & Enhancers
        self._relevance_enhancer = None
        self._reranker = None
        self._knowledge_linker = None
        self._fact_verifier = None
        self._usability_enhancer = None
        self._quality_scorer = None
        self._enhanced_answer_generator = None
        self._terminology_agent = None  # Original property
        
        # LLM Clients
        self._glm_client = None
        
        self.service_errors: Dict[str, str] = {}
        self.is_initialized: bool = False

    def initialize(self):
        """Eager initialization procedure matching original main.py initialization"""
        if self.is_initialized:
            return
            
        self.service_errors.clear()

        try:
            from src.rag.vector_engine import VectorStoreEngine
            self._vector_engine = VectorStoreEngine(db_dir=str(CHROMA_DB_DIR))
        except Exception as exc:
            self.service_errors["vector_db"] = str(exc)
            
        try:
            from src.rag.pageindex_engine import PageIndexEngine
            self._pageindex_engine = PageIndexEngine(str(PROCESSED_DATA_DIR / "CCAR-33-R2_structure.json"))
        except Exception as exc:
            self.service_errors["pageindex"] = str(exc)
            
        try:
            from src.ontology.graph_store import OntologyGraphStore
            self._graph_store = OntologyGraphStore()
        except Exception as exc:
             self.service_errors["graph_db"] = str(exc)

        try:
            from src.rag.guardrail import FactCheckingGuardrail
            self._guardrail = FactCheckingGuardrail()
        except Exception as exc:
            self.service_errors["guardrail"] = str(exc)

        try:
            from src.knowledge_base.source_catalog import KnowledgeSourceCatalog
            self._source_catalog = KnowledgeSourceCatalog.load()
        except Exception as exc:
            from src.knowledge_base.source_catalog import KnowledgeSourceCatalog
            self._source_catalog = KnowledgeSourceCatalog()
            self.service_errors["source_catalog"] = str(exc)

        try:
            from src.knowledge_base.enhanced_multi_ccar import EnhancedMultiCCARKB
            self._enhanced_kb = EnhancedMultiCCARKB(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["enhanced_kb"] = str(exc)

        try:
            from src.multi_agent.metadata_enhancer_agent import EnhancedMetadataExtractor
            self._metadata_extractor = EnhancedMetadataExtractor(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["metadata_extractor"] = str(exc)

        try:
            from src.rag.hallucination_guard import HallucinationGuard
            self._hallucination_guard = HallucinationGuard(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["hallucination_guard"] = str(exc)

        try:
            from src.rag.relevance_enhancer import QueryRelevanceEnhancer, ReRanker
            self._relevance_enhancer = QueryRelevanceEnhancer(str(PROCESSED_DATA_DIR))
            self._reranker = ReRanker(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["relevance_enhancer"] = str(exc)

        try:
            from src.multi_agent.knowledge_linker_agent import KnowledgeLinkerAgent
            self._knowledge_linker = KnowledgeLinkerAgent(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["knowledge_linker"] = str(exc)

        try:
            from src.multi_agent.fact_verification_agent import FactVerificationAgent
            self._fact_verifier = FactVerificationAgent(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["fact_verifier"] = str(exc)

        try:
            from src.multi_agent.usability_enhancer_agent import UsabilityEnhancerAgent
            self._usability_enhancer = UsabilityEnhancerAgent(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["usability_enhancer"] = str(exc)

        try:
            from src.scoring.quality_enhancer import QualityScoringEngine
            self._quality_scorer = QualityScoringEngine(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["quality_scorer"] = str(exc)

        try:
            from src.rag.enhanced_answer_generator import EnhancedAnswerGenerator
            self._enhanced_answer_generator = EnhancedAnswerGenerator(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["enhanced_answer_generator"] = str(exc)
            
        try:
            from src.rag.hallucination_reducer import HallucinationReducer
            self._hallucination_reducer = HallucinationReducer(str(PROCESSED_DATA_DIR))
        except Exception as exc:
            self.service_errors["hallucination_reducer"] = str(exc)

        try:
            from src.rag.safe_answer_builder import SafeAnswerBuilder
            self._safe_answer_builder = SafeAnswerBuilder()
        except Exception as exc:
             self.service_errors["safe_answer_builder"] = str(exc)

        try:
            from src.rag.enhanced_safe_builder import EnhancedSafeAnswerBuilder
            self._enhanced_safe_answer_builder = EnhancedSafeAnswerBuilder(str(PROCESSED_DATA_DIR))
        except Exception as exc:
             self.service_errors["enhanced_safe_answer_builder"] = str(exc)

        try:
            from src.multi_agent.enhanced_terminology_agent import EnhancedTerminologyAgent
            self._terminology_agent = EnhancedTerminologyAgent()
        except Exception as exc:
             self.service_errors["terminology_agent"] = str(exc)

        try:
            import openai
            minimax_key = os.getenv("MINIMAX_API_KEY")
            zhipu_key = os.getenv("ZHIPU_API_KEY")
            if minimax_key and has_real_value(minimax_key):
                self._glm_client = openai.OpenAI(
                    api_key=minimax_key,
                    base_url="https://api.minimax.chat/v1"
                )
            elif zhipu_key and has_real_value(zhipu_key):
                self._glm_client = openai.OpenAI(
                    api_key=zhipu_key,
                    base_url="https://open.bigmodel.cn/api/paas/v4/"
                )
        except ImportError:
            pass

        self.is_initialized = True

    # ---------- LAZY EVALUATION PROPERTIES (For safety and Testing) ----------

    @property
    def vector_engine(self):
         if self._vector_engine is None and not self.is_initialized:
             from src.rag.vector_engine import VectorStoreEngine
             self._vector_engine = VectorStoreEngine(db_dir=str(CHROMA_DB_DIR))
         return self._vector_engine

    @property
    def pageindex_engine(self):
        if self._pageindex_engine is None and not self.is_initialized:
            from src.rag.pageindex_engine import PageIndexEngine
            self._pageindex_engine = PageIndexEngine(str(PROCESSED_DATA_DIR / "CCAR-33-R2_structure.json"))
        return self._pageindex_engine

    @property
    def graph_store(self):
        if self._graph_store is None and not self.is_initialized:
            from src.ontology.graph_store import OntologyGraphStore
            self._graph_store = OntologyGraphStore()
        return self._graph_store

    @property
    def enhanced_kb(self):
        if self._enhanced_kb is None and not self.is_initialized:
             try:
                 from src.knowledge_base.enhanced_multi_ccar import EnhancedMultiCCARKB
                 self._enhanced_kb = EnhancedMultiCCARKB(str(PROCESSED_DATA_DIR))
             except ImportError:
                 pass
        return self._enhanced_kb

    @property
    def metadata_extractor(self):
         if self._metadata_extractor is None and not self.is_initialized:
             from src.multi_agent.metadata_enhancer_agent import EnhancedMetadataExtractor
             self._metadata_extractor = EnhancedMetadataExtractor(str(PROCESSED_DATA_DIR))
         return self._metadata_extractor

    @property
    def hallucination_guard(self):
         if self._hallucination_guard is None and not self.is_initialized:
             from src.rag.hallucination_guard import HallucinationGuard
             self._hallucination_guard = HallucinationGuard(str(PROCESSED_DATA_DIR))
         return self._hallucination_guard

    @property
    def quality_scorer(self):
         if self._quality_scorer is None and not self.is_initialized:
             from src.scoring.quality_enhancer import QualityScoringEngine
             self._quality_scorer = QualityScoringEngine(str(PROCESSED_DATA_DIR))
         return self._quality_scorer

    @property
    def terminology_agent(self):
         if self._terminology_agent is None and not self.is_initialized:
             from src.multi_agent.enhanced_terminology_agent import EnhancedTerminologyAgent
             self._terminology_agent = EnhancedTerminologyAgent()
         return self._terminology_agent

    @property
    def guardrail(self):
         if self._guardrail is None and not self.is_initialized:
             from src.rag.guardrail import FactCheckingGuardrail
             self._guardrail = FactCheckingGuardrail()
         return self._guardrail

    @property
    def glm_client(self):
         return self._glm_client

    @property
    def source_catalog(self):
         return self._source_catalog

    @property
    def reranker(self):
        if self._reranker is None and not self.is_initialized:
             from src.rag.relevance_enhancer import ReRanker
             self._reranker = ReRanker(str(PROCESSED_DATA_DIR))
        return self._reranker

    @property
    def relevance_enhancer(self):
        if self._relevance_enhancer is None and not self.is_initialized:
             from src.rag.relevance_enhancer import QueryRelevanceEnhancer
             self._relevance_enhancer = QueryRelevanceEnhancer(str(PROCESSED_DATA_DIR))
        return self._relevance_enhancer

    @property
    def knowledge_linker(self):
        if self._knowledge_linker is None and not self.is_initialized:
             from src.multi_agent.knowledge_linker_agent import KnowledgeLinkerAgent
             self._knowledge_linker = KnowledgeLinkerAgent(str(PROCESSED_DATA_DIR))
        return self._knowledge_linker

    @property
    def fact_verifier(self):
        if self._fact_verifier is None and not self.is_initialized:
             from src.multi_agent.fact_verification_agent import FactVerificationAgent
             self._fact_verifier = FactVerificationAgent(str(PROCESSED_DATA_DIR))
        return self._fact_verifier

    @property
    def usability_enhancer(self):
        if self._usability_enhancer is None and not self.is_initialized:
             from src.multi_agent.usability_enhancer_agent import UsabilityEnhancerAgent
             self._usability_enhancer = UsabilityEnhancerAgent(str(PROCESSED_DATA_DIR))
        return self._usability_enhancer

    @property
    def enhanced_answer_generator(self):
        if self._enhanced_answer_generator is None and not self.is_initialized:
             from src.rag.enhanced_answer_generator import EnhancedAnswerGenerator
             self._enhanced_answer_generator = EnhancedAnswerGenerator(str(PROCESSED_DATA_DIR))
        return self._enhanced_answer_generator

    @property
    def hallucination_reducer(self):
        if self._hallucination_reducer is None and not self.is_initialized:
             from src.rag.hallucination_reducer import HallucinationReducer
             self._hallucination_reducer = HallucinationReducer(str(PROCESSED_DATA_DIR))
        return self._hallucination_reducer

    @property
    def safe_answer_builder(self):
        if self._safe_answer_builder is None and not self.is_initialized:
             from src.rag.safe_answer_builder import SafeAnswerBuilder
             self._safe_answer_builder = SafeAnswerBuilder()
        return self._safe_answer_builder

    @property
    def enhanced_safe_answer_builder(self):
        if self._enhanced_safe_answer_builder is None and not self.is_initialized:
             from src.rag.enhanced_safe_builder import EnhancedSafeAnswerBuilder
             self._enhanced_safe_answer_builder = EnhancedSafeAnswerBuilder(str(PROCESSED_DATA_DIR))
        return self._enhanced_safe_answer_builder

    def reset(self):
        """重置所有服务（用于测试或重新初始化）"""
        self.__init__()



# 全局服务容器实例
services = ServiceContainer()

# === FastAPI 依赖注入函数 ===

def get_vector_engine():
    return services.vector_engine

def get_pageindex_engine():
    return services.pageindex_engine

def get_enhanced_kb():
    return services.enhanced_kb

def get_glm_client():
    return services.glm_client

def get_quality_scorer():
    return services.quality_scorer

def get_hallucination_guard():
    return services.hallucination_guard

def get_metadata_extractor():
    return services.metadata_extractor

def get_guardrail():
    return services.guardrail
