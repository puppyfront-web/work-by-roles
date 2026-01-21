"""
SOP (Standard Operating Procedure) importer.
Converts SOP documents into Roles/Skills/Workflow configurations.
Following Single Responsibility Principle - handles SOP import only.

Enhanced with LLM deep analysis for better extraction accuracy.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import re
import yaml
import json

from .exceptions import WorkflowError


@dataclass
class SOPAnalysis:
    """Result of SOP deep analysis"""
    # Extracted entities
    roles: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    workflow_stages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Analysis metadata
    document_type: str = "unknown"  # "process", "procedure", "guideline", "standard"
    industry: str = "general"  # "agile", "devops", "product", etc.
    complexity: str = "medium"  # "simple", "medium", "complex"
    
    # Quality indicators
    confidence_score: float = 0.0
    extraction_method: str = "rule_based"  # "rule_based", "llm", "hybrid"
    warnings: List[str] = field(default_factory=list)
    
    # Relationships
    role_skill_mapping: Dict[str, List[str]] = field(default_factory=dict)  # role_id -> skill_ids
    stage_dependencies: Dict[str, List[str]] = field(default_factory=dict)  # stage_id -> dependency_stage_ids
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "roles": self.roles,
            "skills": self.skills,
            "workflow_stages": self.workflow_stages,
            "document_type": self.document_type,
            "industry": self.industry,
            "complexity": self.complexity,
            "confidence_score": self.confidence_score,
            "extraction_method": self.extraction_method,
            "warnings": self.warnings,
            "role_skill_mapping": self.role_skill_mapping,
            "stage_dependencies": self.stage_dependencies
        }


class SOPImporter:
    """
    Imports SOP documents and generates role/skill/workflow configurations.
    
    This is a simplified implementation that extracts structured information
    from markdown documents. Can be enhanced with LLM for better extraction.
    """
    
    def __init__(self, llm_client: Optional[Any] = None, template_library: Optional[Any] = None):
        """
        Initialize SOP importer.
        
        Args:
            llm_client: Optional LLM client for enhanced extraction
            template_library: Optional TeamTemplateLibrary for template matching
        """
        self.llm_client = llm_client
        self.llm_enabled = llm_client is not None
        self.template_library = template_library
    
    # ========================================================================
    # Enhanced LLM-based Analysis Methods
    # ========================================================================
    
    def deep_analyze(self, sop_content: str, use_llm: Optional[bool] = None) -> SOPAnalysis:
        """
        Perform deep analysis of SOP content using LLM or rule-based methods.
        
        This method provides more comprehensive extraction than import_sop(),
        including relationship mapping and quality indicators.
        
        Args:
            sop_content: SOP document content (markdown or plain text)
            use_llm: Whether to use LLM (None=auto, True=force, False=disable)
            
        Returns:
            SOPAnalysis with extracted entities and metadata
        """
        # Determine extraction method
        if use_llm is None:
            use_llm = self.llm_enabled and len(sop_content) > 100
        
        if use_llm and self.llm_enabled:
            try:
                return self._analyze_with_llm(sop_content)
            except Exception as e:
                # Fall back to rule-based
                analysis = self._analyze_with_rules(sop_content)
                analysis.warnings.append(f"LLM analysis failed, using rule-based: {str(e)}")
                return analysis
        else:
            return self._analyze_with_rules(sop_content)
    
    def _analyze_with_llm(self, sop_content: str) -> SOPAnalysis:
        """Analyze SOP content using LLM"""
        prompt = self._build_analysis_prompt(sop_content)
        response = self._call_llm(prompt)
        return self._parse_llm_analysis(response, sop_content)
    
    def _build_analysis_prompt(self, sop_content: str) -> str:
        """Build LLM prompt for SOP analysis"""
        # Truncate if too long
        max_content_length = 8000
        if len(sop_content) > max_content_length:
            sop_content = sop_content[:max_content_length] + "\n...[内容已截断]..."
        
        prompt = f"""你是一个SOP（标准操作流程）分析专家。请分析以下SOP文档，提取角色、技能和工作流信息。

SOP文档内容：
```
{sop_content}
```

请以JSON格式返回分析结果：
{{
    "document_type": "process|procedure|guideline|standard",
    "industry": "agile|devops|product|startup|enterprise|general",
    "complexity": "simple|medium|complex",
    "roles": [
        {{
            "id": "role_id",
            "name": "角色名称",
            "description": "角色描述",
            "domain": "frontend|backend|fullstack|product|qa|devops|design|general",
            "responsibility": "主要职责",
            "skills": ["skill_id1", "skill_id2"],
            "constraints": {{
                "allowed_actions": ["action1"],
                "forbidden_actions": ["action2"]
            }}
        }}
    ],
    "skills": [
        {{
            "id": "skill_id",
            "name": "技能名称",
            "description": "技能描述",
            "category": "analysis|design|development|testing|operations",
            "skill_type": "cognitive|procedural|hybrid"
        }}
    ],
    "workflow_stages": [
        {{
            "id": "stage_id",
            "name": "阶段名称",
            "role": "负责角色ID",
            "order": 1,
            "dependencies": ["前置阶段ID"],
            "outputs": [
                {{"name": "输出文件名", "type": "document|code|report"}}
            ]
        }}
    ],
    "role_skill_mapping": {{
        "role_id": ["skill_id1", "skill_id2"]
    }},
    "stage_dependencies": {{
        "stage_id": ["dependency_stage_id"]
    }}
}}

注意：
1. 仔细识别文档中隐含的角色和职责
2. 提取工作流的依赖关系
3. 为每个角色分配合适的技能
4. 只返回JSON，不要其他内容"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt"""
        if hasattr(self.llm_client, 'chat'):
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages)
            if isinstance(response, dict):
                return response.get('content', response.get('text', str(response)))
            return str(response)
        elif hasattr(self.llm_client, 'complete'):
            response = self.llm_client.complete(prompt, max_tokens=4000)
            return str(response)
        elif callable(self.llm_client):
            return str(self.llm_client(prompt))
        else:
            raise ValueError("LLM client interface not supported")
    
    def _parse_llm_analysis(self, response: str, sop_content: str) -> SOPAnalysis:
        """Parse LLM response into SOPAnalysis"""
        analysis = SOPAnalysis()
        analysis.extraction_method = "llm"
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                
                analysis.document_type = data.get("document_type", "unknown")
                analysis.industry = data.get("industry", "general")
                analysis.complexity = data.get("complexity", "medium")
                analysis.roles = data.get("roles", [])
                analysis.skills = data.get("skills", [])
                analysis.workflow_stages = data.get("workflow_stages", [])
                analysis.role_skill_mapping = data.get("role_skill_mapping", {})
                analysis.stage_dependencies = data.get("stage_dependencies", {})
                analysis.confidence_score = 0.8  # LLM extraction is generally more confident
            else:
                raise ValueError("No JSON found in response")
                
        except json.JSONDecodeError as e:
            analysis.warnings.append(f"JSON parse error: {str(e)}")
            # Fall back to rule-based
            rule_analysis = self._analyze_with_rules(sop_content)
            analysis.roles = rule_analysis.roles
            analysis.skills = rule_analysis.skills
            analysis.workflow_stages = rule_analysis.workflow_stages
            analysis.confidence_score = 0.5
            analysis.extraction_method = "hybrid"
        
        return analysis
    
    def _analyze_with_rules(self, sop_content: str) -> SOPAnalysis:
        """
        Analyze SOP content using rule-based extraction.
        
        New approach: Skills -> Roles -> Workflow
        1. First extract all skills from SOP (from responsibilities, workflow steps, skill requirements)
        2. Then compose roles from skills (group related skills into roles)
        3. Finally build workflow from skills and roles (create stages based on skills and roles)
        """
        analysis = SOPAnalysis()
        analysis.extraction_method = "rule_based"
        
        # Step 1: Extract all skills first (from various parts of SOP)
        analysis.skills = self._extract_all_skills(sop_content)
        
        # Step 2: Extract role definitions and compose roles from skills
        role_definitions = self._extract_role_definitions(sop_content)
        analysis.roles = self._compose_roles_from_skills(role_definitions, analysis.skills)
        
        # Step 3: Build workflow stages from skills and roles
        workflow = self._build_workflow_from_skills(sop_content, analysis.skills, analysis.roles)
        analysis.workflow_stages = workflow.get("stages", [])
        
        # Infer document type and industry
        analysis.document_type = self._infer_document_type(sop_content)
        analysis.industry = self._infer_industry(sop_content)
        analysis.complexity = self._infer_complexity(sop_content, analysis)
        
        # Build role-skill mapping
        for role in analysis.roles:
            role_id = role.get("id", "")
            skills = role.get("skills", [])
            if role_id and skills:
                analysis.role_skill_mapping[role_id] = skills
        
        # Calculate confidence based on extraction quality
        analysis.confidence_score = self._calculate_confidence(analysis)
        
        return analysis
    
    def _infer_document_type(self, content: str) -> str:
        """Infer document type from content"""
        content_lower = content.lower()
        if any(kw in content_lower for kw in ["流程", "process", "workflow", "步骤"]):
            return "process"
        elif any(kw in content_lower for kw in ["操作规程", "procedure", "操作指南"]):
            return "procedure"
        elif any(kw in content_lower for kw in ["指南", "guideline", "guide"]):
            return "guideline"
        elif any(kw in content_lower for kw in ["标准", "standard", "规范"]):
            return "standard"
        return "unknown"
    
    def _infer_industry(self, content: str) -> str:
        """Infer industry from content"""
        content_lower = content.lower()
        industry_keywords = {
            "agile": ["sprint", "scrum", "敏捷", "backlog", "迭代"],
            "devops": ["ci/cd", "pipeline", "部署", "容器", "kubernetes"],
            "product": ["产品", "用户研究", "discovery", "原型"],
            "startup": ["mvp", "精益", "创业", "startup"],
            "enterprise": ["企业", "合规", "审计", "compliance"]
        }
        
        scores = {}
        for industry, keywords in industry_keywords.items():
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                scores[industry] = score
        
        if scores:
            return max(scores, key=scores.get)
        return "general"
    
    def _infer_complexity(self, content: str, analysis: SOPAnalysis) -> str:
        """Infer complexity from content and analysis"""
        # Based on number of roles, stages, and content length
        role_count = len(analysis.roles)
        stage_count = len(analysis.workflow_stages)
        content_length = len(content)
        
        if role_count <= 2 and stage_count <= 3 and content_length < 2000:
            return "simple"
        elif role_count >= 5 or stage_count >= 6 or content_length > 10000:
            return "complex"
        return "medium"
    
    def _calculate_confidence(self, analysis: SOPAnalysis) -> float:
        """Calculate confidence score for extraction"""
        score = 0.3  # Base score
        
        # More roles found = higher confidence
        if len(analysis.roles) > 0:
            score += 0.2
        if len(analysis.roles) >= 3:
            score += 0.1
        
        # Workflow stages found
        if len(analysis.workflow_stages) > 0:
            score += 0.2
        
        # Skills found
        if len(analysis.skills) > 0:
            score += 0.1
        
        # Role-skill mapping complete
        if analysis.role_skill_mapping:
            score += 0.1
        
        return min(score, 1.0)
    
    def match_template(self, analysis: SOPAnalysis) -> List[Tuple[str, float]]:
        """
        Match SOP analysis to team templates.
        
        Args:
            analysis: SOPAnalysis result
            
        Returns:
            List of (template_id, match_score) tuples sorted by score
        """
        if not self.template_library:
            return []
        
        matches = []
        
        for template in self.template_library.list_all():
            score = 0.0
            
            # Industry match
            if template.industry == analysis.industry:
                score += 0.4
            elif analysis.industry == "general":
                score += 0.2
            
            # Role count similarity
            role_diff = abs(len(template.roles) - len(analysis.roles))
            if role_diff == 0:
                score += 0.2
            elif role_diff <= 2:
                score += 0.1
            
            # Workflow pattern match based on complexity
            if analysis.complexity == "simple" and template.workflow_pattern == "lean":
                score += 0.2
            elif analysis.complexity == "complex" and template.workflow_pattern in ["agile", "waterfall"]:
                score += 0.2
            elif analysis.complexity == "medium":
                score += 0.1
            
            # Document type match
            if analysis.document_type in ["process", "procedure"] and template.workflow_pattern != "lean":
                score += 0.1
            
            if score > 0.2:
                matches.append((template.id, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:5]
    
    def generate_team_from_analysis(
        self, 
        analysis: SOPAnalysis,
        template_id: Optional[str] = None,
        customizations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate team configuration from SOP analysis.
        
        Args:
            analysis: SOPAnalysis result
            template_id: Optional template to use as base
            customizations: Optional customizations to apply
            
        Returns:
            Complete team configuration
        """
        config = {
            "team_id": "sop_generated_team",
            "team_name": "SOP Generated Team",
            "description": f"Team generated from SOP analysis ({analysis.document_type})",
            "role_schema": {
                "schema_version": "1.0",
                "roles": analysis.roles
            },
            "workflow_schema": {
                "schema_version": "1.0",
                "workflow": {
                    "id": "sop_workflow",
                    "name": "SOP Workflow",
                    "description": f"Workflow from {analysis.document_type} document",
                    "stages": [
                        {
                            "id": stage.get("id", f"stage_{i}"),
                            "name": stage.get("name", f"Stage {i}"),
                            "role": stage.get("role", ""),
                            "order": stage.get("order", i),
                            "prerequisites": stage.get("dependencies", []),
                            "entry_criteria": [],
                            "exit_criteria": [],
                            "quality_gates": [],
                            "outputs": stage.get("outputs", [])
                        }
                        for i, stage in enumerate(analysis.workflow_stages, 1)
                    ]
                }
            },
            "skills": analysis.skills,
            "metadata": {
                "source": "sop_import",
                "document_type": analysis.document_type,
                "industry": analysis.industry,
                "complexity": analysis.complexity,
                "confidence_score": analysis.confidence_score,
                "extraction_method": analysis.extraction_method
            }
        }
        
        # If template provided, merge with template
        if template_id and self.template_library:
            template = self.template_library.get_by_id(template_id)
            if template:
                template_config = self.template_library.generate_team_config(template)
                # Merge: use SOP roles but fill gaps from template
                if not analysis.roles:
                    config["role_schema"]["roles"] = template_config["role_schema"]["roles"]
                if not analysis.workflow_stages:
                    config["workflow_schema"] = template_config["workflow_schema"]
                config["metadata"]["base_template"] = template_id
        
        # Apply customizations
        if customizations:
            if "team_name" in customizations:
                config["team_name"] = customizations["team_name"]
            if "description" in customizations:
                config["description"] = customizations["description"]
        
        return config
    
    def import_sop_enhanced(
        self, 
        sop_file: Path,
        use_llm: Optional[bool] = None,
        auto_match_template: bool = True
    ) -> Tuple[Dict[str, Any], SOPAnalysis]:
        """
        Enhanced SOP import with deep analysis and template matching.
        
        Args:
            sop_file: Path to SOP file
            use_llm: Whether to use LLM for analysis
            auto_match_template: Whether to automatically match a template
            
        Returns:
            Tuple of (team_config, analysis)
        """
        if not sop_file.exists():
            raise WorkflowError(f"SOP file not found: {sop_file}")
        
        content = sop_file.read_text(encoding='utf-8')
        
        # Deep analyze
        analysis = self.deep_analyze(content, use_llm)
        
        # Match template if requested
        template_id = None
        if auto_match_template and self.template_library:
            matches = self.match_template(analysis)
            if matches and matches[0][1] >= 0.4:  # Use template if good match
                template_id = matches[0][0]
                analysis.warnings.append(f"Auto-matched template: {template_id} (score: {matches[0][1]:.2f})")
        
        # Generate team config
        config = self.generate_team_from_analysis(analysis, template_id)
        
        return config, analysis
    
    # ========================================================================
    # Original Methods (preserved for backward compatibility)
    # ========================================================================

    def import_sop(self, sop_file: Path) -> Dict[str, Any]:
        """
        Import SOP document and generate configurations.
        
        Args:
            sop_file: Path to SOP markdown file
        
        Returns:
            Dict containing generated configurations:
            - roles: List of role definitions
            - skills: List of skill definitions
            - workflow: Workflow definition
        """
        if not sop_file.exists():
            raise WorkflowError(f"SOP file not found: {sop_file}")
        
        # Read SOP content
        content = sop_file.read_text(encoding='utf-8')
        
        # Extract information (simplified - can be enhanced with LLM)
        roles = self._extract_roles(content)
        skills = self._extract_skills(content)
        workflow = self._extract_workflow(content, roles)
        
        return {
            "roles": roles,
            "skills": skills,
            "workflow": workflow
        }
    
    def _extract_roles(self, content: str) -> List[Dict[str, Any]]:
        """Extract role definitions from SOP content"""
        roles = []
        
        # Look for role-like sections (headers with "Role", "Person", "Team", etc.)
        role_pattern = r'##+\s*(?:Role|Person|Team|Position):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(role_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            role_section = match.group(1)
            role_name = match.group(1).split('\n')[0].strip()
            
            # Extract role details
            role_id = role_name.lower().replace(' ', '_').replace('-', '_')
            description = self._extract_description(role_section)
            responsibilities = self._extract_list_items(role_section, "responsibilities", "duties")
            skills_mentioned = self._extract_skills_from_text(role_section)
            
            role = {
                "id": role_id,
                "name": role_name,
                "description": description or f"Role: {role_name}",
                "domain": self._infer_domain(role_section),
                "responsibility": "; ".join(responsibilities[:3]) if responsibilities else description or "",
                "skills": skills_mentioned,
                "constraints": {}
            }
            roles.append(role)
        
        return roles
    
    def _extract_all_skills(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract all skills from SOP content.
        
        Skills are extracted from:
        1. Explicit skill sections (## Skill: ...)
        2. Role responsibilities (职责)
        3. Workflow steps (流程步骤)
        4. Skill requirements (技能要求)
        """
        skills = []
        skill_map = {}  # skill_id -> skill_dict to avoid duplicates
        
        # 1. Extract explicit skill sections
        skill_pattern = r'##+\s*(?:Skill|Ability|Capability|Task):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(skill_pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            skill_section = match.group(1)
            skill_name = match.group(1).split('\n')[0].strip()
            skill_id = self._normalize_id(skill_name)
            description = self._extract_description(skill_section)
            
            skill_map[skill_id] = {
                "id": skill_id,
                "name": skill_name,
                "description": description or f"Skill: {skill_name}",
                "category": self._infer_category(skill_section),
                "skill_type": "cognitive",
                "side_effects": [],
                "deterministic": False,
                "testable": True
            }
        
        # 2. Extract skills from role responsibilities
        role_pattern = r'##+\s*(?:Role|角色):\s*(.+?)(?=\n##|\Z)'
        role_matches = re.finditer(role_pattern, content, re.IGNORECASE | re.DOTALL)
        for match in role_matches:
            role_section = match.group(1)
            # Extract responsibilities from list items (both "职责" and bullet points)
            responsibilities = self._extract_list_items(role_section, "职责", "responsibilities", "duties")
            # Also extract from bullet points directly
            bullet_items = re.findall(r'[-*]\s*(.+)', role_section)
            responsibilities.extend(bullet_items)
            
            for resp in responsibilities:
                # Skip if it's a skill requirement section
                if any(kw in resp.lower() for kw in ["技能", "skill", "能力", "ability"]):
                    continue
                skill_id, skill_name = self._extract_skill_from_text(resp)
                if skill_id and skill_id not in skill_map:
                    skill_map[skill_id] = {
                        "id": skill_id,
                        "name": skill_name,
                        "description": f"从职责中提取: {resp}",
                        "category": self._infer_category_from_text(resp),
                        "skill_type": "procedural",
                        "side_effects": [],
                        "deterministic": False,
                        "testable": True
                    }
        
        # 3. Extract skills from workflow steps (extract multiple skills per step)
        workflow_pattern = r'##+\s*(?:Process|Procedure|Workflow|流程|步骤):\s*(.+?)(?=\n##|\Z)'
        workflow_matches = re.finditer(workflow_pattern, content, re.IGNORECASE | re.DOTALL)
        for match in workflow_matches:
            workflow_section = match.group(1)
            steps = self._extract_steps(workflow_section)
            for step_text in steps:
                # Extract multiple skills from a single step (split by comma or semicolon)
                step_parts = re.split(r'[，,;；]', step_text)
                for part in step_parts:
                    part = part.strip()
                    if not part:
                        continue
                    skill_id, skill_name = self._extract_skill_from_workflow_step(part)
                    if skill_id and skill_id not in skill_map:
                        skill_map[skill_id] = {
                            "id": skill_id,
                            "name": skill_name,
                            "description": f"从工作流步骤中提取: {part[:100]}",
                            "category": self._infer_category_from_text(part),
                            "skill_type": "procedural",
                            "side_effects": [],
                            "deterministic": False,
                            "testable": True
                        }
        
        # 4. Extract skills from skill requirements
        skill_req_pattern = r'(?:技能要求|技能|skills?):\s*\n((?:\s*[-*]\s*.+\n?)+)'
        skill_req_matches = re.finditer(skill_req_pattern, content, re.IGNORECASE)
        for match in skill_req_matches:
            req_text = match.group(1)
            req_items = re.findall(r'[-*]\s*(.+)', req_text)
            for req_item in req_items:
                skill_id, skill_name = self._extract_skill_from_text(req_item)
                if skill_id and skill_id not in skill_map:
                    skill_map[skill_id] = {
                        "id": skill_id,
                        "name": skill_name,
                        "description": f"技能要求: {req_item}",
                        "category": self._infer_category_from_text(req_item),
                        "skill_type": "cognitive",
                        "side_effects": [],
                        "deterministic": False,
                        "testable": True
                    }
        
        return list(skill_map.values())
    
    def _extract_skill_from_text(self, text: str) -> Tuple[str, str]:
        """Extract skill ID and name from text"""
        # Extract action verbs and key nouns
        text = text.strip()
        if not text:
            return "", ""
        
        # Common action verbs that indicate skills
        action_verbs = {
            "验证": "verify", "检查": "check", "审核": "review", "分析": "analyze",
            "设计": "design", "实现": "implement", "测试": "test", "部署": "deploy",
            "处理": "process", "协调": "coordinate", "跟踪": "track", "管理": "manage",
            "生成": "generate", "创建": "create", "更新": "update", "优化": "optimize",
            "回答": "answer", "解决": "solve", "收集": "collect", "确认": "confirm",
            "接收": "receive", "拣选": "pick", "打包": "pack", "选择": "select",
            "安排": "arrange", "对接": "connect", "跟进": "follow_up"
        }
        
        # Find action verb
        skill_name = text
        skill_id = ""
        
        for cn_verb, en_verb in action_verbs.items():
            if cn_verb in text:
                # Extract the verb and following noun (up to 4 characters)
                parts = text.split(cn_verb, 1)
                if len(parts) > 1:
                    # Get noun phrase (up to 6 characters to avoid too long)
                    noun_part = parts[1].strip()
                    # Extract first meaningful noun phrase
                    noun_words = noun_part.split()[:2]  # Take first 2 words
                    noun = "".join(noun_words)[:6] if noun_words else ""
                    skill_name = f"{cn_verb}{noun}" if noun else cn_verb
                    skill_id = f"{en_verb}_{self._normalize_id(noun)}" if noun else en_verb
                    break
        
        # If no action verb found, check if it's a capability/ability description
        if not skill_id:
            # Check for common skill patterns
            capability_patterns = {
                "能力": "ability", "知识": "knowledge", "操作": "operation", "系统": "system"
            }
            for pattern, prefix in capability_patterns.items():
                if pattern in text:
                    # Extract the capability name
                    parts = text.split(pattern)
                    if len(parts) > 0:
                        cap_name = parts[0].strip()[:10]
                        skill_name = f"{cap_name}{pattern}"
                        skill_id = f"{prefix}_{self._normalize_id(cap_name)}"
                        break
            
            # If still no match, use first few words
            if not skill_id:
                words = text.split()[:2]  # Limit to 2 words
                skill_name = "".join(words)
                skill_id = self._normalize_id(skill_name)
        
        return skill_id, skill_name
    
    def _extract_skill_from_workflow_step(self, step_text: str) -> Tuple[str, str]:
        """Extract skill from workflow step text"""
        # Remove role name if present (format: "步骤 - 角色: 描述")
        if " - " in step_text:
            step_text = step_text.split(" - ", 1)[1]
        if ": " in step_text:
            step_text = step_text.split(": ", 1)[1]
        
        # Extract first action verb phrase
        return self._extract_skill_from_text(step_text)
    
    def _normalize_id(self, text: str) -> str:
        """Normalize text to ID format"""
        # Remove special characters, convert to lowercase, replace spaces with underscores
        text = re.sub(r'[^\w\s-]', '', text)
        text = text.lower().strip()
        text = re.sub(r'\s+', '_', text)
        return text
    
    def _infer_category_from_text(self, text: str) -> str:
        """Infer skill category from text content"""
        text_lower = text.lower()
        
        # Analysis skills
        if any(kw in text_lower for kw in ["分析", "analyze", "审核", "review", "验证", "verify", "检查", "check"]):
            return "analysis"
        # Design skills
        elif any(kw in text_lower for kw in ["设计", "design", "规划", "plan"]):
            return "design"
        # Development skills
        elif any(kw in text_lower for kw in ["实现", "implement", "开发", "develop", "生成", "generate", "创建", "create"]):
            return "development"
        # Testing skills
        elif any(kw in text_lower for kw in ["测试", "test", "验证", "validate"]):
            return "testing"
        # Operations skills
        elif any(kw in text_lower for kw in ["部署", "deploy", "管理", "manage", "操作", "operate", "协调", "coordinate"]):
            return "operations"
        else:
            return "general"
    
    def _extract_roles(self, content: str) -> List[Dict[str, Any]]:
        """Extract role definitions from SOP content"""
        roles = []
        
        # Look for role-like sections (headers with "Role", "Person", "Team", etc.)
        role_pattern = r'##+\s*(?:Role|Person|Team|Position):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(role_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            role_section = match.group(1)
            role_name = match.group(1).split('\n')[0].strip()
            
            # Extract role details
            role_id = role_name.lower().replace(' ', '_').replace('-', '_')
            description = self._extract_description(role_section)
            responsibilities = self._extract_list_items(role_section, "responsibilities", "duties")
            skills_mentioned = self._extract_skills_from_text(role_section)
            
            role = {
                "id": role_id,
                "name": role_name,
                "description": description or f"Role: {role_name}",
                "domain": self._infer_domain(role_section),
                "responsibility": "; ".join(responsibilities[:3]) if responsibilities else description or "",
                "skills": skills_mentioned,
                "constraints": {}
            }
            roles.append(role)
        
        return roles
    
    def _extract_role_definitions(self, content: str) -> List[Dict[str, Any]]:
        """Extract role definitions from SOP content (without composing skills yet)"""
        role_definitions = []
        
        # Look for role-like sections
        role_pattern = r'##+\s*(?:Role|角色|Person|Team|Position):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(role_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            role_section = match.group(1)
            role_name = match.group(1).split('\n')[0].strip()
            
            # Extract role details
            role_id = self._normalize_id(role_name)
            description = self._extract_description(role_section)
            responsibilities = self._extract_list_items(role_section, "职责", "responsibilities", "duties")
            skill_requirements = self._extract_list_items(role_section, "技能要求", "技能", "skills")
            
            role_def = {
                "id": role_id,
                "name": role_name,
                "description": description or f"Role: {role_name}",
                "domain": self._infer_domain(role_section),
                "responsibilities": responsibilities,
                "skill_requirements": skill_requirements,
                "raw_section": role_section
            }
            role_definitions.append(role_def)
        
        return role_definitions
    
    def _compose_roles_from_skills(
        self, 
        role_definitions: List[Dict[str, Any]], 
        skills: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compose roles from skills based on role definitions.
        
        Match skills to roles based on:
        1. Responsibilities mentioned in role definition
        2. Skill requirements mentioned in role definition
        3. Skill descriptions matching role responsibilities
        """
        roles = []
        skill_map = {skill["id"]: skill for skill in skills}
        
        for role_def in role_definitions:
            role_id = role_def["id"]
            matched_skill_ids = []
            
            # Match skills from responsibilities
            for resp in role_def.get("responsibilities", []):
                resp_skill_id, _ = self._extract_skill_from_text(resp)
                if resp_skill_id in skill_map:
                    if resp_skill_id not in matched_skill_ids:
                        matched_skill_ids.append(resp_skill_id)
                else:
                    # Try fuzzy matching: find skills that contain keywords from responsibility
                    resp_lower = resp.lower()
                    resp_words = set(re.findall(r'\w+', resp_lower))
                    for skill_id, skill in skill_map.items():
                        skill_desc_lower = skill.get("description", "").lower()
                        skill_name_lower = skill.get("name", "").lower()
                        # Check if responsibility keywords appear in skill description or name
                        if resp_words and any(word in skill_desc_lower or word in skill_name_lower 
                                           for word in resp_words if len(word) > 2):
                            if skill_id not in matched_skill_ids:
                                matched_skill_ids.append(skill_id)
            
            # Match skills from skill requirements
            for req in role_def.get("skill_requirements", []):
                req_skill_id, _ = self._extract_skill_from_text(req)
                if req_skill_id in skill_map:
                    if req_skill_id not in matched_skill_ids:
                        matched_skill_ids.append(req_skill_id)
                else:
                    # Try to find similar skill by name matching
                    req_lower = req.lower()
                    req_words = set(re.findall(r'\w+', req_lower))
                    for skill_id, skill in skill_map.items():
                        skill_name_lower = skill.get("name", "").lower()
                        skill_desc_lower = skill.get("description", "").lower()
                        # Check if requirement keywords appear in skill name or description
                        if req_words and (any(word in skill_name_lower for word in req_words if len(word) > 2) or
                                        any(word in skill_desc_lower for word in req_words if len(word) > 2)):
                            if skill_id not in matched_skill_ids:
                                matched_skill_ids.append(skill_id)
                                break
            
            # Also match skills based on role name and description
            role_name_lower = role_def.get("name", "").lower()
            role_desc_lower = role_def.get("description", "").lower()
            role_keywords = set(re.findall(r'\w+', role_name_lower + " " + role_desc_lower))
            for skill_id, skill in skill_map.items():
                skill_desc_lower = skill.get("description", "").lower()
                # Check if role keywords appear in skill description
                if role_keywords and any(word in skill_desc_lower for word in role_keywords if len(word) > 2):
                    # Additional check: skill should be related to this role's workflow
                    if skill_id not in matched_skill_ids:
                        matched_skill_ids.append(skill_id)
            
            # Build role
            responsibilities_text = "; ".join(role_def.get("responsibilities", [])[:3])
            # Extract responsibility from description if available
            desc = role_def["description"]
            if desc and not desc.startswith("Role:"):
                responsibility_text = desc
            elif responsibilities_text:
                responsibility_text = responsibilities_text
            else:
                responsibility_text = role_def["name"]
            
            role = {
                "id": role_id,
                "name": role_def["name"],
                "description": desc,
                "domain": role_def["domain"],
                "responsibility": responsibility_text,
                "skills": matched_skill_ids,
                "constraints": {}
            }
            roles.append(role)
        
        return roles
    
    def _build_workflow_from_skills(
        self, 
        content: str, 
        skills: List[Dict[str, Any]], 
        roles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build workflow from skills and roles.
        
        Extract workflow steps and match them to roles based on skills used in each step.
        """
        # Look for workflow-like sections
        workflow_pattern = r'##+\s*(?:Process|Procedure|Workflow|流程|步骤):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(workflow_pattern, content, re.IGNORECASE | re.DOTALL)
        
        stages = []
        stage_order = 1
        skill_map = {skill["id"]: skill for skill in skills}
        role_map = {role["id"]: role for role in roles}
        
        for match in matches:
            workflow_section = match.group(1)
            steps = self._extract_steps(workflow_section)
            
            for step_text in steps:
                # Extract skills from step
                step_skill_id, step_skill_name = self._extract_skill_from_workflow_step(step_text)
                
                # Find role that has this skill
                matched_role = None
                if step_skill_id in skill_map:
                    # Find role that has this skill
                    for role in roles:
                        if step_skill_id in role.get("skills", []):
                            matched_role = role
                            break
                
                # If no skill match, try to match by role name in step text
                if not matched_role:
                    matched_role = self._match_step_to_role(step_text, roles)
                
                if matched_role:
                    # Extract step name (remove role name if present)
                    step_name = step_text
                    if " - " in step_text:
                        step_name = step_text.split(" - ", 1)[0]
                    elif ": " in step_text:
                        step_name = step_text.split(": ", 1)[0]
                    
                    stage = {
                        "id": f"stage_{stage_order}",
                        "name": step_name[:100],  # Truncate long names
                        "role": matched_role["id"],
                        "order": stage_order,
                        "prerequisites": [],
                        "entry_criteria": [],
                        "exit_criteria": [],
                        "quality_gates": [],
                        "outputs": []
                    }
                    stages.append(stage)
                    stage_order += 1
        
        workflow = {
            "id": "imported_workflow",
            "name": "Imported Workflow",
            "description": "Workflow imported from SOP document",
            "stages": stages
        }
        
        return workflow
    
    def _extract_skills(self, content: str) -> List[Dict[str, Any]]:
        """Legacy method - kept for backward compatibility"""
        return self._extract_all_skills(content)
    
    def _extract_workflow(self, content: str, roles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract workflow definition from SOP content"""
        # Look for workflow-like sections (process, procedure, steps)
        workflow_pattern = r'##+\s*(?:Process|Procedure|Workflow|Steps):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(workflow_pattern, content, re.IGNORECASE | re.DOTALL)
        
        stages = []
        stage_order = 1
        
        for match in matches:
            workflow_section = match.group(1)
            steps = self._extract_steps(workflow_section)
            
            for step_text in steps:
                # Try to match step to a role
                matched_role = self._match_step_to_role(step_text, roles)
                
                if matched_role:
                    stage = {
                        "id": f"stage_{stage_order}",
                        "name": step_text[:50],  # Truncate long names
                        "role": matched_role["id"],
                        "order": stage_order,
                        "prerequisites": [],
                        "entry_criteria": [],
                        "exit_criteria": [],
                        "quality_gates": [],
                        "outputs": []
                    }
                    stages.append(stage)
                    stage_order += 1
        
        workflow = {
            "id": "imported_workflow",
            "name": "Imported Workflow",
            "description": "Workflow imported from SOP document",
            "stages": stages
        }
        
        return workflow
    
    def _extract_description(self, text: str) -> Optional[str]:
        """Extract description from text section"""
        # Look for description patterns
        desc_pattern = r'(?:description|overview|summary):\s*(.+?)(?=\n\n|\n\*|\n-|\Z)'
        match = re.search(desc_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_list_items(self, text: str, *keywords: str) -> List[str]:
        """Extract list items from text"""
        items = []
        for keyword in keywords:
            pattern = rf'{keyword}:\s*\n((?:\s*[-*]\s*.+\n?)+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                list_text = match.group(1)
                items.extend(re.findall(r'[-*]\s*(.+)', list_text))
        return items
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skill mentions from text"""
        # Simple keyword matching - can be enhanced
        skill_keywords = ["analyze", "design", "implement", "test", "review", "deploy"]
        mentioned = []
        for keyword in skill_keywords:
            if keyword in text.lower():
                mentioned.append(f"{keyword}_skill")
        return mentioned[:5]  # Limit to 5 skills
    
    def _infer_domain(self, text: str) -> str:
        """Infer domain from text content"""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["frontend", "ui", "interface", "react", "vue"]):
            return "frontend"
        elif any(kw in text_lower for kw in ["backend", "api", "server", "database"]):
            return "backend"
        elif any(kw in text_lower for kw in ["design", "ux", "ui design"]):
            return "design"
        elif any(kw in text_lower for kw in ["test", "qa", "quality"]):
            return "qa"
        return "general"
    
    def _infer_category(self, text: str) -> str:
        """Infer skill category from text"""
        return self._infer_domain(text)
    
    def _extract_steps(self, text: str) -> List[str]:
        """Extract workflow steps from text"""
        # Look for numbered or bulleted lists
        steps = []
        step_pattern = r'(?:^\d+\.|^[-*])\s*(.+?)(?=\n\d+\.|\n[-*]|\Z)'
        matches = re.finditer(step_pattern, text, re.MULTILINE)
        for match in matches:
            steps.append(match.group(1).strip())
        return steps
    
    def _match_step_to_role(self, step_text: str, roles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Match a workflow step to a role"""
        step_lower = step_text.lower()
        for role in roles:
            role_desc_lower = role.get("description", "").lower()
            role_resp_lower = role.get("responsibility", "").lower()
            if any(keyword in step_lower for keyword in role_desc_lower.split()[:5]):
                return role
            if any(keyword in step_lower for keyword in role_resp_lower.split()[:5]):
                return role
        return None
    
    def generate_config_files(
        self,
        sop_file: Path,
        output_dir: Path,
        overwrite: bool = False,
        use_enhanced: bool = True
    ) -> Dict[str, Path]:
        """
        Generate configuration files from SOP.
        
        Args:
            sop_file: Path to SOP file
            output_dir: Output directory for generated files
            overwrite: Whether to overwrite existing files
            use_enhanced: Whether to use enhanced import (skills -> roles -> workflow)
        
        Returns:
            Dict mapping config type to generated file path
        """
        if use_enhanced:
            # Use new enhanced import flow: skills -> roles -> workflow
            config, analysis = self.import_sop_enhanced(
                sop_file,
                use_llm=False,
                auto_match_template=False
            )
            configs = {
                "roles": config["role_schema"]["roles"],
                "skills": analysis.skills,
                "workflow": config["workflow_schema"]["workflow"]
            }
        else:
            # Use legacy import method
            configs = self.import_sop(sop_file)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = {}
        
        # Generate role_schema.yaml
        role_file = output_dir / "role_schema.yaml"
        if not role_file.exists() or overwrite:
            role_schema = {
                "schema_version": "1.0",
                "roles": configs["roles"]
            }
            with role_file.open('w', encoding='utf-8') as f:
                yaml.dump(role_schema, f, default_flow_style=False, allow_unicode=True)
            generated_files["roles"] = role_file
        
        # Skills are now defined in Skill.md files (Anthropic format)
        # Generate skills directory structure with Skill.md files
        skills_dir = output_dir / "skills"
        if not skills_dir.exists() or overwrite:
            skills_dir.mkdir(parents=True, exist_ok=True)
            for skill in configs.get("skills", []):
                skill_id = skill.get("id", "unknown")
                skill_dir = skills_dir / skill_id
                skill_dir.mkdir(exist_ok=True)
                
                # Generate Skill.md file
                skill_md = skill_dir / "Skill.md"
                frontmatter = {
                    "name": skill.get("name", skill_id),
                    "description": skill.get("description", ""),
                    "id": skill_id,
                    "category": skill.get("category", "general"),
                    "dimensions": skill.get("dimensions", []),
                    "levels": skill.get("levels", {}),
                    "tools": skill.get("tools", []),
                    "constraints": skill.get("constraints", []),
                    "skill_type": skill.get("skill_type"),
                    "side_effects": skill.get("side_effects", []),
                    "deterministic": skill.get("deterministic", False),
                    "testable": skill.get("testable", True),
                }
                
                # Write Skill.md with YAML frontmatter
                frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
                content = f"---\n{frontmatter_yaml}---\n# {skill.get('name', skill_id)}\n\n{skill.get('description', '')}\n"
                skill_md.write_text(content, encoding='utf-8')
            
            generated_files["skills"] = skills_dir
        
        # Generate workflow_schema.yaml
        workflow_file = output_dir / "workflow_schema.yaml"
        if not workflow_file.exists() or overwrite:
            workflow_schema = {
                "schema_version": "1.0",
                "workflow": configs["workflow"]
            }
            with workflow_file.open('w', encoding='utf-8') as f:
                yaml.dump(workflow_schema, f, default_flow_style=False, allow_unicode=True)
            generated_files["workflow"] = workflow_file
        
        return generated_files

