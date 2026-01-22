# 贡献指南

感谢您对 Work-by-Roles 项目的关注！我们欢迎所有形式的贡献。

## 🤝 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请：

1. 在 [GitHub Issues](https://github.com/puppyfront-web/work-by-roles/issues) 中搜索是否已有相关问题
2. 如果没有，请创建新的 issue，包含：
   - 清晰的问题描述
   - 复现步骤（如果是 bug）
   - 预期行为和实际行为
   - 环境信息（Python 版本、操作系统等）

### 提交代码

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/work-by-roles.git
   cd work-by-roles
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **安装开发依赖**
   ```bash
   pip install -e ".[dev]"
   ```

4. **运行测试**
   ```bash
   pytest
   ```

5. **提交代码**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   git push origin feature/your-feature-name
   ```

6. **创建 Pull Request**
   - 在 GitHub 上创建 Pull Request
   - 描述您的更改和原因
   - 确保所有测试通过

## 📝 代码规范

### 代码风格

- 遵循 PEP 8 Python 代码规范
- 使用类型提示（Type Hints）
- 遵循 SOLID 原则
- 保持代码简洁和可读性

### 提交信息规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整（不影响功能）
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建过程或辅助工具的变动

示例：
```
feat: 添加 SOP 导入功能
fix: 修复技能选择器的内存泄漏问题
docs: 更新 README.md 的使用说明
```

## 🧪 测试

在提交代码前，请确保：

1. 所有现有测试通过
2. 为新功能添加测试用例
3. 测试覆盖率不低于现有水平

运行测试：
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_specific.py

# 查看覆盖率
pytest --cov=work_by_roles
```

## 📚 文档

如果您修改了功能，请同时更新相关文档：

- `README.md` - 主要文档
- `QUICKSTART.md` - 快速开始指南
- `docs/ARCHITECTURE.md` - 架构文档（如果涉及架构变更）
- `docs/API.md` - API 文档（如果涉及 API 变更）

## 🎯 贡献方向

我们特别欢迎以下方面的贡献：

- 🐛 Bug 修复
- ✨ 新功能实现
- 📖 文档改进
- 🧪 测试用例补充
- 🎨 代码优化和重构
- 🌐 国际化支持
- 🔌 插件和扩展

## ❓ 问题

如果您有任何问题，可以：

- 在 [GitHub Discussions](https://github.com/puppyfront-web/work-by-roles/discussions) 中提问
- 创建 [GitHub Issue](https://github.com/puppyfront-web/work-by-roles/issues)
- 发送邮件至 puppy.front@gmail.com

## 📄 许可证

通过贡献代码，您同意您的贡献将在 MIT 许可证下授权。

---

再次感谢您的贡献！🎉
