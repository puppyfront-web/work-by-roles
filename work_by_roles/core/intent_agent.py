"""
Intent Agent for unified user intent recognition and routing.
Following Single Responsibility Principle - handles intent recognition and routing only.

Enhanced with multi-turn dialog support and ambiguity detection for non-technical users.
"""

from typing import Dict, List, Optional, Any, Tuple
import json
import re

from .exceptions import WorkflowError
from .enums import IntentType
from .workflow_engine import WorkflowEngine
from .intent_router import IntentRouter
from .dialog_manager import (
    DialogManager, 
    DialogTurn, 
    AmbiguityType, 
    ClarificationQuestion,
    DialogState
)


class IntentAgent:
    """
    统一的意图识别Agent：识别用户输入是需求实现还是bug修复
    
    核心功能：
    1. 识别用户意图类型（需求实现 vs bug修复）
    2. 根据意图类型路由到不同的处理流程
    3. 移除对Cursor配置文件的依赖，在代码层面实现统一入口
    """
    
    def __init__(self, engine: 'WorkflowEngine', llm_client: Optional[Any] = None):
        """
        初始化IntentAgent
        
        Args:
            engine: WorkflowEngine实例
            llm_client: 可选的LLM客户端，用于智能意图识别
        """
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
        self.intent_router = IntentRouter(engine, llm_client)
        self.dialog_manager: Optional[DialogManager] = None
    
    # ========================================================================
    # Interactive Multi-turn Dialog Methods
    # ========================================================================
    
    def interactive_recognize(
        self, 
        user_input: str, 
        session_id: Optional[str] = None,
        use_llm: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Interactive intent recognition with multi-turn dialog support.
        
        This method supports clarification through multiple conversation turns,
        making it suitable for non-technical users who may provide vague requirements.
        
        Args:
            user_input: User's message
            session_id: Optional session ID to continue a conversation
            use_llm: Whether to use LLM (None=auto, True=force, False=disable)
            
        Returns:
            {
                "session_id": str,
                "intent": Dict,
                "needs_clarification": bool,
                "clarification_questions": List[Dict],
                "context_summary": str,
                "ready_to_execute": bool,
                "final_goal": str (if ready)
            }
        """
        # Initialize or restore dialog manager
        if session_id and self.dialog_manager and self.dialog_manager.session_id == session_id:
            # Continue existing session
            pass
        else:
            # Start new session
            self.dialog_manager = DialogManager(session_id)
        
        # Add user turn
        intent_result = self.recognize_intent(user_input, use_llm)
        self.dialog_manager.add_user_turn(user_input, intent_result)
        
        # Detect ambiguities
        ambiguities = self.detect_ambiguities(user_input, intent_result)
        
        # Generate clarification questions if needed
        clarification_questions = []
        if ambiguities and self.dialog_manager.needs_clarification(intent_result):
            questions = self.generate_clarification_questions(ambiguities, user_input)
            for q_text, amb_type in questions:
                q = self.dialog_manager.add_clarification_question(
                    question=q_text,
                    ambiguity_type=amb_type
                )
                clarification_questions.append(q.to_dict())
            
            # Add system turn with questions
            self.dialog_manager.add_system_turn(
                content="需要澄清一些细节以更好地理解您的需求",
                clarifications=[q["question"] for q in clarification_questions]
            )
        
        # Update context confidence
        self.dialog_manager.update_context({
            "confidence": intent_result.get("confidence", 0.5)
        })
        
        # Check if ready to execute
        ready = self.dialog_manager.is_ready_to_execute()
        
        result = {
            "session_id": self.dialog_manager.session_id,
            "intent": intent_result,
            "needs_clarification": len(clarification_questions) > 0,
            "clarification_questions": clarification_questions,
            "context_summary": self.dialog_manager.get_context_summary(),
            "dialog_state": self.dialog_manager.state.value,
            "ready_to_execute": ready
        }
        
        if ready:
            result["final_goal"] = self.dialog_manager.get_final_goal()
        
        return result
    
    def provide_clarification(
        self, 
        session_id: str, 
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Provide answers to clarification questions.
        
        Args:
            session_id: Session ID
            answers: Dictionary mapping question IDs to answers
            
        Returns:
            Updated recognition result
        """
        if not self.dialog_manager or self.dialog_manager.session_id != session_id:
            raise WorkflowError(f"Session not found: {session_id}")
        
        # Record answers
        answered = self.dialog_manager.answer_all_pending(answers)
        
        # Build refined goal from answers
        refined_goal = self._refine_goal_from_answers(answers)
        if refined_goal:
            self.dialog_manager.update_context({"refined_goal": refined_goal})
        
        # Start new clarification round - move this AFTER goal refinement
        self.dialog_manager.start_clarification_round()
        
        # Re-recognize with additional context
        combined_input = self._build_combined_input()
        intent_result = self.recognize_intent(combined_input)
        
        # Update confidence based on clarifications
        new_confidence = min(1.0, intent_result.get("confidence", 0.5) + 0.1 * answered)
        self.dialog_manager.update_context({"confidence": new_confidence})
        intent_result["confidence"] = new_confidence
        
        # Check for remaining ambiguities
        remaining_ambiguities = self.detect_ambiguities(combined_input, intent_result)
        new_questions = []
        
        if remaining_ambiguities and self.dialog_manager.needs_clarification(intent_result):
            questions = self.generate_clarification_questions(remaining_ambiguities, combined_input)
            for q_text, amb_type in questions:
                q = self.dialog_manager.add_clarification_question(
                    question=q_text,
                    ambiguity_type=amb_type
                )
                new_questions.append(q.to_dict())
        
        ready = self.dialog_manager.is_ready_to_execute()
        
        result = {
            "session_id": session_id,
            "intent": intent_result,
            "answers_recorded": answered,
            "needs_clarification": len(new_questions) > 0,
            "clarification_questions": new_questions,
            "context_summary": self.dialog_manager.get_context_summary(),
            "dialog_state": self.dialog_manager.state.value,
            "ready_to_execute": ready
        }
        
        if ready:
            result["final_goal"] = self.dialog_manager.get_final_goal()
        
        return result
    
    def confirm_and_execute(self, session_id: str) -> Dict[str, Any]:
        """
        Confirm understanding and prepare for execution.
        
        Args:
            session_id: Session ID
            
        Returns:
            Final intent and routing information
        """
        if not self.dialog_manager or self.dialog_manager.session_id != session_id:
            raise WorkflowError(f"Session not found: {session_id}")
        
        self.dialog_manager.mark_confirmed()
        
        final_goal = self.dialog_manager.get_final_goal()
        final_intent = self.recognize_intent(final_goal)
        routing = self.route(final_intent)
        
        return {
            "session_id": session_id,
            "confirmed": True,
            "final_goal": final_goal,
            "intent": final_intent,
            "routing": routing,
            "context": self.dialog_manager.context.to_dict()
        }
    
    def detect_ambiguities(
        self, 
        user_input: str, 
        intent_result: Dict[str, Any]
    ) -> List[Tuple[AmbiguityType, str]]:
        """
        Detect ambiguities in user input that need clarification.
        
        Args:
            user_input: User's input text
            intent_result: Intent recognition result
            
        Returns:
            List of (AmbiguityType, description) tuples
        """
        ambiguities = []
        input_lower = user_input.lower()
        confidence = intent_result.get("confidence", 0.5)
        
        # 1. Check for missing scope
        scope_indicators = ["系统", "模块", "功能", "页面", "服务", "组件", "system", "module", "feature", "page"]
        has_scope = any(ind in input_lower for ind in scope_indicators)
        if not has_scope and len(user_input) < 50:
            ambiguities.append((
                AmbiguityType.MISSING_SCOPE,
                "没有明确指定功能范围"
            ))
        
        # 2. Check for unclear requirements (vague language)
        vague_words = ["一些", "某种", "大概", "可能", "也许", "差不多", "some", "maybe", "perhaps", "kind of"]
        if any(word in input_lower for word in vague_words):
            ambiguities.append((
                AmbiguityType.UNCLEAR_REQUIREMENTS,
                "需求描述包含模糊词汇"
            ))
        
        # 3. Check for technical ambiguity
        tech_ambiguous = ["数据库", "api", "接口", "存储", "database", "storage", "interface"]
        tech_specific = ["mysql", "postgres", "redis", "mongodb", "rest", "graphql", "sqlite"]
        has_tech_general = any(t in input_lower for t in tech_ambiguous)
        has_tech_specific = any(t in input_lower for t in tech_specific)
        if has_tech_general and not has_tech_specific:
            ambiguities.append((
                AmbiguityType.TECHNICAL_AMBIGUITY,
                "技术实现方式未明确"
            ))
        
        # 4. Check for priority/importance indicators
        priority_words = ["紧急", "优先", "重要", "尽快", "urgent", "priority", "important", "asap"]
        has_priority = any(p in input_lower for p in priority_words)
        if not has_priority and len(user_input) > 30:
            ambiguities.append((
                AmbiguityType.PRIORITY_UNCLEAR,
                "未指定优先级"
            ))
        
        # 5. Check for missing context (no reference to existing system)
        context_words = ["现有", "已有", "当前", "目前", "existing", "current", "based on"]
        if not any(c in input_lower for c in context_words) and "新" not in input_lower:
            # Only add if it seems like a modification task
            mod_words = ["修改", "更新", "改进", "优化", "modify", "update", "improve", "optimize"]
            if any(m in input_lower for m in mod_words):
                ambiguities.append((
                    AmbiguityType.MISSING_CONTEXT,
                    "未说明基于现有系统还是新建"
                ))
        
        # 6. Check for multiple interpretations (low confidence)
        if confidence <= 0.6:
            ambiguities.append((
                AmbiguityType.MULTIPLE_INTERPRETATIONS,
                f"意图识别置信度较低({confidence:.0%})"
            ))
        
        return ambiguities
    
    def generate_clarification_questions(
        self, 
        ambiguities: List[Tuple[AmbiguityType, str]],
        user_input: str
    ) -> List[Tuple[str, AmbiguityType]]:
        """
        Generate clarification questions based on detected ambiguities.
        
        Args:
            ambiguities: List of detected ambiguities
            user_input: Original user input
            
        Returns:
            List of (question, ambiguity_type) tuples
        """
        questions = []
        
        # Question templates for each ambiguity type
        question_templates = {
            AmbiguityType.MISSING_SCOPE: [
                "请问这个功能属于哪个系统或模块？",
                "这个功能的边界是什么？需要影响哪些现有功能？"
            ],
            AmbiguityType.UNCLEAR_REQUIREMENTS: [
                "能否更具体地描述您期望的行为？",
                "请提供一个具体的使用场景示例？"
            ],
            AmbiguityType.TECHNICAL_AMBIGUITY: [
                "对于技术实现有什么偏好？（如数据库类型、API风格等）",
                "是否有特定的技术栈要求？"
            ],
            AmbiguityType.PRIORITY_UNCLEAR: [
                "这个需求的优先级如何？（高/中/低）",
                "是否有截止日期或时间限制？"
            ],
            AmbiguityType.MISSING_CONTEXT: [
                "这是基于现有系统的修改还是全新功能？",
                "如果是修改现有功能，请说明当前的行为是什么？"
            ],
            AmbiguityType.MULTIPLE_INTERPRETATIONS: [
                "您的需求可以有多种理解方式，能否更详细地说明？",
                "以下哪种描述更接近您的需求？"
            ]
        }
        
        # Generate questions based on ambiguities
        for amb_type, description in ambiguities:
            templates = question_templates.get(amb_type, ["能否提供更多细节？"])
            # Use first template, could be enhanced with LLM selection
            question = templates[0]
            questions.append((question, amb_type))
        
        # If using LLM, generate more contextual questions
        if self.llm_enabled and len(ambiguities) > 0:
            try:
                llm_questions = self._generate_questions_with_llm(user_input, ambiguities)
                if llm_questions:
                    questions = llm_questions
            except Exception:
                pass  # Fall back to template questions
        
        return questions[:3]  # Limit to 3 questions per round
    
    def _generate_questions_with_llm(
        self, 
        user_input: str, 
        ambiguities: List[Tuple[AmbiguityType, str]]
    ) -> List[Tuple[str, AmbiguityType]]:
        """Generate clarification questions using LLM"""
        amb_descriptions = [f"- {amb[0].value}: {amb[1]}" for amb in ambiguities]
        prompt = f"""根据用户输入和检测到的模糊点，生成2-3个澄清问题。

用户输入: "{user_input}"

检测到的模糊点:
{chr(10).join(amb_descriptions)}

要求：
1. 问题应该简洁明了
2. 适合非技术用户回答
3. 能帮助明确需求

请返回JSON数组格式：
[
    {{"question": "问题1", "type": "ambiguity_type"}},
    {{"question": "问题2", "type": "ambiguity_type"}}
]
"""
        try:
            response = self._call_llm(prompt)
            # Parse response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                questions_data = json.loads(json_match.group())
                result = []
                for q in questions_data:
                    try:
                        amb_type = AmbiguityType(q.get("type", "unclear_requirements"))
                    except ValueError:
                        amb_type = AmbiguityType.UNCLEAR_REQUIREMENTS
                    result.append((q["question"], amb_type))
                return result
        except Exception:
            pass
        return []
    
    def _refine_goal_from_answers(self, answers: Dict[str, str]) -> Optional[str]:
        """Refine the goal based on clarification answers"""
        if not self.dialog_manager or not answers:
            return None
        
        original = self.dialog_manager.context.original_goal
        if not original:
            return None
        
        # Build refined goal by incorporating answers
        refinements = []
        for qid, answer in answers.items():
            # Find the question
            for q in self.dialog_manager.pending_questions:
                if q.id == qid:
                    # Add context from the answer
                    if answer.strip():
                        refinements.append(answer)
                    break
        
        if refinements:
            return f"{original} (补充说明: {'; '.join(refinements)})"
        return original
    
    def _build_combined_input(self) -> str:
        """Build combined input from dialog history and context"""
        if not self.dialog_manager:
            return ""
        
        parts = []
        
        # Original goal
        if self.dialog_manager.context.original_goal:
            parts.append(self.dialog_manager.context.original_goal)
        
        # Refined goal
        if self.dialog_manager.context.refined_goal:
            parts.append(f"细化需求: {self.dialog_manager.context.refined_goal}")
        
        # Clarification answers
        if self.dialog_manager.context.clarifications:
            for qid, answer in self.dialog_manager.context.clarifications.items():
                parts.append(f"补充: {answer}")
        
        return " ".join(parts)
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state by ID"""
        if self.dialog_manager and self.dialog_manager.session_id == session_id:
            return self.dialog_manager.to_dict()
        return None
    
    def clear_session(self, session_id: Optional[str] = None):
        """Clear session state"""
        if session_id is None or (self.dialog_manager and self.dialog_manager.session_id == session_id):
            self.dialog_manager = None
    
    # ========================================================================
    # Original Methods (preserved for backward compatibility)
    # ========================================================================

    def recognize_intent(self, user_input: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        识别用户意图，返回意图类型和处理建议
        
        Args:
            user_input: 用户输入的自然语言描述
            use_llm: 是否使用LLM（None=自动选择，True=强制LLM，False=强制规则引擎）
        
        Returns:
            {
                "intent_type": IntentType,  # 意图类型
                "confidence": float,         # 置信度 0.0-1.0
                "reasoning": str,            # 推理说明
                "routing": Dict[str, Any],   # 路由信息
                "method": str                # "llm" or "rule_based"
            }
        """
        # 自动选择：如果有LLM且输入较复杂，使用LLM
        if use_llm is None:
            use_llm = self.llm_enabled and self._should_use_llm(user_input)
        
        # LLM模式
        if use_llm and self.llm_enabled:
            return self._recognize_with_llm(user_input)
        else:
            # 规则引擎模式（回退）
            return self._recognize_with_rules(user_input)
    
    def _should_use_llm(self, user_input: str) -> bool:
        """判断是否应该使用LLM（基于输入复杂度）"""
        # 简单关键词 -> 规则引擎
        simple_keywords = ["bug", "错误", "修复", "需求", "实现", "功能"]
        if any(kw in user_input.lower() for kw in simple_keywords) and len(user_input) < 50:
            return False
        
        # 复杂描述 -> LLM
        return len(user_input) > 30 or len(user_input.split()) > 5
    
    def _recognize_with_llm(self, user_input: str) -> Dict[str, Any]:
        """使用LLM识别用户意图"""
        try:
            prompt = self._build_intent_prompt(user_input)
            response = self._call_llm(prompt)
            result = self._parse_llm_response(response, user_input)
            result["method"] = "llm"
            return result
        except Exception as e:
            # LLM失败时回退到规则引擎
            result = self._recognize_with_rules(user_input)
            result["method"] = "rule_based_fallback"
            result["reasoning"] = f"LLM识别失败，使用规则引擎: {str(e)}"
            return result
    
    def _build_intent_prompt(self, user_input: str) -> str:
        """构建LLM意图识别提示"""
        prompt = f"""你是一个意图识别专家。根据用户的输入，判断用户的意图类型。

用户输入："{user_input}"

请分析用户意图，并返回JSON格式：
{{
    "intent_type": "feature_request" | "bug_fix" | "query" | "unknown",
    "confidence": 0.85,  // 置信度 0.0-1.0
    "reasoning": "用户描述了一个新功能需求，需要实现用户登录功能",
    "routing": {{
        "workflow_type": "standard" | "bug_fix",  // 工作流类型
        "stages": ["stage_id1", "stage_id2", ...],  // 如果是feature_request，需要执行的阶段
        "assigned_role": "role_id"  // 如果是bug_fix，建议分配的角色
    }}
}}

意图类型说明：
- "feature_request": 用户想要实现新功能或需求
- "bug_fix": 用户报告bug或需要修复问题
- "query": 用户只是询问或查看信息
- "unknown": 无法确定意图

只返回JSON，不要其他内容。"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        if hasattr(self.llm_client, 'chat'):
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages)
            if isinstance(response, dict):
                return response.get('content', response.get('text', str(response)))
            return str(response)
        elif hasattr(self.llm_client, 'complete'):
            response = self.llm_client.complete(prompt, max_tokens=500)
            return str(response)
        elif callable(self.llm_client):
            return str(self.llm_client(prompt))
        else:
            raise ValueError("LLM client interface not supported")
    
    def _parse_llm_response(self, response: str, user_input: str) -> Dict[str, Any]:
        """解析LLM响应"""
        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*"intent_type"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                json_str = json_match.group()
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                try:
                    result = json.loads(json_str)
                except:
                    result = self._fallback_parse(response)
        else:
            result = self._fallback_parse(response)
        
        # 验证和修复结果
        intent_type_str = result.get("intent_type", "unknown")
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.UNKNOWN
        
        # 确保有置信度
        confidence = result.get("confidence", 0.5)
        
        # 构建路由信息
        routing = result.get("routing", {})
        if intent_type == IntentType.FEATURE_REQUEST:
            # 需求实现：使用IntentRouter识别需要执行的阶段
            stage_result = self.intent_router.analyze_intent(user_input)
            routing["workflow_type"] = "standard"
            routing["stages"] = stage_result.get("stages", [])
        elif intent_type == IntentType.BUG_FIX:
            # Bug修复：分析bug并分配角色
            routing["workflow_type"] = "bug_fix"
            routing["assigned_role"] = routing.get("assigned_role") or self._suggest_bug_fix_role(user_input)
        
        return {
            "intent_type": intent_type,
            "confidence": confidence,
            "reasoning": result.get("reasoning", "LLM识别结果"),
            "routing": routing,
            "method": "llm"
        }
    
    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """LLM响应解析失败时的回退处理"""
        return {
            "intent_type": "unknown",
            "confidence": 0.3,
            "reasoning": "LLM响应解析失败",
            "routing": {}
        }
    
    def _recognize_with_rules(self, user_input: str) -> Dict[str, Any]:
        """使用规则引擎识别用户意图"""
        user_input_lower = user_input.lower()
        
        # Bug修复关键词
        bug_keywords = [
            "bug", "错误", "修复", "问题", "故障", "异常", "报错",
            "不工作", "失效", "失败", "broken", "error", "fix", "issue"
        ]
        
        # 需求实现关键词
        feature_keywords = [
            "实现", "开发", "创建", "构建", "添加", "新功能", "需求",
            "implement", "develop", "create", "build", "add", "feature", "requirement"
        ]
        
        # 查询关键词
        query_keywords = [
            "什么", "如何", "为什么", "查看", "显示", "列出",
            "what", "how", "why", "show", "list", "explain"
        ]
        
        # 检测bug修复意图
        bug_score = sum(1 for kw in bug_keywords if kw in user_input_lower)
        feature_score = sum(1 for kw in feature_keywords if kw in user_input_lower)
        query_score = sum(1 for kw in query_keywords if kw in user_input_lower)
        
        # 确定意图类型
        if bug_score > feature_score and bug_score > query_score:
            intent_type = IntentType.BUG_FIX
            confidence = min(0.9, 0.5 + bug_score * 0.1)
            reasoning = f"检测到bug修复关键词（匹配{bug_score}个）"
            routing = {
                "workflow_type": "bug_fix",
                "assigned_role": self._suggest_bug_fix_role(user_input)
            }
        elif feature_score > query_score:
            intent_type = IntentType.FEATURE_REQUEST
            confidence = min(0.9, 0.5 + feature_score * 0.1)
            reasoning = f"检测到需求实现关键词（匹配{feature_score}个）"
            # 使用IntentRouter识别需要执行的阶段
            stage_result = self.intent_router.analyze_intent(user_input)
            routing = {
                "workflow_type": "standard",
                "stages": stage_result.get("stages", [])
            }
        elif query_score > 0:
            intent_type = IntentType.QUERY
            confidence = min(0.8, 0.4 + query_score * 0.1)
            reasoning = f"检测到查询关键词（匹配{query_score}个）"
            routing = {
                "workflow_type": "query"
            }
        else:
            # 默认：如果有任务描述，认为是需求实现
            task_keywords = ["做", "完成", "处理", "执行"]
            has_task = any(kw in user_input_lower for kw in task_keywords)
            if has_task or len(user_input.strip()) > 10:
                intent_type = IntentType.FEATURE_REQUEST
                confidence = 0.6
                reasoning = "默认识别为需求实现"
                stage_result = self.intent_router.analyze_intent(user_input)
                routing = {
                    "workflow_type": "standard",
                    "stages": stage_result.get("stages", [])
                }
            else:
                intent_type = IntentType.UNKNOWN
                confidence = 0.3
                reasoning = "无法确定意图"
                routing = {}
        
        return {
            "intent_type": intent_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "routing": routing,
            "method": "rule_based"
        }
    
    def _suggest_bug_fix_role(self, user_input: str) -> Optional[str]:
        """根据bug描述建议合适的修复角色"""
        if not self.engine.role_manager:
            return None
        
        user_input_lower = user_input.lower()
        
        # 根据bug描述匹配角色
        role_keywords = {
            "frontend": ["前端", "ui", "界面", "页面", "样式", "frontend", "ui"],
            "backend": ["后端", "api", "服务", "数据库", "backend", "server"],
            "qa": ["测试", "质量", "验证", "test", "qa", "quality"],
            "devops": ["部署", "环境", "配置", "deploy", "devops", "infrastructure"]
        }
        
        # 找到最匹配的角色
        best_role = None
        best_score = 0
        
        for role_id, role in self.engine.role_manager.roles.items():
            score = 0
            role_name_lower = role.name.lower()
            role_desc_lower = role.description.lower()
            
            # 检查角色名称和描述
            for category, keywords in role_keywords.items():
                if any(kw in role_name_lower or kw in role_desc_lower for kw in keywords):
                    if any(kw in user_input_lower for kw in keywords):
                        score += 2
            
            if score > best_score:
                best_score = score
                best_role = role_id
        
        # 如果没有匹配，返回qa_reviewer或第一个可用角色
        if not best_role:
            if "qa_reviewer" in self.engine.role_manager.roles:
                return "qa_reviewer"
            elif self.engine.role_manager.roles:
                return list(self.engine.role_manager.roles.keys())[0]
        
        return best_role
    
    def route(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据意图识别结果路由到相应的处理流程
        
        Args:
            intent_result: recognize_intent()返回的结果
        
        Returns:
            路由结果，包含处理建议
        """
        intent_type = intent_result["intent_type"]
        routing = intent_result.get("routing", {})
        
        if intent_type == IntentType.FEATURE_REQUEST:
            # 需求实现：走标准工作流
            return {
                "action": "execute_workflow",
                "workflow_type": "standard",
                "stages": routing.get("stages", []),
                "description": "执行标准工作流：需求分析 → 架构设计 → 实现 → 验证"
            }
        elif intent_type == IntentType.BUG_FIX:
            # Bug修复：分析后分配
            return {
                "action": "analyze_and_assign",
                "workflow_type": "bug_fix",
                "assigned_role": routing.get("assigned_role"),
                "description": "分析bug并分配给合适的角色进行修复"
            }
        elif intent_type == IntentType.QUERY:
            # 查询：直接回答
            return {
                "action": "answer_query",
                "workflow_type": "query",
                "description": "回答用户查询"
            }
        else:
            # 未知意图：询问用户
            return {
                "action": "clarify",
                "workflow_type": "unknown",
                "description": "无法确定意图，需要用户澄清"
            }
