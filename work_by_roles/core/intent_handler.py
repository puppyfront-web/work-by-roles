"""
Unified Intent Handler - Entry point for user input processing.
This module provides a unified interface for handling user intents without relying on Cursor configuration files.

Enhanced with session management for multi-turn conversations.
"""

from typing import Dict, Optional, Any, List
from pathlib import Path
import json
from datetime import datetime

from .workflow_engine import WorkflowEngine
from .intent_agent import IntentAgent
from .bug_analysis_agent import BugAnalysisAgent
from .enums import IntentType
from .agent_orchestrator import AgentOrchestrator
from .dialog_manager import DialogManager, DialogState


class SessionStore:
    """
    Manages session persistence for multi-turn conversations.
    
    Sessions can be stored in memory or persisted to disk.
    """
    
    def __init__(self, persist_dir: Optional[Path] = None):
        """
        Initialize session store.
        
        Args:
            persist_dir: Optional directory for persisting sessions
        """
        self.sessions: Dict[str, DialogManager] = {}
        self.persist_dir = persist_dir
        
        if persist_dir:
            persist_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, session_id: str) -> Optional[DialogManager]:
        """Get a session by ID"""
        # Check in-memory cache first
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try to load from disk
        if self.persist_dir:
            session_file = self.persist_dir / f"{session_id}.json"
            if session_file.exists():
                try:
                    data = json.loads(session_file.read_text(encoding='utf-8'))
                    dialog_manager = DialogManager.from_dict(data)
                    self.sessions[session_id] = dialog_manager
                    return dialog_manager
                except Exception:
                    pass
        
        return None
    
    def save(self, dialog_manager: DialogManager):
        """Save a session"""
        session_id = dialog_manager.session_id
        self.sessions[session_id] = dialog_manager
        
        # Persist to disk if configured
        if self.persist_dir:
            session_file = self.persist_dir / f"{session_id}.json"
            try:
                session_file.write_text(
                    json.dumps(dialog_manager.to_dict(), ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
            except Exception:
                pass
    
    def delete(self, session_id: str):
        """Delete a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        if self.persist_dir:
            session_file = self.persist_dir / f"{session_id}.json"
            if session_file.exists():
                try:
                    session_file.unlink()
                except Exception:
                    pass
    
    def list_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all sessions"""
        sessions = []
        
        # Get from in-memory cache
        for sid, dm in self.sessions.items():
            sessions.append({
                "session_id": sid,
                "state": dm.state.value,
                "created_at": dm.created_at.isoformat(),
                "last_activity": dm.last_activity.isoformat(),
                "turns": len(dm.history)
            })
        
        # Get from disk if configured
        if self.persist_dir:
            for session_file in self.persist_dir.glob("session_*.json"):
                sid = session_file.stem
                if sid not in self.sessions:
                    try:
                        data = json.loads(session_file.read_text(encoding='utf-8'))
                        sessions.append({
                            "session_id": sid,
                            "state": data.get("state", "unknown"),
                            "created_at": data.get("created_at", ""),
                            "last_activity": data.get("last_activity", ""),
                            "turns": len(data.get("history", []))
                        })
                    except Exception:
                        pass
        
        # Sort by last activity
        sessions.sort(key=lambda x: x.get("last_activity", ""), reverse=True)
        return sessions[:limit]
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove sessions older than max_age_hours"""
        now = datetime.now()
        to_delete = []
        
        for sid, dm in list(self.sessions.items()):
            age = (now - dm.last_activity).total_seconds() / 3600
            if age > max_age_hours:
                to_delete.append(sid)
        
        for sid in to_delete:
            self.delete(sid)


class IntentHandler:
    """
    统一的意图处理入口：处理用户输入并路由到相应的处理流程
    
    这是系统的统一入口，不再依赖`.cursorrules`等配置文件。
    所有用户输入都通过这个类进行处理。
    
    Enhanced with session management for multi-turn conversations.
    """
    
    def __init__(
        self, 
        engine: 'WorkflowEngine', 
        llm_client: Optional[Any] = None,
        persist_sessions: bool = False
    ):
        """
        初始化IntentHandler
        
        Args:
            engine: WorkflowEngine实例
            llm_client: 可选的LLM客户端
            persist_sessions: 是否持久化会话到磁盘
        """
        self.engine = engine
        self.llm_client = llm_client
        self.intent_agent = IntentAgent(engine, llm_client)
        self.bug_agent = BugAnalysisAgent(engine, llm_client)
        self.orchestrator = AgentOrchestrator(engine, llm_client) if engine else None
        
        # Session management
        persist_dir = None
        if persist_sessions and engine:
            persist_dir = engine.workspace_path / ".workflow" / "sessions"
        self.session_store = SessionStore(persist_dir)
    
    def handle(self, user_input: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        处理用户输入的统一入口（单轮对话）
        
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
    
    # ========================================================================
    # Session-based Multi-turn Dialog Methods
    # ========================================================================
    
    def handle_with_session(
        self, 
        user_input: str, 
        session_id: Optional[str] = None,
        use_llm: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        处理用户输入（支持多轮对话）
        
        This method supports multi-turn conversations with session state management.
        Suitable for non-technical users who may need clarification.
        
        Args:
            user_input: 用户输入
            session_id: 可选的会话ID，不提供则创建新会话
            use_llm: 是否使用LLM
            
        Returns:
            {
                "session_id": str,
                "intent": Dict,
                "needs_clarification": bool,
                "clarification_questions": List[Dict],
                "ready_to_execute": bool,
                "routing": Dict (if ready),
                "execution": Dict (if ready and auto_execute)
            }
        """
        # Get or create session
        dialog_manager = None
        if session_id:
            dialog_manager = self.session_store.get(session_id)
        
        if dialog_manager:
            # Continue existing session
            self.intent_agent.dialog_manager = dialog_manager
        
        # Use interactive recognition
        result = self.intent_agent.interactive_recognize(user_input, session_id, use_llm)
        
        # Save session
        if self.intent_agent.dialog_manager:
            self.session_store.save(self.intent_agent.dialog_manager)
        
        # If ready to execute, add routing info
        if result.get("ready_to_execute"):
            routing_result = self.intent_agent.route(result["intent"])
            result["routing"] = routing_result
        
        return result
    
    def clarify(
        self, 
        session_id: str, 
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        提供对澄清问题的回答
        
        Args:
            session_id: 会话ID
            answers: 问题ID到答案的映射
            
        Returns:
            更新后的处理结果
        """
        # Get session
        dialog_manager = self.session_store.get(session_id)
        if not dialog_manager:
            return {
                "error": f"Session not found: {session_id}",
                "session_id": session_id
            }
        
        # Restore to intent agent
        self.intent_agent.dialog_manager = dialog_manager
        
        # Provide clarification
        result = self.intent_agent.provide_clarification(session_id, answers)
        
        # Save updated session
        self.session_store.save(self.intent_agent.dialog_manager)
        
        # If ready to execute, add routing info
        if result.get("ready_to_execute"):
            routing_result = self.intent_agent.route(result["intent"])
            result["routing"] = routing_result
        
        return result
    
    def confirm_session(self, session_id: str) -> Dict[str, Any]:
        """
        确认会话并准备执行
        
        Args:
            session_id: 会话ID
            
        Returns:
            最终的意图和路由信息
        """
        # Get session
        dialog_manager = self.session_store.get(session_id)
        if not dialog_manager:
            return {
                "error": f"Session not found: {session_id}",
                "session_id": session_id
            }
        
        # Restore to intent agent
        self.intent_agent.dialog_manager = dialog_manager
        
        # Confirm and get final result
        result = self.intent_agent.confirm_and_execute(session_id)
        
        # Save updated session
        self.session_store.save(self.intent_agent.dialog_manager)
        
        return result
    
    def execute_session(
        self, 
        session_id: str, 
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        执行已确认的会话
        
        Args:
            session_id: 会话ID
            auto_execute: 是否自动执行工作流
            
        Returns:
            执行结果
        """
        # Get session
        dialog_manager = self.session_store.get(session_id)
        if not dialog_manager:
            return {
                "error": f"Session not found: {session_id}",
                "session_id": session_id
            }
        
        if dialog_manager.state != DialogState.CONFIRMED:
            return {
                "error": f"Session not confirmed. Current state: {dialog_manager.state.value}",
                "session_id": session_id
            }
        
        # Get final intent and routing
        final_goal = dialog_manager.get_final_goal()
        intent_result = self.intent_agent.recognize_intent(final_goal)
        routing_result = self.intent_agent.route(intent_result)
        
        result = {
            "session_id": session_id,
            "final_goal": final_goal,
            "intent": intent_result,
            "routing": routing_result,
            "context": dialog_manager.context.to_dict()
        }
        
        if auto_execute:
            # Execute the routing
            execution_result = self._execute_routing(final_goal, intent_result, routing_result)
            result["execution"] = execution_result
            
            # Update session state
            dialog_manager.mark_executing()
            self.session_store.save(dialog_manager)
        
        return result
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话状态信息
        """
        dialog_manager = self.session_store.get(session_id)
        if not dialog_manager:
            return {
                "error": f"Session not found: {session_id}",
                "session_id": session_id
            }
        
        return {
            "session_id": session_id,
            "state": dialog_manager.state.value,
            "turns": len(dialog_manager.history),
            "pending_questions": len(dialog_manager.get_pending_questions()),
            "clarification_round": dialog_manager.clarification_round,
            "confidence": dialog_manager.context.confidence_score,
            "original_goal": dialog_manager.context.original_goal,
            "refined_goal": dialog_manager.context.refined_goal,
            "ready_to_execute": dialog_manager.is_ready_to_execute(),
            "created_at": dialog_manager.created_at.isoformat(),
            "last_activity": dialog_manager.last_activity.isoformat()
        }
    
    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Args:
            limit: 最大返回数量
            
        Returns:
            会话列表
        """
        return self.session_store.list_sessions(limit)
    
    def close_session(self, session_id: str) -> Dict[str, Any]:
        """
        关闭并清理会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        dialog_manager = self.session_store.get(session_id)
        if dialog_manager:
            dialog_manager.mark_cancelled()
        
        self.session_store.delete(session_id)
        self.intent_agent.clear_session(session_id)
        
        return {
            "session_id": session_id,
            "closed": True
        }
    
    def cleanup_sessions(self, max_age_hours: int = 24):
        """
        清理过期会话
        
        Args:
            max_age_hours: 会话最大保留时间（小时）
        """
        self.session_store.cleanup_old_sessions(max_age_hours)
    
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
