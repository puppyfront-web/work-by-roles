"""
Role executor for executing role-specific tasks.
Following Single Responsibility Principle - handles role execution only.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

from .exceptions import WorkflowError
from .models import Role, Stage, ContextSummary, AgentContext
from .workflow_engine import WorkflowEngine
from .skill_selector import SkillSelector
from .skill_invoker import SkillInvoker
from .agent import Agent
from .agent_orchestrator import AgentOrchestrator
from .execution_tracker import ExecutionTracker

class RoleExecutor:
    """
    简化的角色执行器 - 直接执行角色和技能，无需workflow阶段。
    
    适用于IDE环境（如Cursor），用户指定角色和需求，角色使用skills来处理。
    
    架构：
    - 用户指定角色和需求
    - 角色根据需求选择合适的skills
    - 执行skills并返回结果
    """
    
    def __init__(
        self,
        engine: 'WorkflowEngine',
        llm_client: Optional[Any] = None,
        skill_invoker: Optional[SkillInvoker] = None
    ):
        """
        初始化RoleExecutor。
        
        Args:
            engine: WorkflowEngine实例（用于访问角色和技能库）
            llm_client: 可选的LLM客户端
            skill_invoker: 可选的技能调用器
        """
        self.engine = engine
        self.llm_client = llm_client
        self.skill_selector = SkillSelector(engine)
        self.execution_tracker = ExecutionTracker()
        
        # 使用AgentOrchestrator的技能执行能力
        self.orchestrator = AgentOrchestrator(
            engine=engine,
            llm_client=llm_client,
            skill_invoker=skill_invoker
        )
    
    def execute_role(
        self,
        role_id: str,
        requirement: str,
        inputs: Optional[Dict[str, Any]] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        执行角色处理需求。
        
        Args:
            role_id: 角色ID
            requirement: 用户需求描述
            inputs: 可选的输入数据
            use_llm: 是否使用LLM进行推理（需要llm_client）
            
        Returns:
            包含执行结果的字典
        """
        # 1. 获取角色
        role = self.engine.role_manager.get_role(role_id)
        if not role:
            raise WorkflowError(f"Role '{role_id}' not found")
        
        # 2. 创建Agent
        agent = Agent(role, self.engine, self.skill_selector)
        agent.prepare(requirement, inputs or {})
        
        # 3. 构建完整上下文
        full_context = self._build_context(role, requirement, agent.context, inputs or {})
        
        # 4. 根据需求选择合适的技能
        selected_skills = self._select_skills_for_requirement(role, requirement, full_context)
        
        # 4. 执行技能
        skill_results = []
        for skill_id in selected_skills:
            try:
                skill_input = self._prepare_skill_input(requirement, inputs or {}, agent.context)
                result = self.orchestrator.execute_skill(
                    skill_id=skill_id,
                    input_data=skill_input,
                    role_id=role_id
                )
                skill_results.append({
                    "skill_id": skill_id,
                    "result": result
                })
            except Exception as e:
                skill_results.append({
                    "skill_id": skill_id,
                    "error": str(e)
                })
        
        # 5. 生成最终响应
        final_response = self._generate_response(
            role=role,
            requirement=requirement,
            skill_results=skill_results,
            agent=agent,
            use_llm=use_llm
        )
        
        return {
            "role_id": role_id,
            "requirement": requirement,
            "skills_executed": [r["skill_id"] for r in skill_results],
            "skill_results": skill_results,
            "response": final_response,
            "agent_context": agent.context
        }
    
    def _build_context(
        self,
        role: Role,
        requirement: str,
        agent_context: Optional[AgentContext],
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建完整的上下文信息用于技能选择"""
        context = {
            "requirement": requirement,
            "role_id": role.id,
            "inputs": inputs
        }
        
        # 添加项目上下文
        if agent_context and agent_context.project_context:
            pc = agent_context.project_context
            context["project_context"] = pc
            
            # 提取项目类型和技术栈
            if pc.specs:
                project_type = pc.specs.get("project_type", "")
                if project_type:
                    context["project_type"] = project_type
            
            # 从路径推断技术栈
            tech_stack = []
            if pc.paths:
                if "src" in pc.paths:
                    tech_stack.append("python")
                if "requirements.txt" in str(pc.root_path):
                    tech_stack.append("python")
            if tech_stack:
                context["tech_stack"] = tech_stack
        
        # 添加当前阶段（如果有）
        if self.engine.executor and self.engine.executor.state:
            current_stage = self.engine.executor.state.current_stage
            if current_stage:
                context["current_stage"] = current_stage
        
        # 添加历史技能执行记录
        if self.execution_tracker:
            previous_skills = []
            for skill_id in self.execution_tracker.executions.keys():
                history = self.execution_tracker.get_skill_history(skill_id)
                if any(e.status == "success" for e in history):
                    previous_skills.append(skill_id)
            if previous_skills:
                context["previous_skills"] = previous_skills
        
        return context
    
    def _select_skills_for_requirement(
        self,
        role: Role,
        requirement: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        根据需求和角色选择合适的技能。
        
        优先使用角色required_skills中定义的技能。
        """
        selected = []
        context = context or {}
        
        # 优先使用角色required_skills中定义的技能
        if role.required_skills:
            for skill_req in role.required_skills:
                if skill_req.skill_id not in selected:
                    # 检查技能是否存在
                    if self.engine.role_manager.skill_library:
                        skill = self.engine.role_manager.skill_library.get(skill_req.skill_id)
                        if skill:
                            selected.append(skill_req.skill_id)
        
        # 如果没有required_skills或没有找到技能，使用SkillSelector自动选择
        if not selected:
            skill = self.skill_selector.select_skill(
                task_description=requirement,
                role=role,
                context=context
            )
            if skill and skill.id not in selected:
                selected.append(skill.id)
        
        return selected
    
    def _prepare_skill_input(
        self,
        requirement: str,
        inputs: Dict[str, Any],
        context: Optional[AgentContext]
    ) -> Dict[str, Any]:
        """准备技能输入数据"""
        skill_input = {
            "requirement": requirement,
            **inputs
        }
        
        if context:
            skill_input["workspace_path"] = str(context.workspace_path)
            if context.project_context:
                skill_input["project_context"] = context.project_context.to_dict()
        
        return skill_input
    
    def _generate_response(
        self,
        role: Role,
        requirement: str,
        skill_results: List[Dict[str, Any]],
        agent: Agent,
        use_llm: bool
    ) -> str:
        """
        生成最终响应。
        
        如果use_llm=True且有llm_client，使用LLM生成响应。
        否则，简单汇总技能执行结果。
        """
        if use_llm and self.llm_client:
            # 使用LLM生成响应
            prompt = self._build_response_prompt(role, requirement, skill_results)
            try:
                if hasattr(self.llm_client, 'complete'):
                    response = self.llm_client.complete(prompt)
                elif hasattr(self.llm_client, 'chat'):
                    response = self.llm_client.chat([{"role": "user", "content": prompt}])
                elif callable(self.llm_client):
                    response = self.llm_client(prompt)
                else:
                    response = self._format_simple_response(skill_results)
                return str(response)
            except Exception as e:
                # LLM调用失败，回退到简单响应
                return self._format_simple_response(skill_results)
        else:
            # 简单汇总响应
            return self._format_simple_response(skill_results)
    
    def _build_response_prompt(
        self,
        role: Role,
        requirement: str,
        skill_results: List[Dict[str, Any]]
    ) -> str:
        """构建LLM响应提示"""
        prompt_parts = [
            f"You are acting as a {role.name}.",
            f"Description: {role.description}\n",
            f"User Requirement: {requirement}\n",
            "Skill Execution Results:"
        ]
        
        for i, result in enumerate(skill_results, 1):
            prompt_parts.append(f"\n{i}. Skill: {result['skill_id']}")
            if "result" in result:
                prompt_parts.append(f"   Result: {json.dumps(result['result'], indent=2)}")
            if "error" in result:
                prompt_parts.append(f"   Error: {result['error']}")
        
        prompt_parts.append("\nBased on the skill execution results above, provide a comprehensive response to the user's requirement.")
        if role.instruction_template:
            prompt_parts.append(f"\nRole Instructions:\n{role.instruction_template}")
        
        return "\n".join(prompt_parts)
    
    def _format_simple_response(self, skill_results: List[Dict[str, Any]]) -> str:
        """格式化简单响应（不使用LLM）"""
        response_parts = ["技能执行结果汇总：\n"]
        
        for i, result in enumerate(skill_results, 1):
            response_parts.append(f"{i}. 技能: {result['skill_id']}")
            if "result" in result:
                if result['result'].get('success'):
                    response_parts.append(f"   ✅ 执行成功")
                    if result['result'].get('output'):
                        output = result['result']['output']
                        if isinstance(output, dict):
                            response_parts.append(f"   输出: {json.dumps(output, indent=2, ensure_ascii=False)}")
                        else:
                            response_parts.append(f"   输出: {output}")
                else:
                    response_parts.append(f"   ❌ 执行失败")
            if "error" in result:
                response_parts.append(f"   ❌ 错误: {result['error']}")
            response_parts.append("")
        
        return "\n".join(response_parts)


