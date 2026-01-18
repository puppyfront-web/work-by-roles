"""
Role executor for executing role-specific tasks.
Following Single Responsibility Principle - handles role execution only.
"""

import json
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
from .execution_mode_analyzer import ExecutionModeAnalyzer

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
        use_llm: bool = False,
        immersive_display: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        执行角色处理需求（独立执行模式）。
        
        这是独立于工作流的角色执行模式，不应用工作流约束：
        - 不检查工作流阶段状态
        - 不应用阶段边界限制
        - 不检查工作流前提条件
        - 不验证角色在工作流中的 allowed_actions/forbidden_actions 约束
        - 角色可以自由执行，不受工作流限制
        
        适用于通过 `@role_name` 或 `workflow role-execute` 直接调用角色的场景。
        
        Args:
            role_id: 角色ID
            requirement: 用户需求描述
            inputs: 可选的输入数据
            use_llm: 是否使用LLM进行推理（需要llm_client）
            immersive_display: 可选的沉浸式显示实例
            
        Returns:
            包含执行结果的字典
        """
        # 1. 获取角色
        role = self.engine.role_manager.get_role(role_id)
        if not role:
            raise WorkflowError(f"Role '{role_id}' not found")
        
        # 获取执行模式信息
        execution_mode_info = None
        if self.engine.role_manager.skill_library:
            execution_mode_info = ExecutionModeAnalyzer.get_execution_mode_info(
                role=role,
                skill_library=self.engine.role_manager.skill_library,
                environment="cursor"
            )
        
        # 显示角色开始执行（沉浸式）
        if immersive_display:
            immersive_display.display_role_start(
                role_id=role_id,
                role_name=role.name,
                role_description=role.description,
                requirement=requirement,
                execution_mode_info=execution_mode_info
            )
        
        # 2. 创建Agent
        agent = Agent(role, self.engine, self.skill_selector)
        agent.prepare(requirement, inputs or {})
        
        # 3. 构建完整上下文
        full_context = self._build_context(role, requirement, agent.context, inputs or {})
        
        # 4. 根据需求选择合适的技能
        selected_skills = self._select_skills_for_requirement(role, requirement, full_context)
        
        # 显示技能选择结果（沉浸式）
        if immersive_display and selected_skills:
            immersive_display.display_role_progress(
                role_name=role.name,
                action=f"已选择 {len(selected_skills)} 个技能: {', '.join(selected_skills)}"
            )
        
        # 4. 执行技能（独立执行模式：stage_id=None，不应用工作流约束）
        skill_results = []
        workflow_results = []  # 收集技能执行结果，用于生成输出文件
        for skill_id in selected_skills:
            try:
                # 显示技能执行开始（沉浸式）
                if immersive_display:
                    immersive_display.display_role_skill_execution(
                        role_name=role.name,
                        skill_id=skill_id,
                        status="executing"
                    )
                
                skill_input = self._prepare_skill_input(requirement, inputs or {}, agent.context)
                # 注意：stage_id=None 表示独立执行模式，不应用工作流约束
                result = self.orchestrator.execute_skill(
                    skill_id=skill_id,
                    input_data=skill_input,
                    stage_id=None,  # 独立执行模式，不关联工作流阶段
                    role_id=role_id
                )
                
                # 显示技能执行完成（沉浸式）
                if immersive_display:
                    status = "success" if result.get("success") else "failed"
                    immersive_display.display_role_skill_execution(
                        role_name=role.name,
                        skill_id=skill_id,
                        status=status
                    )
                skill_results.append({
                    "skill_id": skill_id,
                    "result": result
                })
                # 收集技能执行结果用于输出文件生成
                if result and isinstance(result, dict):
                    workflow_results.append({
                        "workflow_id": f"role_execute_{role_id}",
                        "status": "success" if result.get("success") else "error",
                        "outputs": result.get("output", {}),
                        "errors": [] if result.get("success") else [result.get("error", "Unknown error")]
                    })
            except Exception as e:
                skill_results.append({
                    "skill_id": skill_id,
                    "error": str(e)
                })
                workflow_results.append({
                    "workflow_id": f"role_execute_{role_id}",
                    "status": "error",
                    "outputs": {},
                    "errors": [str(e)]
                })
        
        # 4.5. 生成输出文件（如果角色对应有 workflow stage 定义）
        self._generate_role_output_files(role_id, agent, workflow_results)
        
        # 5. 生成最终响应
        final_response = self._generate_response(
            role=role,
            requirement=requirement,
            skill_results=skill_results,
            agent=agent,
            use_llm=use_llm
        )
        
        # 显示角色完成（沉浸式）
        if immersive_display:
            summary = f"[{role.name}] 已完成任务: {requirement}"
            immersive_display.display_role_complete(
                role_name=role.name,
                summary=summary,
                skills_executed=[r["skill_id"] for r in skill_results]
            )
        
        # 获取执行模式信息（如果之前没有获取）
        if execution_mode_info is None and self.engine.role_manager.skill_library:
            execution_mode_info = ExecutionModeAnalyzer.get_execution_mode_info(
                role=role,
                skill_library=self.engine.role_manager.skill_library,
                environment="cursor"
            )
        
        return {
            "role_id": role_id,
            "requirement": requirement,
            "skills_executed": [r["skill_id"] for r in skill_results],
            "skill_results": skill_results,
            "response": final_response,
            "agent_context": agent.context,
            "execution_mode": execution_mode_info
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
        
        # 注意：独立执行模式不添加工作流阶段信息
        # 这样可以确保角色执行不受工作流状态影响
        # 如果需要工作流阶段信息，应该在 workflow 模式下通过 stage_id 传递
        
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
            return self._format_simple_response(skill_results, role=role)
    
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
    
    def _format_simple_response(self, skill_results: List[Dict[str, Any]], role: Optional[Role] = None) -> str:
        """格式化简单响应（不使用LLM）"""
        role_prefix = f"[{role.name}] " if role else ""
        response_parts = [f"{role_prefix}技能执行结果汇总：\n"] if role else ["技能执行结果汇总：\n"]
        
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
    
    def _generate_role_output_files(
        self,
        role_id: str,
        agent: Agent,
        workflow_results: List[Dict[str, Any]]
    ) -> None:
        """
        为角色执行生成输出文件。
        
        如果角色在 workflow 中有对应的 stage 定义，则生成该 stage 定义的输出文件。
        
        Args:
            role_id: 角色ID
            agent: Agent实例
            workflow_results: 技能执行结果列表
        """
        # 检查是否有 workflow 定义
        if not self.engine.workflow:
            return
        
        # 查找角色对应的 stage
        matching_stage = None
        for stage in self.engine.workflow.stages:
            if stage.role == role_id:
                matching_stage = stage
                break
        
        # 如果没有找到对应的 stage，不生成输出文件
        if not matching_stage:
            return
        
        # 如果没有输出定义，不生成文件
        if not matching_stage.outputs:
            return
        
        # 使用 AgentOrchestrator 的输出生成逻辑
        try:
            self.orchestrator._generate_stage_output_files(
                stage=matching_stage,
                agent=agent,
                workflow_results=workflow_results,
                immersive=False  # role-execute 模式不需要沉浸式显示
            )
        except Exception as e:
            # 输出文件生成失败不应该阻止角色执行完成
            import warnings
            warnings.warn(f"Failed to generate output files for role {role_id}: {e}")


