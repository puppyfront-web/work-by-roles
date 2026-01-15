# Teams 团队配置案例库

这个目录用于存放优秀的团队配置案例，包括工作流、角色和技能配置。这些配置可以作为模板，方便快速创建新的虚拟团队。

## 目录结构

每个团队配置案例应该包含以下文件：

```
team-name/
├── README.md              # 团队配置说明文档
├── workflow_schema.yaml   # 工作流定义
├── role_schema.yaml       # 角色定义
└── skill_library.yaml    # 技能库定义
```

## 使用方法

### 1. 项目初始化（自动使用标准配置）

**重要**：当运行 `workflow init` 时，系统会**自动优先使用 `teams/standard-delivery/` 配置**作为项目默认配置，符合项目规范。

```bash
# 初始化项目（自动使用 teams/standard-delivery/）
workflow init
```

初始化时会：
- ✅ 自动检测 `teams/standard-delivery/` 配置
- ✅ 将标准配置复制到 `.workflow/` 目录
- ✅ 如果 `.workflow/` 已存在配置文件，则跳过复制（避免覆盖）

### 2. 从团队配置创建新团队

```bash
# 使用 teams 目录中的配置创建新团队
workflow team create my-team --template standard-delivery --name "我的团队"
```

### 3. 查看可用的团队配置

```bash
# 列出所有可用的团队配置模板
workflow team templates
```

### 4. 贡献新的团队配置

1. 在 `teams/` 目录下创建新的子目录
2. 添加完整的配置文件（workflow_schema.yaml, role_schema.yaml, skill_library.yaml）
3. 添加 README.md 说明该配置的用途和特点
4. 提交 Pull Request

## 配置案例说明

### standard-delivery
标准的软件交付工作流，包含需求、架构、实现和验证四个阶段。

### frontend-team
前端开发团队配置，专注于前端开发流程和技能。

### backend-team
后端开发团队配置，专注于后端服务和 API 开发。

### full-stack-team
全栈开发团队配置，涵盖前后端开发流程。

## 最佳实践

1. **清晰的命名**：使用描述性的目录名称，如 `frontend-team`、`backend-team`
2. **完整的文档**：每个配置都应该有 README.md 说明其用途、适用场景和特点
3. **可复用性**：配置应该足够通用，便于其他项目复用
4. **版本管理**：在 README 中说明配置的版本和更新历史

## 配置优先级

当使用 `--template` 参数创建团队时，系统会按以下优先级查找模板：

1. `teams/` 目录（项目级别，最高优先级）
2. `work_by_roles/templates/` 目录（内置模板）
3. `templates/` 目录（项目级别）

这样可以确保项目特定的团队配置优先于内置模板。

