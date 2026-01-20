"""
Shared pytest fixtures and configuration for all tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
import yaml

from work_by_roles.core.workflow_engine import WorkflowEngine
from work_by_roles.core.agent_message_bus import AgentMessageBus
from work_by_roles.core.models import Role, Stage, Workflow, Skill


@pytest.fixture
def temp_workspace() -> Generator[Path, None, None]:
    """Create a temporary workspace directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="work_by_roles_test_")
    workspace = Path(temp_dir)
    
    # Create .workflow directory and temp subdirectory
    workflow_dir = workspace / ".workflow"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = workflow_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    yield workspace
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_role() -> Role:
    """Create a sample role for testing."""
    return Role(
        id="test_role",
        name="Test Role",
        description="A test role",
        skills=["test_skill"],
        domain="general",
        responsibility="Test responsibility",
        extends=None,
        constraints={
            "allowed_actions": ["test_action"],
            "forbidden_actions": []
        },
        validation_rules=[],
        instruction_template="Test instruction"
    )


@pytest.fixture
def sample_stage() -> Stage:
    """Create a sample stage for testing."""
    from work_by_roles.core.models import QualityGate, Output
    
    return Stage(
        id="test_stage",
        name="Test Stage",
        role="test_role",
        order=1,
        prerequisites=[],
        entry_criteria=[],
        exit_criteria=[],
        quality_gates=[
            QualityGate(
                type="file_exists",
                criteria=["test_file.txt"],
                validator="file_validator",
                strict=False
            )
        ],
        outputs=[
            Output(
                type="file",
                format="text",
                required=True,
                name="test_file.txt"
            )
        ],
        goal_template="Test goal"
    )


@pytest.fixture
def sample_workflow(sample_stage: Stage) -> Workflow:
    """Create a sample workflow for testing."""
    return Workflow(
        id="test_workflow",
        name="Test Workflow",
        description="A test workflow",
        stages=[sample_stage]
    )


@pytest.fixture
def sample_skill() -> Skill:
    """Create a sample skill for testing."""
    return Skill(
        id="test_skill",
        name="Test Skill",
        description="A test skill",
        category="general",
        dimensions=["test_dimension"],
        levels={1: "Level 1"},
        tools=["test_tool"],
        constraints=[],
        input_schema={
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "output": {"type": "string"}
            }
        }
    )


@pytest.fixture
def workflow_engine(temp_workspace: Path) -> WorkflowEngine:
    """Create a WorkflowEngine instance for testing."""
    return WorkflowEngine(workspace_path=temp_workspace)


@pytest.fixture
def message_bus(temp_workspace: Path) -> AgentMessageBus:
    """Create an AgentMessageBus instance for testing."""
    messages_dir = temp_workspace / ".workflow" / "messages"
    return AgentMessageBus(persist_messages=False, messages_dir=messages_dir)


@pytest.fixture
def sample_workflow_config(temp_workspace: Path) -> Dict[str, Any]:
    """Create sample workflow configuration files."""
    workflow_dir = temp_workspace / ".workflow"
    
    # Create role_schema.yaml
    role_schema = {
        "schema_version": "1.0",
        "roles": [
            {
                "id": "test_role",
                "name": "Test Role",
                "description": "A test role",
                "instruction_template": "Test instruction",
                "extends": None,
                "constraints": {
                    "allowed_actions": ["test_action"],
                    "forbidden_actions": []
                },
                "skills": ["test_skill"],
                "domain": "general",
                "responsibility": "Test responsibility",
                "validation_rules": []
            }
        ]
    }
    
    with open(workflow_dir / "role_schema.yaml", "w") as f:
        yaml.dump(role_schema, f)
    
    # Create workflow_schema.yaml
    workflow_schema = {
        "schema_version": "1.0",
        "workflow": {
            "id": "test_workflow",
            "name": "Test Workflow",
            "description": "A test workflow",
            "stages": [
                {
                    "id": "test_stage",
                    "name": "Test Stage",
                    "role": "test_role",
                    "order": 1,
                    "prerequisites": [],
                    "entry_criteria": [],
                    "exit_criteria": [],
                    "quality_gates": [
                        {
                            "type": "file_exists",
                            "criteria": ["test_file.txt"],
                            "validator": "file_validator",
                            "strict": False
                        }
                    ],
                    "outputs": [
                        {
                            "type": "file",
                            "format": "text",
                            "required": True,
                            "name": "test_file.txt"
                        }
                    ],
                    "goal_template": "Test goal"
                }
            ]
        }
    }
    
    with open(workflow_dir / "workflow_schema.yaml", "w") as f:
        yaml.dump(workflow_schema, f)
    
    # Create skills directory
    skills_dir = workflow_dir / "skills" / "test_skill"
    skills_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Skill.md
    skill_md = """---
name: test_skill
description: A test skill
category: general
input_schema:
  type: object
  properties:
    input:
      type: string
output_schema:
  type: object
  properties:
    output:
      type: string
---

# Test Skill

This is a test skill for testing purposes.
"""
    
    with open(skills_dir / "Skill.md", "w") as f:
        f.write(skill_md)
    
    return {
        "workspace": temp_workspace,
        "workflow_dir": workflow_dir,
        "role_schema": role_schema,
        "workflow_schema": workflow_schema
    }


# Import enhanced fixtures for automated testing
from tests.fixtures.test_project_fixtures import (
    clean_project,
    fresh_project,
    project_with_files,
    project_with_template,
    command_tester,
    command_tester_clean,
    ProjectTestHelper,
    CommandTester
)

