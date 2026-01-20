"""
Intent Agent for unified user intent recognition and routing.
Following Single Responsibility Principle - handles intent recognition and routing only.
"""

from typing import Dict, List, Optional, Any
import json
import re

from .exceptions import WorkflowError
from .enums import IntentType
from .workflow_engine import WorkflowEngine
from .intent_router import IntentRouter


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
