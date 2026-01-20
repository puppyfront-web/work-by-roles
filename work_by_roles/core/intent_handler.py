"""
Unified Intent Handler - Entry point for user input processing.
This module provides a unified interface for handling user intents without relying on Cursor configuration files.
"""

from typing import Dict, Optional, Any
from .workflow_engine import WorkflowEngine
from .intent_agent import IntentAgent
from .bug_analysis_agent import BugAnalysisAgent
from .enums import IntentType
from .agent_orchestrator import AgentOrchestrator


class IntentHandler:
    """
    统一的意图处理入口：处理用户输入并路由到相应的处理流程
    
    这是系统的统一入口，不再依赖`.cursorrules`等配置文件。
    所有用户输入都通过这个类进行处理。
    """
    
    def __init__(self, engine: 'WorkflowEngine', llm_client: Optional[Any] = None):
        """
        初始化IntentHandler
        
        Args:
            engine: WorkflowEngine实例
            llm_client: 可选的LLM客户端
        """
        self.engine = engine
        self.intent_agent = IntentAgent(engine, llm_client)
        self.bug_agent = BugAnalysisAgent(engine, llm_client)
        self.orchestrator = AgentOrchestrator(engine, llm_client) if engine else None
    
    def handle(self, user_input: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        处理用户输入的统一入口
        
        Args:
            user_input: 用户输入的自然语言描述
            use_llm: 是否使用LLM（None=自动选择）
        
        Returns:
            处理结果，包含意图识别结果和路由建议
        """
        # 1. 识别用户意图
        intent_result = self.intent_agent.recognize_intent(user_input, use_llm)
        
        # 2. 根据意图类型路由
        routing_result = self.intent_agent.route(intent_result)
        
        # 3. 根据路由结果执行相应操作
        execution_result = self._execute_routing(user_input, intent_result, routing_result)
        
        return {
            "intent": intent_result,
            "routing": routing_result,
            "execution": execution_result
        }
    
    def _execute_routing(
        self, 
        user_input: str, 
        intent_result: Dict[str, Any], 
        routing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """根据路由结果执行相应操作"""
        action = routing_result.get("action")
        intent_type = intent_result.get("intent_type")
        
        if action == "execute_workflow":
            # 需求实现：执行标准工作流
            return self._execute_feature_workflow(user_input, routing_result)
        elif action == "analyze_and_assign":
            # Bug修复：分析并分配
            return self._execute_bug_fix(user_input, routing_result)
        elif action == "answer_query":
            # 查询：直接回答
            return {
                "action": "answer_query",
                "message": "这是一个查询请求，需要进一步处理"
            }
        else:
            # 未知意图：需要澄清
            return {
                "action": "clarify",
                "message": "无法确定您的意图，请提供更多信息"
            }
    
    def _execute_feature_workflow(
        self, 
        user_input: str, 
        routing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行需求实现的标准工作流"""
        stages = routing_result.get("stages", [])
        
        if not self.engine.workflow:
            return {
                "success": False,
                "error": "工作流未加载"
            }
        
        # 如果没有指定阶段，执行完整工作流
        if not stages:
            stages = [stage.id for stage in self.engine.workflow.stages]
        
        return {
            "action": "execute_workflow",
            "workflow_type": "standard",
            "stages": stages,
            "message": f"将执行标准工作流，包含{len(stages)}个阶段",
            "next_step": "调用workflow执行器开始执行"
        }
    
    def _execute_bug_fix(
        self, 
        user_input: str, 
        routing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行bug修复流程"""
        # 分析bug
        analysis_result = self.bug_agent.analyze_bug(user_input)
        
        # 分配bug
        assignment_result = self.bug_agent.assign_bug(user_input, analysis_result)
        
        return {
            "action": "analyze_and_assign",
            "workflow_type": "bug_fix",
            "analysis": analysis_result,
            "assignment": assignment_result,
            "message": f"Bug已分析并分配给角色：{assignment_result.get('assigned_role', 'unknown')}"
        }


def handle_user_input(
    engine: 'WorkflowEngine', 
    user_input: str, 
    llm_client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    统一的用户输入处理函数（便捷接口）
    
    这是系统的统一入口点，替代依赖`.cursorrules`的方式。
    
    Args:
        engine: WorkflowEngine实例
        user_input: 用户输入
        llm_client: 可选的LLM客户端
    
    Returns:
        处理结果
    
    Example:
        >>> from work_by_roles.core import WorkflowEngine, handle_user_input
        >>> engine = WorkflowEngine(workspace_path=".")
        >>> result = handle_user_input(engine, "实现用户登录功能")
        >>> print(result["intent"]["intent_type"])  # IntentType.FEATURE_REQUEST
    """
    handler = IntentHandler(engine, llm_client)
    return handler.handle(user_input)
