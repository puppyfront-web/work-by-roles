"""
端到端测试：在其他项目中使用工作流框架

测试场景：
1. 模拟在新项目中使用 workflow setup 命令
2. 验证配置文件是否正确创建
3. 验证基本命令是否可用
4. 验证角色和技能是否正确加载
"""
import pytest
import subprocess
import sys
import shutil
from pathlib import Path
import yaml


class TestSetupInNewProject:
    """测试在其他项目中使用工作流框架的完整流程"""
    
    def test_workflow_setup_creates_config_files(self, temp_workspace):
        """测试 workflow setup 命令创建必要的配置文件"""
        # 模拟一个新项目（没有 .workflow 目录）
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 创建一些项目文件，模拟真实项目
        (project_dir / "README.md").write_text("# My Project\n")
        (project_dir / "main.py").write_text("print('Hello')\n")
        
        # 运行 workflow setup
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        # 验证命令执行成功
        assert result.returncode == 0, f"Setup failed: {result.stderr}"
        
        # 验证 .workflow 目录已创建
        workflow_dir = project_dir / ".workflow"
        assert workflow_dir.exists(), ".workflow 目录应该被创建"
        
        # 验证角色配置文件已创建
        roles_file = workflow_dir / "role_schema.yaml"
        assert roles_file.exists(), "role_schema.yaml 应该被创建"
        
        # 验证技能目录已创建
        skills_dir = workflow_dir / "skills"
        assert skills_dir.exists(), "skills 目录应该被创建"
        
        # 验证至少有一些技能文件
        skill_files = list(skills_dir.rglob("Skill.md"))
        assert len(skill_files) > 0, "应该至少有一个技能文件"
        
        # 验证项目上下文文件已创建
        context_file = workflow_dir / "project_context.yaml"
        assert context_file.exists(), "project_context.yaml 应该被创建"
        
        # 验证使用说明文件已创建
        usage_file = workflow_dir / "USAGE.md"
        assert usage_file.exists(), "USAGE.md 应该被创建"
    
    def test_workflow_setup_uses_correct_template(self, temp_workspace):
        """测试 workflow setup 使用正确的模板"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 运行 workflow setup
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # 验证角色配置文件内容
        roles_file = project_dir / ".workflow" / "role_schema.yaml"
        with open(roles_file, 'r', encoding='utf-8') as f:
            roles_data = yaml.safe_load(f)
        
        # 验证包含标准角色
        role_ids = [role['id'] for role in roles_data.get('roles', [])]
        assert 'product_analyst' in role_ids or len(role_ids) > 0, "应该包含标准角色"
    
    def test_list_roles_after_setup(self, temp_workspace):
        """测试 setup 后可以列出角色"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 先运行 setup
        setup_result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert setup_result.returncode == 0
        
        # 然后测试 list-roles 命令
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "list-roles"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        # 应该成功执行
        assert result.returncode == 0, f"list-roles failed: {result.stderr}"
        
        # 输出应该包含角色信息
        assert len(result.stdout) > 0, "应该输出角色列表"
    
    def test_list_skills_after_setup(self, temp_workspace):
        """测试 setup 后可以列出技能"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 先运行 setup
        setup_result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert setup_result.returncode == 0
        
        # 然后测试 list-skills 命令
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "list-skills"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        # 应该成功执行
        assert result.returncode == 0, f"list-skills failed: {result.stderr}"
        
        # 输出应该包含技能信息
        assert len(result.stdout) > 0, "应该输出技能列表"
    
    def test_setup_idempotent(self, temp_workspace):
        """测试 setup 命令是幂等的（可以安全地多次运行）"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 第一次运行 setup
        result1 = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert result1.returncode == 0
        
        # 记录第一次创建的文件
        roles_file = project_dir / ".workflow" / "role_schema.yaml"
        first_content = roles_file.read_text()
        
        # 第二次运行 setup（应该不会失败）
        result2 = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        # 应该成功（可能显示已存在的警告）
        assert result2.returncode == 0 or "已接入" in result2.stdout or "已存在" in result2.stdout
        
        # 文件内容应该保持不变
        second_content = roles_file.read_text()
        assert first_content == second_content, "重复运行不应该修改现有文件"
    
    def test_role_execute_after_setup(self, temp_workspace):
        """测试 setup 后可以使用 role-execute 命令"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 先运行 setup
        setup_result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert setup_result.returncode == 0
        
        # 测试 role-execute 命令（不实际执行，只验证命令可用）
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "role-execute", "--help"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        
        # 应该成功显示帮助信息
        assert result.returncode == 0, "role-execute 命令应该可用"
    
    def test_project_context_generated(self, temp_workspace):
        """测试项目上下文文件正确生成"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 创建一些项目文件
        (project_dir / "main.py").write_text("print('Hello')\n")
        (project_dir / "requirements.txt").write_text("pytest>=7.0\n")
        (project_dir / "src").mkdir(parents=True, exist_ok=True)
        (project_dir / "src" / "app.py").write_text("def main(): pass\n")
        
        # 运行 setup
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # 验证项目上下文文件存在且包含信息
        context_file = project_dir / ".workflow" / "project_context.yaml"
        assert context_file.exists(), "项目上下文文件应该被创建"
        
        with open(context_file, 'r', encoding='utf-8') as f:
            context_data = yaml.safe_load(f)
        
        # 验证包含项目信息
        assert 'project_structure' in context_data or 'files' in context_data or len(context_data) > 0, \
            "项目上下文应该包含项目信息"
    
    def test_usage_file_created(self, temp_workspace):
        """测试使用说明文件正确创建"""
        project_dir = temp_workspace / "new_project"
        project_dir.mkdir()
        
        # 运行 setup
        result = subprocess.run(
            [sys.executable, "-m", "work_by_roles.cli", "setup"],
            cwd=project_dir,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # 验证 USAGE.md 文件存在
        usage_file = project_dir / ".workflow" / "USAGE.md"
        assert usage_file.exists(), "USAGE.md 应该被创建"
        
        # 验证文件内容包含使用说明
        usage_content = usage_file.read_text(encoding='utf-8')
        assert len(usage_content) > 0, "USAGE.md 应该包含内容"
        assert "使用" in usage_content or "使用指南" in usage_content or "指南" in usage_content, \
            "USAGE.md 应该包含使用说明"

