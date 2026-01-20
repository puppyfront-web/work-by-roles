"""
Task router for task assignment and feedback handling.
Following Single Responsibility Principle - handles task routing only.
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING

from .models import Task, TaskAssignment, Role

if TYPE_CHECKING:
    from .role_manager import RoleManager


class TaskRouter:
    """
    任务路由器 - 负责任务分配和反馈处理
    
    核心功能：
    1. 自动选择最合适的角色
    2. 让角色判断是否能处理任务（博弈反馈）
    3. 如果拒绝，建议替代角色
    4. 记录任务分配历史
    """
    
    def __init__(self, role_manager: 'RoleManager'):
        """
        初始化任务路由器
        
        Args:
            role_manager: 角色管理器，用于获取角色信息
        """
        self.role_manager = role_manager
        self.task_history: List[TaskAssignment] = []
    
    def assign_task(
        self, 
        task: Task, 
        target_role_id: Optional[str] = None
    ) -> TaskAssignment:
        """
        分配任务给角色，角色会判断是否接受
        
        Args:
            task: 要分配的任务
            target_role_id: 目标角色ID（如果为None，则自动选择）
        
        Returns:
            任务分配结果
        """
        # 1. 如果没有指定角色，自动选择最合适的角色
        if not target_role_id:
            target_role_id = self._select_best_role(task)
        
        role = self.role_manager.get_role(target_role_id)
        if not role:
            raise ValueError(f"Role {target_role_id} not found")
        
        # 2. 让角色判断是否能处理该任务（博弈反馈）
        can_handle, feedback = role.evaluate_task(task, self.role_manager)
        
        if can_handle:
            # 角色接受任务
            assignment = TaskAssignment(
                task_id=task.id,
                assigned_role=target_role_id,
                status="accepted",
                feedback=feedback or "Task accepted"
            )
            task.status = "accepted"
            task.assigned_role = target_role_id
        else:
            # 角色拒绝任务，尝试澄清或建议替代角色
            # Check if multiple roles rejected (P1 optimization: Clarifier Role)
            rejected_count = sum(1 for a in self.task_history if a.task_id == task.id and a.status == "rejected")
            
            if rejected_count >= 2:
                # Multiple roles rejected, trigger clarifier
                clarifier_result = self._trigger_clarifier(task)
                if clarifier_result:
                    assignment = clarifier_result
                else:
                    # Fallback to suggestion
                    suggested_role = self._suggest_alternative_role(task, role)
                    assignment = TaskAssignment(
                        task_id=task.id,
                        assigned_role=target_role_id,
                        status="rejected",
                        feedback=feedback or "Task not suitable for this role",
                        suggested_role=suggested_role
                    )
            else:
                # Single rejection, suggest alternative
                suggested_role = self._suggest_alternative_role(task, role)
                assignment = TaskAssignment(
                    task_id=task.id,
                    assigned_role=target_role_id,
                    status="rejected",
                    feedback=feedback or "Task not suitable for this role",
                    suggested_role=suggested_role
                )
            
            task.status = "rejected"
            task.rejection_reason = feedback
            if assignment.suggested_role:
                task.reassigned_to = assignment.suggested_role
        
        self.task_history.append(assignment)
        return assignment
    
    def _select_best_role(self, task: Task) -> str:
        """
        根据任务描述自动选择最合适的角色
        
        Args:
            task: 任务对象
        
        Returns:
            最合适的角色ID
        """
        available_roles = list(self.role_manager.roles.values())
        if not available_roles:
            raise ValueError("No available roles")
        
        best_match = None
        best_score = 0.0
        
        for role in available_roles:
            score = role.match_score(task.description, task.category, self.role_manager)
            if score > best_score:
                best_score = score
                best_match = role
        
        if not best_match:
            # Fallback: 返回第一个可用角色
            return available_roles[0].id
        
        return best_match.id
    
    def _suggest_alternative_role(self, task: Task, rejected_role: Role) -> Optional[str]:
        """
        建议替代角色
        
        Args:
            task: 任务对象
            rejected_role: 拒绝任务的角色
        
        Returns:
            建议的角色ID，如果没有则返回None
        """
        available_roles = [
            r for r in self.role_manager.roles.values() 
            if r.id != rejected_role.id
        ]
        
        if not available_roles:
            return None
        
        # 找到最匹配的角色
        best_match = None
        best_score = 0.0
        
        for role in available_roles:
            if role.can_handle_task(task.description, self.role_manager):
                score = role.match_score(task.description, task.category, self.role_manager)
                if score > best_score:
                    best_score = score
                    best_match = role
        
        return best_match.id if best_match else None
    
    def get_task_history(self, role_id: Optional[str] = None) -> List[TaskAssignment]:
        """
        获取任务分配历史
        
        Args:
            role_id: 可选的角色ID，用于过滤
        
        Returns:
            任务分配历史列表
        """
        if role_id:
            return [a for a in self.task_history if a.assigned_role == role_id]
        return self.task_history.copy()
    
    def get_rejection_rate(self, role_id: str) -> float:
        """
        获取角色的任务拒绝率
        
        Args:
            role_id: 角色ID
        
        Returns:
            拒绝率（0.0-1.0）
        """
        role_assignments = [a for a in self.task_history if a.assigned_role == role_id]
        if not role_assignments:
            return 0.0
        
        rejected = sum(1 for a in role_assignments if a.status == "rejected")
        return rejected / len(role_assignments)
    
    def _trigger_clarifier(self, task: Task) -> Optional[TaskAssignment]:
        """
        Trigger clarifier role when multiple roles reject a task (P1 optimization).
        
        Args:
            task: Task that was rejected
        
        Returns:
            TaskAssignment from clarifier, or None if clarifier not available
        """
        # Check if clarifier role exists
        clarifier_role = self.role_manager.get_role("clarifier")
        if not clarifier_role:
            return None
        
        # Clarifier analyzes the task and asks clarifying questions
        # This is a simplified implementation - can be enhanced with LLM
        questions = [
            f"Can you clarify what '{task.description}' means?",
            "What is the expected outcome?",
            "What domain does this task belong to?"
        ]
        
        # Create a clarification task assignment
        assignment = TaskAssignment(
            task_id=task.id,
            assigned_role="clarifier",
            status="accepted",
            feedback=f"Clarifier role activated. Questions: {'; '.join(questions)}"
        )
        
        return assignment

