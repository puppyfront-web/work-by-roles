"""
Intent router for analyzing user intent and routing to stages.
Following Single Responsibility Principle - handles intent analysis and routing only.
"""

from typing import Dict, List, Optional, Any
import re
import warnings

from .exceptions import WorkflowError
from .models import Stage, Workflow, Skill, SkillExecution
from .enums import SkillErrorType
from .workflow_engine import WorkflowEngine

class IntentRouter:
    """
    意图路由器：根据用户输入智能识别需要执行的阶段
    
    支持两种模式：
    1. LLM模式（优先）：使用LLM理解用户意图
    2. 规则引擎模式（回退）：基于关键词匹配（无LLM时使用）
    """
    
    def __init__(self, engine: 'WorkflowEngine', llm_client: Optional[Any] = None):
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
    
    def analyze_intent(self, user_input: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        分析用户意图，返回需要执行的阶段列表
        
        Args:
            user_input: 用户输入的自然语言描述
            use_llm: 是否使用LLM（None=自动选择，True=强制LLM，False=强制规则引擎）
        
        Returns:
            {
                "stages": [stage_ids],
                "confidence": float,  # 0.0-1.0
                "reasoning": str,
                "intent_type": str,  # "full", "partial", "specific"
                "method": str  # "llm" or "rule_based"
            }
        """
        if not self.engine.workflow:
            return {
                "stages": [],
                "confidence": 0.0,
                "reasoning": "工作流未加载",
                "intent_type": "unknown",
                "method": "none"
            }
        
        # 自动选择：如果有LLM且输入较复杂，使用LLM
        if use_llm is None:
            use_llm = self.llm_enabled and self._should_use_llm(user_input)
        
        # LLM模式
        if use_llm and self.llm_enabled:
            return self._analyze_with_llm(user_input)
        else:
            # 规则引擎模式（回退）
            return self._analyze_with_rules(user_input)
    
    def _should_use_llm(self, user_input: str) -> bool:
        """判断是否应该使用LLM（基于输入复杂度）"""
        # 简单关键词 -> 规则引擎
        simple_keywords = ["需求", "架构", "实现", "测试", "requirements", "architecture", "implementation"]
        if any(kw in user_input.lower() for kw in simple_keywords) and len(user_input) < 50:
            return False
        
        # 复杂描述 -> LLM
        return len(user_input) > 30 or len(user_input.split()) > 5
    
    def _analyze_with_llm(self, user_input: str) -> Dict[str, Any]:
        """使用LLM分析用户意图"""
        try:
            # 构建意图识别提示
            prompt = self._build_intent_prompt(user_input)
            
            # 调用LLM
            response = self._call_llm(prompt)
            
            # 解析LLM响应
            result = self._parse_llm_response(response, user_input)
            result["method"] = "llm"
            
            return result
            
        except Exception as e:
            # LLM失败时回退到规则引擎
            result = self._analyze_with_rules(user_input)
            result["method"] = "rule_based_fallback"
            result["reasoning"] = f"LLM分析失败，使用规则引擎: {str(e)}"
            return result
    
    def _build_intent_prompt(self, user_input: str) -> str:
        """构建LLM意图识别提示"""
        # 获取所有阶段信息
        stages_info = []
        for stage in self.engine.workflow.stages:
            role = self.engine.role_manager.get_role(stage.role)
            role_name = role.name if role else stage.role
            
            stages_info.append(f"""
- Stage ID: {stage.id}
  Name: {stage.name}
  Role: {role_name}
  Goal: {stage.goal_template or 'N/A'}
  Description: {role.description if role else 'N/A'}
""")
        
        prompt = f"""你是一个工作流意图识别专家。根据用户的输入，分析需要执行哪些工作流阶段。

可用阶段：
{''.join(stages_info)}

用户输入："{user_input}"

请分析用户意图，并返回JSON格式：
{{
    "stages": ["stage_id1", "stage_id2", ...],  // 需要执行的阶段ID列表
    "confidence": 0.85,  // 置信度 0.0-1.0
    "reasoning": "用户想要实现新功能并测试，需要implementation和validation阶段",
    "intent_type": "partial"  // "full"=完整流程, "partial"=部分阶段, "specific"=单个阶段
}}

注意：
1. 只返回需要的阶段，不要包含不必要的阶段
2. 如果用户明确要求"完整流程"、"全部"、"end-to-end"等，返回所有阶段
3. 必须考虑阶段依赖关系（如果阶段B依赖阶段A，且B被选中，则A也必须被包含）
4. confidence应该反映你对意图理解的把握程度
5. 如果用户只是询问或查看，stages可以为空数组

只返回JSON，不要其他内容。"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        if hasattr(self.llm_client, 'chat'):
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages)
            # 处理不同LLM响应格式
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
        import re
        
        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*"stages"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试修复常见问题
                json_str = json_match.group()
                json_str = re.sub(r',\s*}', '}', json_str)  # 移除尾随逗号
                json_str = re.sub(r',\s*]', ']', json_str)
                try:
                    result = json.loads(json_str)
                except:
                    result = self._fallback_parse(response)
        else:
            result = self._fallback_parse(response)
        
        # 验证和修复结果
        if "stages" not in result:
            result["stages"] = []
        
        # 确保阶段ID有效
        valid_stages = []
        for stage_id in result.get("stages", []):
            if self._get_stage_by_id(stage_id):
                valid_stages.append(stage_id)
        result["stages"] = valid_stages
        
        # 解析依赖关系
        result["stages"] = self._resolve_dependencies(result["stages"])
        
        # 确保有置信度
        if "confidence" not in result:
            result["confidence"] = 0.7 if result["stages"] else 0.3
        
        # 确定意图类型
        if not result["stages"]:
            result["intent_type"] = "none"
        elif len(result["stages"]) == len(self.engine.workflow.stages):
            result["intent_type"] = "full"
        elif len(result["stages"]) == 1:
            result["intent_type"] = "specific"
        else:
            result["intent_type"] = "partial"
        
        # 生成推理说明
        if "reasoning" not in result or not result["reasoning"]:
            result["reasoning"] = self._generate_reasoning(
                result["stages"], 
                result["intent_type"]
            )
        
        return result
    
    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """LLM响应解析失败时的回退处理"""
        # 尝试从文本中提取阶段ID
        stages = []
        for stage in self.engine.workflow.stages:
            if stage.id.lower() in response.lower() or stage.name.lower() in response.lower():
                stages.append(stage.id)
        
        return {
            "stages": stages,
            "confidence": 0.5,
            "reasoning": "LLM响应解析失败，使用文本匹配",
            "intent_type": "partial" if stages else "unknown"
        }
    
    def _analyze_with_rules(self, user_input: str) -> Dict[str, Any]:
        """使用规则引擎分析（关键词匹配）"""
        user_input_lower = user_input.lower()
        
        # 1. 检测@[team] - 总是执行完整工作流
        if "@[team]" in user_input or "@team" in user_input:
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 1.0,
                "reasoning": "检测到@[team]，虚拟团队工作流执行完整流程",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 2. 检测完整流程意图
        full_workflow_keywords = [
            "完整", "全部", "整个", "end-to-end", "e2e", 
            "从头", "全流程", "wfauto", "完整工作流"
        ]
        if any(kw in user_input_lower for kw in full_workflow_keywords):
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 1.0,
                "reasoning": "检测到完整流程请求",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 3. 检测明确指定部分阶段的请求
        explicit_partial_keywords = ["只做", "只要", "仅", "only", "just", "跳过", "不要", "不需要"]
        is_explicit_partial = any(kw in user_input_lower for kw in explicit_partial_keywords)
        
        # 如果不是明确指定部分阶段，默认返回完整工作流（虚拟团队工作流特性）
        if not is_explicit_partial:
            # 检测是否有任务描述（实现、开发、创建等）
            task_keywords = ["实现", "开发", "创建", "构建", "做", "完成", "implement", "develop", "create", "build", "make"]
            has_task = any(kw in user_input_lower for kw in task_keywords)
            
            # 如果有任务描述或输入足够长，默认执行完整工作流
            if has_task or len(user_input.strip()) > 10:
                return {
                    "stages": [s.id for s in self.engine.workflow.stages],
                    "confidence": 0.9,
                    "reasoning": "虚拟团队工作流：默认执行完整工作流分析需求目标",
                    "intent_type": "full",
                    "method": "rule_based"
                }
        
        # 4. 阶段关键词匹配（仅在明确指定部分阶段时使用）
        stage_matches = self._match_stages_by_keywords(user_input_lower)
        
        # 5. 角色关键词匹配
        role_matches = self._match_stages_by_roles(user_input_lower)
        
        # 6. 合并匹配结果
        matched_stage_ids = set(stage_matches) | set(role_matches)
        
        # 7. 如果没有匹配，检查是否有特定任务类型
        if not matched_stage_ids:
            matched_stage_ids = self._match_by_task_type(user_input_lower)
        
        # 8. 包含依赖阶段
        required_stages = self._resolve_dependencies(list(matched_stage_ids))
        
        # 9. 如果明确指定部分阶段但匹配结果为空，仍然返回完整工作流
        if is_explicit_partial and not required_stages:
            return {
                "stages": [s.id for s in self.engine.workflow.stages],
                "confidence": 0.7,
                "reasoning": "未匹配到明确阶段，执行完整工作流",
                "intent_type": "full",
                "method": "rule_based"
            }
        
        # 10. 计算置信度
        confidence = self._calculate_confidence(
            list(matched_stage_ids), 
            user_input_lower,
            len(required_stages) < len(self.engine.workflow.stages)
        )
        
        # 11. 确定意图类型
        intent_type = "full" if len(required_stages) == len(self.engine.workflow.stages) else (
            "specific" if len(required_stages) == 1 else "partial"
        )
        
        return {
            "stages": sorted(required_stages, key=lambda sid: self._get_stage_order(sid)),
            "confidence": confidence,
            "reasoning": self._generate_reasoning(list(matched_stage_ids), required_stages, intent_type),
            "intent_type": intent_type,
            "method": "rule_based"
        }
    
    def _match_stages_by_keywords(self, user_input: str) -> List[str]:
        """基于阶段名称和关键词匹配"""
        matched = []
        
        # 阶段关键词映射
        stage_keywords = {
            "requirements": ["需求", "要求", "范围", "scope", "requirement", "spec", "规范"],
            "architecture": ["架构", "设计", "architecture", "design", "schema", "dsl", "结构"],
            "implementation": ["实现", "编码", "代码", "implement", "code", "开发", "编写"],
            "validation": ["验证", "测试", "质量", "validation", "test", "qa", "review", "检查"]
        }
        
        for stage in self.engine.workflow.stages:
            stage_id_lower = stage.id.lower()
            stage_name_lower = stage.name.lower()
            
            # 检查阶段ID和名称
            if stage_id_lower in user_input or stage_name_lower in user_input:
                matched.append(stage.id)
                continue
            
            # 检查关键词
            keywords = stage_keywords.get(stage.id, [])
            if any(kw in user_input for kw in keywords):
                matched.append(stage.id)
        
        return matched
    
    def _match_stages_by_roles(self, user_input: str) -> List[str]:
        """基于角色描述匹配"""
        matched = []
        
        for stage in self.engine.workflow.stages:
            role = self.engine.role_manager.get_role(stage.role)
            if not role:
                continue
            
            # 检查角色名称和描述
            role_name_lower = role.name.lower()
            role_desc_lower = role.description.lower()
            
            if role_name_lower in user_input or role_desc_lower in user_input:
                matched.append(stage.id)
                continue
            
            # 检查角色允许的动作
            allowed_actions = role.constraints.get('allowed_actions', [])
            for action in allowed_actions:
                if action.lower() in user_input:
                    matched.append(stage.id)
                    break
        
        return matched
    
    def _match_by_task_type(self, user_input: str) -> List[str]:
        """基于任务类型推断阶段"""
        matched = []
        
        # 文档相关 -> requirements/architecture
        if any(kw in user_input for kw in ["文档", "doc", "写文档", "创建文档"]):
            matched.extend(["requirements", "architecture"])
        
        # 代码相关 -> implementation
        if any(kw in user_input for kw in ["代码", "code", "写代码", "实现功能"]):
            matched.append("implementation")
        
        # 测试相关 -> validation
        if any(kw in user_input for kw in ["测试", "test", "验证", "检查代码"]):
            matched.append("validation")
        
        # 过滤无效的阶段ID
        valid_matched = []
        for stage_id in matched:
            if self._get_stage_by_id(stage_id):
                valid_matched.append(stage_id)
        
        return valid_matched
    
    def _resolve_dependencies(self, stage_ids: List[str]) -> List[str]:
        """解析阶段依赖，确保前置阶段被包含"""
        required = set(stage_ids)
        
        # 递归解析依赖
        changed = True
        while changed:
            changed = False
            for stage_id in list(required):
                stage = self._get_stage_by_id(stage_id)
                if stage and stage.prerequisites:
                    for prereq in stage.prerequisites:
                        if prereq not in required:
                            required.add(prereq)
                            changed = True
        
        return list(required)
    
    def _calculate_confidence(
        self, 
        matched_stages: List[str], 
        user_input: str,
        is_partial: bool
    ) -> float:
        """计算匹配置信度"""
        if not matched_stages:
            return 0.0
        
        # 基础置信度
        confidence = 0.5
        
        # 如果匹配到多个阶段，增加置信度
        if len(matched_stages) > 1:
            confidence += 0.2
        
        # 如果输入包含明确的阶段名称，增加置信度
        for stage in self.engine.workflow.stages:
            if stage.id.lower() in user_input or stage.name.lower() in user_input:
                confidence += 0.2
                break
        
        # 如果是部分匹配，稍微降低置信度（因为可能遗漏）
        if is_partial:
            confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))
    
    def _generate_reasoning(
        self, 
        matched: List[str], 
        required: List[str],
        intent_type: str
    ) -> str:
        """生成推理说明"""
        if intent_type == "full":
            return "执行完整工作流（所有阶段）"
        
        matched_names = [self._get_stage_name(sid) for sid in matched]
        required_names = [self._get_stage_name(sid) for sid in required]
        
        if len(matched) == len(required):
            return f"匹配到阶段: {', '.join(matched_names)}"
        else:
            return f"匹配到阶段: {', '.join(matched_names)}，包含依赖: {', '.join(required_names)}"
    
    def _get_stage_by_id(self, stage_id: str) -> Optional[Stage]:
        """获取阶段对象"""
        if not self.engine.executor:
            return None
        return self.engine.executor._get_stage_by_id(stage_id)
    
    def _get_stage_order(self, stage_id: str) -> int:
        """获取阶段顺序"""
        stage = self._get_stage_by_id(stage_id)
        return stage.order if stage else 999
    
    def _get_stage_name(self, stage_id: str) -> str:
        """获取阶段名称"""
        stage = self._get_stage_by_id(stage_id)
        return stage.name if stage else stage_id
    
    def handle_retry(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        error: Exception,
        skill: Skill
    ) -> Dict[str, Any]:
        """Handle retry logic and return retry configuration"""
        if not skill.error_handling:
            raise error  # No retry configured, re-raise
        
        error_config = skill.error_handling
        strategy = error_config.get('retry_strategy', 'exponential_backoff')
        
        # Get current retry count from tracker if available
        retry_count = 0
        if self.execution_tracker:
            history = self.execution_tracker.get_skill_history(skill_id)
            retry_count = max((e.retry_count for e in history), default=0) + 1
        
        delay = self.get_retry_delay(retry_count, strategy)
        
        return {
            "should_retry": True,
            "retry_count": retry_count,
            "delay": delay,
            "strategy": strategy
        }
    
    def _classify_error(self, error: Exception) -> SkillErrorType:
        """Classify exception into SkillErrorType"""
        error_msg = str(error).lower()
        error_type = type(error).__name__.lower()
        
        if 'validation' in error_msg or 'schema' in error_msg:
            return SkillErrorType.VALIDATION_ERROR
        elif 'timeout' in error_msg or 'time' in error_type:
            return SkillErrorType.TIMEOUT_ERROR
        elif 'test' in error_msg or 'test' in error_type:
            return SkillErrorType.TEST_FAILURE
        elif 'context' in error_msg or 'missing' in error_msg:
            return SkillErrorType.INSUFFICIENT_CONTEXT
        else:
            return SkillErrorType.EXECUTION_ERROR
    
    def format_error_response(
        self,
        error: Exception,
        skill: Skill,
        retryable: bool = False
    ) -> Dict[str, Any]:
        """Format error response in standard format"""
        error_type = self._classify_error(error)
        
        response = {
            "success": False,
            "error_type": error_type.value,
            "error_message": str(error),
            "retryable": retryable,
        }
        
        # Add suggested fix if available in skill metadata
        if skill.metadata and 'error_suggestions' in skill.metadata:
            suggestions = skill.metadata['error_suggestions']
            if isinstance(suggestions, dict) and error_type.value in suggestions:
                response["suggested_fix"] = suggestions[error_type.value]
        
        return response


