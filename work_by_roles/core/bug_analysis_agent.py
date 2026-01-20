"""
Bug Analysis Agent for analyzing bugs and assigning to appropriate roles.
Following Single Responsibility Principle - handles bug analysis and assignment only.
"""

from typing import Dict, List, Optional, Any
from .exceptions import WorkflowError
from .workflow_engine import WorkflowEngine
from .task_router import TaskRouter
from .models import Task


class BugAnalysisAgent:
    """
    Bug分析Agent：分析bug并分配给合适的角色
    
    核心功能：
    1. 分析bug描述，提取关键信息
    2. 定位bug可能的位置和原因
    3. 分配给最合适的角色进行修复
    4. 跟踪bug修复进度
    """
    
    def __init__(self, engine: 'WorkflowEngine', llm_client: Optional[Any] = None):
        """
        初始化BugAnalysisAgent
        
        Args:
            engine: WorkflowEngine实例
            llm_client: 可选的LLM客户端，用于智能分析
        """
        self.engine = engine
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
        self.task_router = TaskRouter(engine.role_manager) if engine.role_manager else None
    
    def analyze_bug(self, bug_description: str, use_llm: Optional[bool] = None) -> Dict[str, Any]:
        """
        分析bug描述，提取关键信息
        
        Args:
            bug_description: Bug描述
            use_llm: 是否使用LLM（None=自动选择）
        
        Returns:
            {
                "severity": str,           # 严重程度：critical, high, medium, low
                "category": str,           # Bug分类：frontend, backend, logic, etc.
                "affected_components": List[str],  # 受影响的组件
                "root_cause": str,         # 可能的原因
                "suggested_fix": str,      # 修复建议
                "assigned_role": str,      # 建议分配的角色
                "confidence": float        # 分析置信度
            }
        """
        if use_llm is None:
            use_llm = self.llm_enabled and len(bug_description) > 50
        
        if use_llm and self.llm_enabled:
            return self._analyze_with_llm(bug_description)
        else:
            return self._analyze_with_rules(bug_description)
    
    def _analyze_with_llm(self, bug_description: str) -> Dict[str, Any]:
        """使用LLM分析bug"""
        try:
            prompt = self._build_analysis_prompt(bug_description)
            response = self._call_llm(prompt)
            result = self._parse_llm_response(response)
            return result
        except Exception as e:
            # LLM失败时回退到规则引擎
            result = self._analyze_with_rules(bug_description)
            result["confidence"] = result.get("confidence", 0.5) * 0.8  # 降低置信度
            return result
    
    def _build_analysis_prompt(self, bug_description: str) -> str:
        """构建LLM分析提示"""
        prompt = f"""你是一个bug分析专家。根据bug描述，分析bug的关键信息。

Bug描述："{bug_description}"

请分析并返回JSON格式：
{{
    "severity": "critical" | "high" | "medium" | "low",
    "category": "frontend" | "backend" | "logic" | "data" | "ui" | "api" | "other",
    "affected_components": ["component1", "component2", ...],
    "root_cause": "可能的原因分析",
    "suggested_fix": "修复建议",
    "assigned_role": "建议的角色ID",
    "confidence": 0.85
}}

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
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        import json
        import re
        
        json_match = re.search(r'\{[^{}]*"severity"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 回退到规则引擎
        return self._analyze_with_rules("")
    
    def _analyze_with_rules(self, bug_description: str) -> Dict[str, Any]:
        """使用规则引擎分析bug"""
        bug_lower = bug_description.lower()
        
        # 严重程度关键词
        critical_keywords = ["崩溃", "无法启动", "数据丢失", "crash", "down", "critical"]
        high_keywords = ["错误", "失败", "不工作", "error", "fail", "broken"]
        medium_keywords = ["问题", "异常", "issue", "problem"]
        
        # 分类关键词
        frontend_keywords = ["前端", "ui", "界面", "页面", "样式", "frontend", "ui", "css"]
        backend_keywords = ["后端", "api", "服务", "数据库", "backend", "server", "database"]
        logic_keywords = ["逻辑", "算法", "计算", "logic", "algorithm"]
        
        # 确定严重程度
        if any(kw in bug_lower for kw in critical_keywords):
            severity = "critical"
        elif any(kw in bug_lower for kw in high_keywords):
            severity = "high"
        elif any(kw in bug_lower for kw in medium_keywords):
            severity = "medium"
        else:
            severity = "low"
        
        # 确定分类
        if any(kw in bug_lower for kw in frontend_keywords):
            category = "frontend"
            assigned_role = self._find_role_by_keywords(["frontend", "ui", "前端"])
        elif any(kw in bug_lower for kw in backend_keywords):
            category = "backend"
            assigned_role = self._find_role_by_keywords(["backend", "后端", "api"])
        elif any(kw in bug_lower for kw in logic_keywords):
            category = "logic"
            assigned_role = self._find_role_by_keywords(["developer", "开发", "engineer"])
        else:
            category = "other"
            assigned_role = self._find_role_by_keywords(["developer", "开发"])
        
        return {
            "severity": severity,
            "category": category,
            "affected_components": [],
            "root_cause": "需要进一步分析",
            "suggested_fix": "需要查看代码和日志",
            "assigned_role": assigned_role,
            "confidence": 0.6
        }
    
    def _find_role_by_keywords(self, keywords: List[str]) -> Optional[str]:
        """根据关键词查找角色"""
        if not self.engine.role_manager:
            return None
        
        for role_id, role in self.engine.role_manager.roles.items():
            role_name_lower = role.name.lower()
            role_desc_lower = role.description.lower()
            if any(kw.lower() in role_name_lower or kw.lower() in role_desc_lower for kw in keywords):
                return role_id
        
        # 返回第一个可用角色
        if self.engine.role_manager.roles:
            return list(self.engine.role_manager.roles.keys())[0]
        return None
    
    def assign_bug(self, bug_description: str, analysis_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分配bug给合适的角色
        
        Args:
            bug_description: Bug描述
            analysis_result: 可选的bug分析结果
        
        Returns:
            分配结果
        """
        if not analysis_result:
            analysis_result = self.analyze_bug(bug_description)
        
        if not self.task_router:
            return {
                "success": False,
                "error": "TaskRouter未初始化"
            }
        
        # 创建任务
        task = Task(
            id=f"bug_{hash(bug_description) % 10000}",
            description=bug_description,
            category=analysis_result.get("category", "other"),
            priority=self._get_priority(analysis_result.get("severity", "low"))
        )
        
        # 分配任务
        assigned_role = analysis_result.get("assigned_role")
        assignment = self.task_router.assign_task(task, assigned_role)
        
        return {
            "success": assignment.status == "accepted",
            "task_id": task.id,
            "assigned_role": assignment.assigned_role,
            "status": assignment.status,
            "feedback": assignment.feedback,
            "suggested_role": assignment.suggested_role,
            "analysis": analysis_result
        }
    
    def _get_priority(self, severity: str) -> int:
        """根据严重程度返回优先级"""
        priority_map = {
            "critical": 10,
            "high": 7,
            "medium": 4,
            "low": 1
        }
        return priority_map.get(severity, 1)
