"""
SOP (Standard Operating Procedure) importer.
Converts SOP documents into Roles/Skills/Workflow configurations.
Following Single Responsibility Principle - handles SOP import only.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import re
import yaml

from .exceptions import WorkflowError


class SOPImporter:
    """
    Imports SOP documents and generates role/skill/workflow configurations.
    
    This is a simplified implementation that extracts structured information
    from markdown documents. Can be enhanced with LLM for better extraction.
    """
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize SOP importer.
        
        Args:
            llm_client: Optional LLM client for enhanced extraction
        """
        self.llm_client = llm_client
    
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
    
    def _extract_skills(self, content: str) -> List[Dict[str, Any]]:
        """Extract skill definitions from SOP content"""
        skills = []
        
        # Look for skill-like sections
        skill_pattern = r'##+\s*(?:Skill|Ability|Capability|Task):\s*(.+?)(?=\n##|\Z)'
        matches = re.finditer(skill_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            skill_section = match.group(1)
            skill_name = match.group(1).split('\n')[0].strip()
            
            skill_id = skill_name.lower().replace(' ', '_').replace('-', '_')
            description = self._extract_description(skill_section)
            
            skill = {
                "id": skill_id,
                "name": skill_name,
                "description": description or f"Skill: {skill_name}",
                "category": self._infer_category(skill_section),
                "skill_type": "cognitive",  # Default, can be enhanced
                "side_effects": [],
                "deterministic": False,
                "testable": True
            }
            skills.append(skill)
        
        return skills
    
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
        overwrite: bool = False
    ) -> Dict[str, Path]:
        """
        Generate configuration files from SOP.
        
        Args:
            sop_file: Path to SOP file
            output_dir: Output directory for generated files
            overwrite: Whether to overwrite existing files
        
        Returns:
            Dict mapping config type to generated file path
        """
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
                import yaml
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

