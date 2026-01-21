"""
Team Template Library for preset industry team configurations.
Following Single Responsibility Principle - handles team template management only.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import json
from difflib import SequenceMatcher


@dataclass
class RoleTemplate:
    """Template for a role definition"""
    id: str
    name: str
    description: str
    domain: str
    responsibility: str
    skills: List[str] = field(default_factory=list)
    constraints: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "responsibility": self.responsibility,
            "skills": self.skills,
            "constraints": self.constraints
        }


@dataclass
class WorkflowStageTemplate:
    """Template for a workflow stage"""
    id: str
    name: str
    role: str  # Role ID
    order: int
    outputs: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "order": self.order,
            "outputs": self.outputs
        }


@dataclass
class TeamTemplate:
    """
    A complete team template including roles, skills, and workflow pattern.
    
    Team templates provide preset configurations for common team structures
    that can be used as starting points for SOP-based team generation.
    """
    id: str
    name: str
    description: str
    industry: str  # "agile", "devops", "product", "startup", "enterprise"
    workflow_pattern: str  # "waterfall", "agile", "kanban", "lean"
    roles: List[RoleTemplate] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)  # Required skill IDs
    stages: List[WorkflowStageTemplate] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "industry": self.industry,
            "workflow_pattern": self.workflow_pattern,
            "roles": [r.to_dict() for r in self.roles],
            "skills": self.skills,
            "stages": [s.to_dict() for s in self.stages],
            "tags": self.tags,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeamTemplate':
        roles = [
            RoleTemplate(
                id=r["id"],
                name=r["name"],
                description=r.get("description", ""),
                domain=r.get("domain", "general"),
                responsibility=r.get("responsibility", ""),
                skills=r.get("skills", []),
                constraints=r.get("constraints", {})
            )
            for r in data.get("roles", [])
        ]
        
        stages = [
            WorkflowStageTemplate(
                id=s["id"],
                name=s["name"],
                role=s["role"],
                order=s.get("order", 0),
                outputs=s.get("outputs", [])
            )
            for s in data.get("stages", [])
        ]
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            industry=data.get("industry", "general"),
            workflow_pattern=data.get("workflow_pattern", "agile"),
            roles=roles,
            skills=data.get("skills", []),
            stages=stages,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )


class TeamTemplateLibrary:
    """
    Library of team templates for different industries and use cases.
    
    Provides:
    1. Loading templates from YAML files
    2. Searching templates by query or industry
    3. Built-in preset templates
    4. Template customization
    """
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize template library.
        
        Args:
            templates_dir: Optional directory containing template YAML files
        """
        self.templates: Dict[str, TeamTemplate] = {}
        self.templates_dir = templates_dir
        
        # Load built-in templates
        self._load_builtin_templates()
        
        # Load custom templates from directory
        if templates_dir and templates_dir.exists():
            self.load_templates_from_dir(templates_dir)
    
    def _load_builtin_templates(self):
        """Load built-in preset templates"""
        # Agile Scrum Team
        self.templates["agile_scrum"] = TeamTemplate(
            id="agile_scrum",
            name="敏捷Scrum团队",
            description="标准的Scrum敏捷开发团队，包含产品负责人、Scrum Master和开发团队",
            industry="agile",
            workflow_pattern="agile",
            roles=[
                RoleTemplate(
                    id="product_owner",
                    name="Product Owner",
                    description="产品负责人，负责产品愿景和需求优先级",
                    domain="product",
                    responsibility="定义产品愿景，管理产品待办列表，确定需求优先级",
                    skills=["requirements_analysis"],
                    constraints={
                        "allowed_actions": ["define_requirements", "prioritize_backlog", "accept_user_stories"],
                        "forbidden_actions": ["write_code", "deploy_system"]
                    }
                ),
                RoleTemplate(
                    id="scrum_master",
                    name="Scrum Master",
                    description="Scrum Master，负责流程管理和障碍清除",
                    domain="process",
                    responsibility="促进Scrum流程，清除障碍，保护团队",
                    skills=["quality_assurance"],
                    constraints={
                        "allowed_actions": ["facilitate_meetings", "remove_blockers", "coach_team"],
                        "forbidden_actions": ["assign_tasks", "make_technical_decisions"]
                    }
                ),
                RoleTemplate(
                    id="developer",
                    name="Developer",
                    description="开发人员，负责实现用户故事",
                    domain="fullstack",
                    responsibility="设计和实现软件功能，编写测试，维护代码质量",
                    skills=["python_engineering", "test_driven_development", "system_design"],
                    constraints={
                        "allowed_actions": ["write_code", "write_tests", "design_architecture"],
                        "forbidden_actions": ["change_requirements", "skip_code_review"]
                    }
                ),
                RoleTemplate(
                    id="qa_engineer",
                    name="QA Engineer",
                    description="质量保证工程师，负责测试和质量门控",
                    domain="qa",
                    responsibility="编写测试用例，执行测试，确保质量标准",
                    skills=["quality_assurance", "test_driven_development"],
                    constraints={
                        "allowed_actions": ["write_tests", "run_tests", "report_bugs"],
                        "forbidden_actions": ["skip_testing", "approve_without_tests"]
                    }
                )
            ],
            skills=["requirements_analysis", "system_design", "python_engineering", "test_driven_development", "quality_assurance"],
            stages=[
                WorkflowStageTemplate(id="sprint_planning", name="Sprint计划", role="product_owner", order=1),
                WorkflowStageTemplate(id="design", name="设计", role="developer", order=2),
                WorkflowStageTemplate(id="implementation", name="实现", role="developer", order=3),
                WorkflowStageTemplate(id="testing", name="测试", role="qa_engineer", order=4),
                WorkflowStageTemplate(id="review", name="评审", role="scrum_master", order=5)
            ],
            tags=["agile", "scrum", "sprint", "team"]
        )
        
        # DevOps Pipeline Team
        self.templates["devops_pipeline"] = TeamTemplate(
            id="devops_pipeline",
            name="DevOps流水线团队",
            description="专注于CI/CD和自动化的DevOps团队",
            industry="devops",
            workflow_pattern="kanban",
            roles=[
                RoleTemplate(
                    id="devops_engineer",
                    name="DevOps Engineer",
                    description="DevOps工程师，负责CI/CD流水线和基础设施",
                    domain="devops",
                    responsibility="构建和维护CI/CD流水线，管理基础设施即代码",
                    skills=["python_engineering", "system_design"],
                    constraints={
                        "allowed_actions": ["configure_pipeline", "deploy_infrastructure", "monitor_systems"],
                        "forbidden_actions": ["skip_security_checks", "deploy_without_tests"]
                    }
                ),
                RoleTemplate(
                    id="sre_engineer",
                    name="SRE Engineer",
                    description="站点可靠性工程师，负责系统可靠性和监控",
                    domain="sre",
                    responsibility="确保系统可靠性，实施监控和告警，管理事件响应",
                    skills=["system_design", "quality_assurance"],
                    constraints={
                        "allowed_actions": ["setup_monitoring", "respond_incidents", "define_slos"],
                        "forbidden_actions": ["ignore_alerts", "skip_postmortem"]
                    }
                ),
                RoleTemplate(
                    id="security_engineer",
                    name="Security Engineer",
                    description="安全工程师，负责安全扫描和合规",
                    domain="security",
                    responsibility="实施安全扫描，确保合规，管理漏洞",
                    skills=["quality_assurance"],
                    constraints={
                        "allowed_actions": ["security_scan", "vulnerability_assessment", "compliance_check"],
                        "forbidden_actions": ["bypass_security", "ignore_vulnerabilities"]
                    }
                )
            ],
            skills=["system_design", "python_engineering", "quality_assurance"],
            stages=[
                WorkflowStageTemplate(id="code_commit", name="代码提交", role="devops_engineer", order=1),
                WorkflowStageTemplate(id="build", name="构建", role="devops_engineer", order=2),
                WorkflowStageTemplate(id="security_scan", name="安全扫描", role="security_engineer", order=3),
                WorkflowStageTemplate(id="deploy_staging", name="部署到测试环境", role="devops_engineer", order=4),
                WorkflowStageTemplate(id="deploy_production", name="部署到生产环境", role="sre_engineer", order=5)
            ],
            tags=["devops", "cicd", "automation", "infrastructure"]
        )
        
        # Product Discovery Team
        self.templates["product_discovery"] = TeamTemplate(
            id="product_discovery",
            name="产品发现团队",
            description="专注于产品发现和用户研究的团队",
            industry="product",
            workflow_pattern="lean",
            roles=[
                RoleTemplate(
                    id="product_manager",
                    name="Product Manager",
                    description="产品经理，负责产品战略和路线图",
                    domain="product",
                    responsibility="定义产品战略，管理产品路线图，协调跨职能团队",
                    skills=["requirements_analysis"],
                    constraints={
                        "allowed_actions": ["define_strategy", "manage_roadmap", "stakeholder_communication"],
                        "forbidden_actions": ["write_code", "make_technical_decisions"]
                    }
                ),
                RoleTemplate(
                    id="ux_researcher",
                    name="UX Researcher",
                    description="用户体验研究员，负责用户研究和洞察",
                    domain="design",
                    responsibility="进行用户研究，分析用户行为，提供设计洞察",
                    skills=["requirements_analysis"],
                    constraints={
                        "allowed_actions": ["conduct_research", "analyze_data", "present_insights"],
                        "forbidden_actions": ["make_product_decisions", "skip_user_validation"]
                    }
                ),
                RoleTemplate(
                    id="ux_designer",
                    name="UX Designer",
                    description="用户体验设计师，负责交互设计和原型",
                    domain="design",
                    responsibility="设计用户界面，创建原型，进行可用性测试",
                    skills=["system_design", "schema_design"],
                    constraints={
                        "allowed_actions": ["design_interfaces", "create_prototypes", "usability_testing"],
                        "forbidden_actions": ["skip_user_testing", "ignore_research"]
                    }
                ),
                RoleTemplate(
                    id="data_analyst",
                    name="Data Analyst",
                    description="数据分析师，负责数据分析和指标追踪",
                    domain="analytics",
                    responsibility="分析产品数据，追踪关键指标，提供数据驱动的建议",
                    skills=["requirements_analysis", "quality_assurance"],
                    constraints={
                        "allowed_actions": ["analyze_metrics", "create_reports", "data_modeling"],
                        "forbidden_actions": ["manipulate_data", "skip_validation"]
                    }
                )
            ],
            skills=["requirements_analysis", "system_design", "schema_design", "quality_assurance"],
            stages=[
                WorkflowStageTemplate(id="discovery", name="发现", role="product_manager", order=1),
                WorkflowStageTemplate(id="research", name="用户研究", role="ux_researcher", order=2),
                WorkflowStageTemplate(id="ideation", name="创意设计", role="ux_designer", order=3),
                WorkflowStageTemplate(id="validation", name="验证", role="data_analyst", order=4),
                WorkflowStageTemplate(id="iteration", name="迭代", role="product_manager", order=5)
            ],
            tags=["product", "discovery", "ux", "research"]
        )
        
        # Startup MVP Team
        self.templates["startup_mvp"] = TeamTemplate(
            id="startup_mvp",
            name="创业MVP团队",
            description="精简的创业团队，专注于快速构建MVP",
            industry="startup",
            workflow_pattern="lean",
            roles=[
                RoleTemplate(
                    id="tech_lead",
                    name="Tech Lead",
                    description="技术负责人，负责技术决策和架构",
                    domain="fullstack",
                    responsibility="做出技术决策，设计系统架构，指导团队",
                    skills=["system_design", "python_engineering", "schema_design"],
                    constraints={
                        "allowed_actions": ["design_architecture", "make_tech_decisions", "code_review"],
                        "forbidden_actions": ["ignore_tech_debt", "skip_security"]
                    }
                ),
                RoleTemplate(
                    id="fullstack_dev",
                    name="Fullstack Developer",
                    description="全栈开发者，负责前后端开发",
                    domain="fullstack",
                    responsibility="实现全栈功能，从数据库到用户界面",
                    skills=["python_engineering", "test_driven_development"],
                    constraints={
                        "allowed_actions": ["write_code", "write_tests", "deploy"],
                        "forbidden_actions": ["skip_tests", "bypass_review"]
                    }
                ),
                RoleTemplate(
                    id="product_lead",
                    name="Product Lead",
                    description="产品负责人，负责需求和优先级",
                    domain="product",
                    responsibility="定义MVP范围，管理需求优先级，与用户沟通",
                    skills=["requirements_analysis"],
                    constraints={
                        "allowed_actions": ["define_mvp", "prioritize_features", "user_interviews"],
                        "forbidden_actions": ["scope_creep", "skip_validation"]
                    }
                )
            ],
            skills=["requirements_analysis", "system_design", "python_engineering", "test_driven_development"],
            stages=[
                WorkflowStageTemplate(id="mvp_definition", name="MVP定义", role="product_lead", order=1),
                WorkflowStageTemplate(id="architecture", name="架构设计", role="tech_lead", order=2),
                WorkflowStageTemplate(id="development", name="快速开发", role="fullstack_dev", order=3),
                WorkflowStageTemplate(id="launch", name="发布", role="tech_lead", order=4)
            ],
            tags=["startup", "mvp", "lean", "fast"]
        )
        
        # Standard Delivery Team (matches existing standard-delivery)
        self.templates["standard_delivery"] = TeamTemplate(
            id="standard_delivery",
            name="标准交付团队",
            description="标准的软件交付团队，覆盖完整的开发生命周期",
            industry="enterprise",
            workflow_pattern="agile",
            roles=[
                RoleTemplate(
                    id="product_analyst",
                    name="Product Analyst",
                    description="产品分析师，负责需求分析和范围定义",
                    domain="product",
                    responsibility="分析用户需求，定义范围，创建需求文档",
                    skills=["requirements_analysis"],
                    constraints={
                        "allowed_actions": ["define_requirements", "define_scope", "create_checklist"],
                        "forbidden_actions": ["write_code", "approve_architecture"]
                    }
                ),
                RoleTemplate(
                    id="system_architect",
                    name="System Architect",
                    description="系统架构师，负责架构设计和技术决策",
                    domain="architecture",
                    responsibility="设计系统架构，定义数据模型，做出技术决策",
                    skills=["system_design", "schema_design"],
                    constraints={
                        "allowed_actions": ["design_architecture", "define_schemas", "make_decisions"],
                        "forbidden_actions": ["write_implementation", "skip_requirements"]
                    }
                ),
                RoleTemplate(
                    id="core_framework_engineer",
                    name="Core Framework Engineer",
                    description="核心框架工程师，负责代码实现",
                    domain="backend",
                    responsibility="实现核心功能，编写测试，维护代码质量",
                    skills=["python_engineering", "test_driven_development"],
                    constraints={
                        "allowed_actions": ["write_code", "write_tests", "implement_schemas"],
                        "forbidden_actions": ["skip_architecture", "skip_tests"]
                    }
                ),
                RoleTemplate(
                    id="qa_reviewer",
                    name="QA Reviewer",
                    description="QA评审员，负责质量验证",
                    domain="qa",
                    responsibility="运行质量门控，验证实现，生成报告",
                    skills=["quality_assurance"],
                    constraints={
                        "allowed_actions": ["run_quality_gates", "validate_implementation", "generate_reports"],
                        "forbidden_actions": ["skip_validation", "bypass_gates"]
                    }
                )
            ],
            skills=["requirements_analysis", "system_design", "schema_design", "python_engineering", "test_driven_development", "quality_assurance"],
            stages=[
                WorkflowStageTemplate(id="requirements", name="需求分析", role="product_analyst", order=1,
                                      outputs=[{"name": "REQUIREMENTS.md", "type": "document"}]),
                WorkflowStageTemplate(id="architecture", name="架构设计", role="system_architect", order=2,
                                      outputs=[{"name": "ARCHITECTURE.md", "type": "document"}]),
                WorkflowStageTemplate(id="implementation", name="实现", role="core_framework_engineer", order=3,
                                      outputs=[{"name": "src/", "type": "code"}]),
                WorkflowStageTemplate(id="validation", name="验证", role="qa_reviewer", order=4,
                                      outputs=[{"name": "validation_report.json", "type": "report"}])
            ],
            tags=["standard", "delivery", "enterprise", "fullcycle"]
        )
    
    def load_templates_from_dir(self, directory: Path):
        """Load templates from a directory of YAML files"""
        for yaml_file in directory.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
                if data:
                    template = TeamTemplate.from_dict(data)
                    self.templates[template.id] = template
            except Exception as e:
                print(f"Warning: Failed to load template from {yaml_file}: {e}")
    
    def get_by_id(self, template_id: str) -> Optional[TeamTemplate]:
        """Get a template by ID"""
        return self.templates.get(template_id)
    
    def list_all(self) -> List[TeamTemplate]:
        """List all templates"""
        return list(self.templates.values())
    
    def list_by_industry(self, industry: str) -> List[TeamTemplate]:
        """List templates by industry"""
        return [t for t in self.templates.values() if t.industry == industry]
    
    def search(
        self, 
        query: str, 
        industry: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[TeamTemplate]:
        """
        Search templates by query, optionally filtered by industry and tags.
        
        Args:
            query: Search query (matches name, description, tags)
            industry: Optional industry filter
            tags: Optional list of tags to filter by
            limit: Maximum number of results
            
        Returns:
            List of matching templates sorted by relevance
        """
        results = []
        query_lower = query.lower()
        
        for template in self.templates.values():
            # Apply filters
            if industry and template.industry != industry:
                continue
            
            if tags and not any(tag in template.tags for tag in tags):
                continue
            
            # Calculate match score
            score = 0.0
            
            # Name match
            name_similarity = SequenceMatcher(None, query_lower, template.name.lower()).ratio()
            score += name_similarity * 0.4
            
            # Description match
            if query_lower in template.description.lower():
                score += 0.3
            
            # Tag match
            for tag in template.tags:
                if query_lower in tag.lower():
                    score += 0.15
            
            # Keyword match in roles
            for role in template.roles:
                if query_lower in role.name.lower() or query_lower in role.description.lower():
                    score += 0.1
            
            if score > 0.1:  # Minimum threshold
                results.append((score, template))
        
        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [t for _, t in results[:limit]]
    
    def match_sop_keywords(self, sop_content: str) -> List[TeamTemplate]:
        """
        Match templates based on SOP content keywords.
        
        Args:
            sop_content: Content of an SOP document
            
        Returns:
            List of matching templates sorted by relevance
        """
        content_lower = sop_content.lower()
        scores = []
        
        # Define keyword mappings
        industry_keywords = {
            "agile": ["sprint", "scrum", "agile", "backlog", "user story", "iteration"],
            "devops": ["ci/cd", "pipeline", "deploy", "kubernetes", "docker", "infrastructure"],
            "product": ["discovery", "ux", "user research", "prototype", "validation"],
            "startup": ["mvp", "lean", "startup", "fast", "iterate"],
            "enterprise": ["waterfall", "requirements", "architecture", "validation", "compliance"]
        }
        
        for template in self.templates.values():
            score = 0.0
            
            # Check industry keywords
            industry_kws = industry_keywords.get(template.industry, [])
            for kw in industry_kws:
                if kw in content_lower:
                    score += 0.2
            
            # Check role names in SOP
            for role in template.roles:
                if role.name.lower() in content_lower:
                    score += 0.15
                if role.responsibility.lower() in content_lower:
                    score += 0.1
            
            # Check stage names
            for stage in template.stages:
                if stage.name.lower() in content_lower:
                    score += 0.1
            
            if score > 0:
                scores.append((score, template))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scores[:5]]
    
    def generate_team_config(
        self, 
        template: TeamTemplate,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete team configuration from a template.
        
        Args:
            template: The team template to use
            customizations: Optional customizations to apply
            
        Returns:
            Complete team configuration dict
        """
        config = {
            "team_id": template.id,
            "team_name": template.name,
            "description": template.description,
            "role_schema": {
                "schema_version": "1.0",
                "roles": [role.to_dict() for role in template.roles]
            },
            "workflow_schema": {
                "schema_version": "1.0",
                "workflow": {
                    "id": f"{template.id}_workflow",
                    "name": f"{template.name} 工作流",
                    "description": f"基于{template.name}模板的工作流",
                    "stages": [
                        {
                            "id": stage.id,
                            "name": stage.name,
                            "role": stage.role,
                            "order": stage.order,
                            "prerequisites": [],
                            "entry_criteria": [],
                            "exit_criteria": [],
                            "quality_gates": [],
                            "outputs": stage.outputs
                        }
                        for stage in template.stages
                    ]
                }
            },
            "required_skills": template.skills,
            "metadata": {
                "template_id": template.id,
                "industry": template.industry,
                "workflow_pattern": template.workflow_pattern,
                "tags": template.tags
            }
        }
        
        # Apply customizations
        if customizations:
            if "team_name" in customizations:
                config["team_name"] = customizations["team_name"]
            if "description" in customizations:
                config["description"] = customizations["description"]
            if "additional_roles" in customizations:
                for role_data in customizations["additional_roles"]:
                    config["role_schema"]["roles"].append(role_data)
            if "additional_stages" in customizations:
                for stage_data in customizations["additional_stages"]:
                    config["workflow_schema"]["workflow"]["stages"].append(stage_data)
        
        return config
    
    def save_template(self, template: TeamTemplate, output_dir: Path):
        """
        Save a template to a YAML file.
        
        Args:
            template: Template to save
            output_dir: Directory to save to
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{template.id}.yaml"
        
        data = template.to_dict()
        with output_file.open('w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def add_custom_template(self, template: TeamTemplate):
        """Add a custom template to the library"""
        self.templates[template.id] = template
    
    def remove_template(self, template_id: str) -> bool:
        """Remove a template from the library"""
        if template_id in self.templates:
            del self.templates[template_id]
            return True
        return False
