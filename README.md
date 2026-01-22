# 多角色技能工作流框架

一个轻量级的工作流约束框架，通过角色边界和工作流阶段来规范开发流程。

## 📑 目录

- [🚀 快速开始（30秒）](#-快速开始30秒)
- [🎯 核心概念](#-核心概念)
- [📦 安装](#-安装)
- [📚 常用命令](#-常用命令)
- [💡 实用技巧](#-实用技巧)
  - [⭐ 从 SOP 文档生成虚拟团队](#-从-sop-文档生成虚拟团队项目亮点)
- [🤖 LLM 配置](#-llm-配置)
- [🔌 MCP 集成](#-mcp-model-context-protocol-集成)
- [🐍 Python API](#-python-api)
- [📖 快速参考](#-快速参考)
- [📚 完整文档](#-完整文档)

## 🚀 快速开始（30秒）

### 第一步：安装

```bash
# 克隆或下载项目后
pip install -e .
```

### 第二步：选择接入方式

#### 🎯 方式 A：一键接入（推荐，适合 IDE 环境）

```bash
# 1. 一键接入（自动配置角色和技能）
workflow setup

# 2. 直接使用角色执行任务
workflow role-execute product_analyst "分析用户登录功能需求"
workflow role-execute system_architect "设计微服务架构"
```

**适用场景**：
- ✅ Cursor、VS Code 等 IDE 环境
- ✅ 快速响应需求，无需复杂流程
- ✅ 直接调用角色处理任务

**示例输出**：
```
🚀 一键接入 Multi-Role Skills Workflow
============================================================
目标项目: /path/to/your/project

✅ 使用模板: standard-delivery
  ✅ 已复制配置和技能
🔍 正在扫描项目结构...
  ✅ 已生成项目上下文
  ✅ 已生成使用说明: TEAM_CONTEXT.md
  ✅ 已生成 Cursor IDE 配置文件

============================================================
✅ 接入完成！
```

#### 🔄 方式 B：完整工作流（适合大型项目）

```bash
# 1. 快速初始化（自动检测项目类型）
workflow init --quick

# 2. 一键执行全部阶段（自动使用 Agent + Skills）
workflow wfauto
```

**适用场景**：
- ✅ 大型项目，需要多阶段流程管理
- ✅ 需要完整的开发流程跟踪
- ✅ 团队协作，需要阶段化交付

**执行流程**：
```
需求分析 → 系统设计 → 架构设计 → 代码实现 → 质量保证 → 完成
   ↓          ↓          ↓          ↓          ↓
自动执行所有阶段，每个阶段使用对应的角色和技能
```

> 💡 **核心特性**: 
> - 🎯 **完全自动化** - 自动使用 Agent + Skills，无需手动干预
> - 📝 **专注代码** - 默认不生成文档，专注于代码实现
> - 🚀 **零配置启动** - 自动检测项目类型，使用合适模板
> - ⭐ **SOP 导入** - 从标准操作流程文档一键生成虚拟团队配置

### 🎉 接入完成后的下一步

1. **查看可用角色和技能**
   ```bash
   workflow list-roles   # 查看所有角色
   workflow list-skills  # 查看所有技能
   ```

2. **开始使用角色**
   ```bash
   # 在 IDE 中直接使用
   workflow role-execute product_analyst "分析用户需求"
   ```

3. **从 SOP 文档生成团队（⭐ 推荐）**
   ```bash
   # 如果你有标准操作流程文档，可以一键生成配置
   workflow import-sop your_sop.md
   ```

4. **查看项目上下文**
   - 打开 `.workflow/TEAM_CONTEXT.md` 了解项目配置
   - 在 Cursor 中，AI 会自动读取此文件

5. **探索更多功能**
   - 查看 [实用技巧](#-实用技巧) 部分
   - 了解 [SOP 导入功能](#-sop-文档导入一键生成虚拟团队)
   - 阅读 [完整文档](#-完整文档)

## 🎯 核心概念

### 两种工作模式

#### 模式 1: Workflow 模式（多阶段流程，可选）
```
需求分析 → 系统设计 → 架构设计 → 代码实现 → 质量保证 → 完成
   ↓          ↓          ↓          ↓          ↓
角色执行 → 角色执行 → 角色执行 → 角色执行 → 角色执行
```

- **角色（Role）**: 谁做什么（如：产品分析师、系统架构师）
- **阶段（Stage）**: 什么时候做什么（如：需求分析阶段、设计阶段）
- **适用场景**: 需要结构化流程的大型项目

#### 模式 2: Role Executor 模式（简化模式，推荐用于 IDE）
```
用户需求 → 直接调用角色 → 角色使用技能 → 完成任务
```

- **角色（Role）**: 谁做什么
- **技能（Skills）**: 角色使用什么能力（Anthropic 标准格式）
- **直接执行**: 无需定义 workflow 阶段，直接调用角色处理需求
- **适用场景**: IDE 环境（如 Cursor），快速响应需求

> 💡 **推荐**: 在 IDE（如 Cursor）中，推荐使用 Role Executor 模式，更简单直接。

### Skills 格式

项目使用 **Anthropic 标准格式**，每个技能是一个目录，包含 `Skill.md` 文件：

```
skills/
  requirements_analysis/
    Skill.md  # YAML frontmatter + Markdown
  system_design/
    Skill.md
  python_engineering/
    Skill.md
```

**格式特点**：
- ✅ 标准化的 YAML frontmatter + Markdown 格式
- ✅ 便于在不同项目间共享和复用
- ✅ 支持版本管理和技能组合
- ✅ 兼容 Anthropic 生态系统

**技能文件结构示例**：
```yaml
---
name: Requirements Analysis
description: 分析用户需求并生成需求文档
id: requirements_analysis
input_schema:
  type: object
  properties:
    user_story:
      type: string
      description: 用户故事描述
---
# 技能详细说明
...
```

## 📦 安装

### 前置要求

- Python 3.8+
- pip（Python 包管理器）

### 安装步骤

```bash
# 1. 克隆项目（或下载 ZIP）
git clone https://github.com/puppyfront-web/work-by-roles.git
cd work-by-roles

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装/开发模式（推荐）
pip install -e .
```

### 验证安装

```bash
# 检查命令是否可用
workflow --help

# 查看版本信息
workflow --version
```

### 开发模式安装

如果你想参与开发或修改代码：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest
```

## 📚 常用命令

### 新项目一键接入（推荐）
```bash
workflow setup             # 一键接入，自动配置角色和技能
workflow list-roles        # 查看所有可用角色
workflow list-skills       # 查看所有可用技能
workflow role-execute <role> "<requirement>"  # 使用角色执行任务
```

### 在 Cursor IDE 中使用（最简单）
```bash
# 1. 接入项目
workflow setup

# 2. 在 Cursor 对话中直接使用：
#    @product_analyst 分析用户需求
#    @system_architect 设计系统架构
#    @team 实现完整功能
```

### ⭐ 从 SOP 文档生成虚拟团队（项目亮点）

如果你有标准操作流程（SOP）文档，可以一键生成完整的团队配置：

```bash
# 从 SOP 文档自动生成 roles、skills 和 workflow
workflow import-sop your_sop.md

# 查看生成结果
workflow list-roles
workflow list-skills
```

**功能亮点**：
- 🎯 **智能提取** - 自动从 SOP 文档中提取角色、技能和工作流
- 🔄 **模板匹配** - 智能匹配最适合的团队模板
- 📝 **标准格式** - 生成符合 Anthropic 标准的技能文件
- 🤖 **LLM 增强** - 支持使用 LLM 进行深度分析（可选）

查看 [SOP 导入示例](#场景-5从-sop-文档生成团队配置-项目亮点) 了解更多。

## 💡 实用技巧

### 🎯 IDE 集成技巧

#### Cursor IDE 最佳实践
1. **使用 @ 符号快速调用角色**
   ```
   @product_analyst 分析用户登录功能需求
   @system_architect 设计微服务架构
   @team 实现完整的用户认证模块
   ```

2. **查看可用角色和技能**
   ```bash
   workflow list-roles    # 查看所有角色及其职责
   workflow list-skills   # 查看所有可用技能
   ```

3. **项目上下文自动生成**
   - 运行 `workflow setup` 后，会自动生成 `.workflow/TEAM_CONTEXT.md`
   - AI 会自动读取此文件并应用角色约束
   - 无需手动配置，开箱即用

#### VS Code 集成
- 在终端中直接使用 `workflow` 命令
- 支持命令补全和参数提示
- 可以创建自定义任务（tasks.json）来快速执行常用命令

### 🔍 调试技巧

1. **查看工作流状态**
   ```bash
   workflow status  # 查看当前阶段、角色和完成情况
   ```

2. **检查项目配置**
   ```bash
   workflow analyze  # 分析项目结构和配置
   ```

3. **查看详细日志**
   - 工作流执行日志保存在 `.workflow/logs/` 目录
   - 状态文件保存在 `.workflow/state.yaml`

### ⚡ 性能优化建议

1. **使用本地 LLM 模型**
   ```yaml
   # .workflow/config.yaml
   llm:
     provider: openai
     base_url: http://localhost:11434/v1  # Ollama 本地服务
     model: llama2
   ```

2. **并行执行（实验性）**
   ```bash
   workflow wfauto --parallel  # 并行执行多个阶段
   ```

3. **跳过不必要的阶段**
   ```bash
   workflow start <stage_id>  # 直接启动特定阶段
   ```

### 🎨 自定义配置技巧

1. **使用项目模板**
   ```bash
   workflow init --template web-app      # Web 应用模板
   workflow init --template api-service  # API 服务模板
   workflow init --template cli-tool     # CLI 工具模板
   ```

2. **共享技能库**
   - 在项目根目录创建 `skills/` 目录
   - 系统会自动识别并使用共享技能
   - 便于团队间共享和复用技能

3. **自定义角色**
   - 编辑 `.workflow/role_schema.yaml` 添加自定义角色
   - 为角色配置相应的技能和权限

### 📝 常见使用场景

#### 场景 1：快速分析需求
```bash
workflow role-execute product_analyst "分析用户登录功能需求" --use-llm
```

#### 场景 2：设计系统架构
```bash
workflow role-execute system_architect "设计微服务架构，包含用户服务、订单服务和支付服务" --use-llm
```

#### 场景 3：完整功能实现
```bash
workflow wfauto --intent "实现用户登录功能，包含注册、登录、登出和密码重置"
```

#### 场景 4：代码审查
```bash
workflow role-execute qa_reviewer "检查代码质量和测试覆盖率" --use-llm
```

#### 场景 5：从 SOP 文档生成团队配置（⭐ 项目亮点）
```bash
# 从 SOP 文档自动生成 roles、skills 和 workflow 配置
workflow import-sop examples/ecommerce_order_sop.md

# 指定输出目录
workflow import-sop my_sop.md --output .workflow/

# 覆盖已存在的配置
workflow import-sop my_sop.md --overwrite
```

**SOP 导入功能特点**：
- ✅ 自动提取角色、技能和工作流
- ✅ 支持 Markdown 格式的 SOP 文档
- ✅ 智能匹配团队模板
- ✅ 生成标准的 Anthropic 格式技能文件
- ✅ 支持 LLM 增强分析（需要配置 LLM）

**SOP 文档格式示例**：
```markdown
## Role: 订单审核员
**职责**: 负责审核订单的合法性和完整性
- 验证订单信息准确性
- 检查库存可用性

**技能要求**:
- 数据分析能力
- 风险识别能力
```

### 🐛 常见问题解答

**Q: 如何重置工作流状态？**
```bash
# 删除状态文件
rm .workflow/state.yaml

# 或使用 --no-restore-state 参数
workflow wfauto --no-restore-state
```

**Q: 如何重新接入项目？**
```bash
# 删除现有配置
rm -rf .workflow/

# 重新接入
workflow setup
```

**Q: 如何查看某个角色的详细信息？**
```bash
workflow list-roles | grep product_analyst
```

**Q: 如何自定义技能？**
- 在 `.workflow/skills/` 目录下创建技能目录
- 参考现有技能的格式创建 `Skill.md` 文件
- 使用 Anthropic 标准格式（YAML frontmatter + Markdown）

**Q: 工作流执行失败怎么办？**
1. 查看 `.workflow/logs/` 目录下的日志文件
2. 检查 `.workflow/state.yaml` 中的错误信息
3. 使用 `workflow status` 查看当前状态
4. 可以手动修复后继续执行

**Q: 如何在不同项目间共享技能？**
- 在项目根目录创建 `skills/` 目录
- 将技能文件放在该目录下
- 系统会自动识别并使用共享技能
- 也可以使用符号链接指向共享的技能库

**Q: 支持哪些 LLM 提供商？**
- OpenAI（GPT-3.5, GPT-4 等）
- Anthropic（Claude 系列）
- 任何兼容 OpenAI API 的服务（如 Ollama、LocalAI）

### Workflow 模式（多阶段流程，可选）
```bash
workflow init --quick      # 快速初始化（推荐）
workflow wfauto            # 一键执行全部阶段（自动使用 Agent + Skills）
workflow status            # 查看状态
workflow team list         # 列出所有团队
```

### Role Executor 模式（简化模式，推荐用于 IDE）
```bash
workflow role-execute <role_id> "<requirement>"  # 直接执行角色处理需求
workflow role-execute product_analyst "分析用户登录功能需求"
workflow role-execute system_architect "设计微服务架构" --use-llm
```

> 💡 **核心特性**: 
> - `workflow wfauto` 自动使用 Agent + Skills 执行，完全自动化，无需手动干预
> - `workflow role-execute` 简化模式，无需定义 workflow 阶段，直接在 IDE 中使用

## 🤖 LLM 配置

使用 `--use-llm` 参数时需要配置 LLM 客户端。系统支持多种 LLM 提供商和配置方式。

### ⚙️ 配置方式

#### 方式 1: 环境变量（推荐，适合 CI/CD）

```bash
# OpenAI
export OPENAI_API_KEY='your-api-key'
export LLM_MODEL='gpt-4'  # 可选

# 或 Anthropic
export ANTHROPIC_API_KEY='your-api-key'
export LLM_MODEL='claude-3-opus-20240229'  # 可选

# 本地模型（如 Ollama）
export OPENAI_BASE_URL='http://localhost:11434/v1'
export LLM_MODEL='llama2'
```

#### 方式 2: 配置文件（推荐，适合本地开发）

创建 `.workflow/config.yaml` 文件：

```yaml
llm:
  provider: openai  # 或 "anthropic"
  api_key: your-api-key  # 或从环境变量读取（留空）
  model: gpt-4  # 可选，默认值取决于提供商
  base_url: https://api.openai.com/v1  # 可选，用于自定义端点
```

**配置优先级**: 环境变量 > 配置文件

### 🌐 支持的 LLM 提供商

#### OpenAI
```yaml
llm:
  provider: openai
  api_key: sk-...
  model: gpt-4  # 或 gpt-3.5-turbo, gpt-4-turbo-preview 等
```

#### Anthropic
```yaml
llm:
  provider: anthropic
  api_key: sk-ant-...
  model: claude-3-opus-20240229  # 或 claude-3-sonnet-20240229 等
```

#### 本地模型（Ollama）
```yaml
llm:
  provider: openai
  api_key: not-needed  # 本地部署通常不需要 API key
  model: llama2  # 或 mistral, codellama 等
  base_url: http://localhost:11434/v1
```

**启动 Ollama 服务**：
```bash
# 安装 Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 下载模型
ollama pull llama2

# 启动服务（默认端口 11434）
ollama serve
```

#### 其他兼容 OpenAI API 的服务
- LocalAI
- OpenRouter
- 其他云服务商的兼容 API
- 代理服务

### 🔒 安全建议

1. **不要提交 API Key 到版本控制**
   ```bash
   # 添加到 .gitignore
   echo ".workflow/config.yaml" >> .gitignore
   ```

2. **使用环境变量（生产环境）**
   ```bash
   # 在 CI/CD 中设置
   export OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}
   ```

3. **使用配置文件模板**
   ```bash
   # 创建模板文件
   cp .workflow/config.yaml.example .workflow/config.yaml
   # 然后编辑 config.yaml 填入实际的 API key
   ```

### ⚠️ 常见问题

**Q: 如何测试 LLM 配置是否正确？**
```bash
# 使用 --use-llm 参数测试
workflow role-execute product_analyst "测试" --use-llm
```

**Q: 如何切换不同的 LLM 提供商？**
- 修改 `.workflow/config.yaml` 中的 `provider` 字段
- 或设置相应的环境变量（`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`）

**Q: 本地模型响应慢怎么办？**
- 使用更小的模型（如 `llama2:7b`）
- 调整 `base_url` 指向更快的服务器
- 考虑使用云服务商的 API

**注意**: 如果使用 `--use-llm` 但未配置 LLM 客户端，系统会抛出错误并提示配置方法。

## ⭐ SOP 文档导入：一键生成虚拟团队

这是项目的核心亮点功能！**从标准操作流程（SOP）文档自动生成完整的团队配置**，包括角色、技能和工作流。

### 🎯 功能特点

- ✅ **智能提取** - 自动从 SOP 文档中提取角色、技能和工作流定义
- ✅ **模板匹配** - 智能匹配最适合的团队模板（如敏捷、DevOps 等）
- ✅ **标准格式** - 生成符合 Anthropic 标准的技能文件（Skill.md）
- ✅ **LLM 增强** - 支持使用 LLM 进行深度分析，提高提取准确性
- ✅ **一键生成** - 自动生成所有配置文件，无需手动编写

### 📝 使用方法

#### 基本用法

```bash
# 从 SOP 文档生成配置
workflow import-sop your_sop.md

# 指定输出目录
workflow import-sop your_sop.md --output .workflow/

# 覆盖已存在的配置
workflow import-sop your_sop.md --overwrite
```

#### SOP 文档格式

SOP 文档支持 Markdown 格式，需要包含角色定义、技能要求和工作流程：

```markdown
# 电商订单处理标准操作流程

## Role: 订单审核员
**职责**: 负责审核订单的合法性和完整性
- 验证订单信息准确性
- 检查库存可用性
- 审核支付状态

**技能要求**:
- 数据分析能力
- 风险识别能力
- 订单管理系统操作

## Role: 仓库管理员
**职责**: 负责订单的拣货、打包和发货
- 根据订单拣选商品
- 检查商品质量
- 打包商品

**技能要求**:
- 仓库管理系统操作
- 商品识别能力
- 物流协调能力

## Process: 订单处理流程
1. 订单接收
2. 订单审核（订单审核员）
3. 商品拣选（仓库管理员）
4. 打包发货（仓库管理员）
5. 物流跟踪（物流协调员）
```

### 🔍 生成结果

执行 `workflow import-sop` 后，会生成以下文件：

```
.workflow/
├── role_schema.yaml      # 角色定义
├── workflow_schema.yaml   # 工作流定义
└── skills/               # 技能目录
    ├── data_analysis/
    │   └── Skill.md
    ├── risk_identification/
    │   └── Skill.md
    └── ...
```

### 📊 提取统计

导入完成后会显示提取统计信息：

```
✅ SOP 导入完成
============================================================
📊 提取统计:
  技能数量: 12
  角色数量: 4
  工作流阶段数: 5
  文档类型: process
  行业: ecommerce
  置信度: 0.85
============================================================
📁 生成的文件:
  roles: .workflow/role_schema.yaml
  skills: .workflow/skills/
  workflow: .workflow/workflow_schema.yaml
```

### 🎨 高级功能

#### 使用 LLM 增强分析

如果配置了 LLM，可以使用更智能的分析：

```python
from work_by_roles.core.sop_importer import SOPImporter

importer = SOPImporter(llm_client=your_llm_client)
analysis = importer.deep_analyze(sop_content, use_llm=True)
```

#### 模板匹配

系统会自动匹配最适合的团队模板：

- **敏捷开发** - 检测到 sprint、backlog、scrum 等关键词
- **DevOps** - 检测到 pipeline、deployment、kubernetes 等关键词
- **产品发现** - 检测到 user story、prototype、validation 等关键词

### 📄 示例文件

查看 [示例 SOP 文档](examples/ecommerce_order_sop.md) 了解完整的格式示例。

### 💡 最佳实践

1. **清晰的角色定义** - 使用 `## Role: [角色名]` 格式定义角色
2. **明确的技能要求** - 在角色定义中列出所需技能
3. **结构化的工作流** - 使用 `## Process:` 或编号列表定义流程
4. **使用标准术语** - 使用行业标准术语有助于模板匹配

---

## 🔌 MCP (Model Context Protocol) 集成

项目支持在工作流执行时调用外部 MCP 服务器，使角色和流程可以集成外部服务和资源。

### 快速开始

#### 1. 在技能定义中添加 MCP 配置

在技能的 `Skill.md` 文件中添加 MCP 元数据：

```yaml
---
name: fetch_browser_data
description: 从浏览器MCP服务器获取页面数据
id: fetch_browser_data
metadata:
  mcp:
    action: fetch_resource  # list_resources | fetch_resource | call_tool
    server: cursor-browser-extension  # MCP服务器标识
    resource_uri: "mcp://cursor-browser-extension/page/content"
input_schema:
  type: object
  properties:
    url:
      type: string
      description: 要获取的页面URL
output_schema:
  type: object
  properties:
    content:
      type: string
      description: 页面内容
---
```

#### 2. 支持的 MCP 操作

- **`list_resources`**: 列出 MCP 服务器上的可用资源
- **`fetch_resource`**: 获取指定的资源（需要 `resource_uri`）
- **`call_tool`**: 调用 MCP 工具（需要 `tool` 名称）

#### 3. 使用示例

```python
from work_by_roles.core.agent_orchestrator import AgentOrchestrator
from work_by_roles.core.mcp_skill_invoker import MCPSkillInvokerFactory

# 创建 MCP invoker（如果使用 MCP SDK）
mcp_invoker = MCPSkillInvokerFactory.create(mcp_client=your_mcp_client)

# 执行技能（如果技能有 MCP 配置，会自动使用 MCP 调用）
orchestrator = AgentOrchestrator(engine)
result = orchestrator.execute_skill(
    skill_id="fetch_browser_data",
    input_data={"url": "https://example.com"},
    stage_id="data_collection",
    role_id="data_analyst"
)
```

### MCP 配置示例

#### 获取浏览器资源
```yaml
metadata:
  mcp:
    action: fetch_resource
    server: cursor-browser-extension
    resource_uri: "mcp://cursor-browser-extension/page/content"
```

#### 调用 MCP 工具
```yaml
metadata:
  mcp:
    action: call_tool
    server: cursor-browser-extension
    tool: navigate_to_page
```

#### 列出可用资源
```yaml
metadata:
  mcp:
    action: list_resources
    server: cursor-browser-extension
```

### 架构说明

项目通过可扩展的 `SkillInvoker` 系统支持 MCP：

```
Workflow Stage → Role Execution → Skill Selection → SkillInvoker.invoke() → MCPSkillInvoker → External MCP Server
```

📖 **[查看详细 MCP 集成指南](docs/MCP_INTEGRATION.md)** - 包含完整配置、使用场景和最佳实践

## 🐍 Python API

除了命令行工具，项目还提供了完整的 Python API，方便在代码中集成使用。

### 快速示例

```python
from work_by_roles import Workflow

# 零配置启动
workflow = Workflow.quick_start()

# 启动阶段
workflow.start("requirements")

# 完成阶段
workflow.complete()

# 查看状态
status = workflow.status()
print(f"当前阶段: {status['current_stage']}")
```

### 高级用法

```python
from work_by_roles import Workflow
from pathlib import Path

# 使用指定模板
workflow = Workflow.from_template("web-app", workspace=Path("./my-project"))

# 指定角色启动阶段
workflow.start("requirements", role_id="product_analyst")

# 完成并获取结果
success, errors = workflow.complete("requirements")
if success:
    print("阶段完成！")
else:
    print(f"错误: {errors}")
```

📖 **更多API详情**: 查看 [API文档](docs/API.md) 了解完整的 API 参考

## 📖 快速参考

### 命令速查表

| 命令 | 说明 | 示例 |
|------|------|------|
| `workflow setup` | 一键接入项目 | `workflow setup` |
| `workflow init --quick` | 快速初始化工作流 | `workflow init --quick` |
| `workflow wfauto` | 自动执行全部阶段 | `workflow wfauto --intent "实现登录功能"` |
| `workflow role-execute` | 执行角色任务 | `workflow role-execute product_analyst "分析需求"` |
| `workflow list-roles` | 列出所有角色 | `workflow list-roles` |
| `workflow list-skills` | 列出所有技能 | `workflow list-skills` |
| `workflow status` | 查看工作流状态 | `workflow status` |
| `workflow start` | 启动阶段 | `workflow start requirements` |
| `workflow complete` | 完成阶段 | `workflow complete` |
| `workflow import-sop` | 从 SOP 文档生成配置 | `workflow import-sop sop.md` |

### 常用角色速查

| 角色 ID | 角色名称 | 主要职责 |
|---------|----------|----------|
| `product_analyst` | 产品分析师 | 需求分析、用户研究 |
| `system_architect` | 系统架构师 | 系统设计、架构规划 |
| `core_framework_engineer` | 核心框架工程师 | 代码实现、框架搭建 |
| `qa_reviewer` | 质量保证审查员 | 代码审查、测试验证 |

## 📚 完整文档

- 📖 [快速开始](QUICKSTART.md) - 30秒接入指南
- 🔗 [角色与技能关系指南](ROLES_AND_SKILLS.md) - 理解角色和技能的关系及配置方法
- 🧠 [API文档](docs/API.md) - 详细API参考
- 🏗️ [架构文档](docs/ARCHITECTURE.md) - 系统架构和设计说明
- 📊 [技能分层分类](docs/SKILLS_LAYERED_CLASSIFICATION.md) - 技能分类体系说明

### 示例文件

- 📄 [SOP 导入示例](examples/ecommerce_order_sop.md) - 查看如何编写 SOP 文档

## 开源协议

MIT License - 详见 [LICENSE](LICENSE)

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 社区

- 报告问题：[GitHub Issues](https://github.com/puppyfront-web/work-by-roles/issues)
- 功能建议：[GitHub Discussions](https://github.com/puppyfront-web/work-by-roles/discussions)

## 📊 项目状态

✅ **生产就绪** - 所有核心功能已实现并通过测试

### 功能特性

- ✅ 一键接入，零配置启动
- ✅ 支持多种 IDE（Cursor、VS Code 等）
- ✅ 自动使用 Agent + Skills 执行
- ✅ 支持多种 LLM 提供商（OpenAI、Anthropic、本地模型）
- ✅ MCP 协议集成
- ✅ 完整的 Python API
- ✅ 丰富的项目模板
- ✅ 技能和角色的灵活配置

### 版本信息

当前版本支持的功能：
- 工作流模式（多阶段流程）
- Role Executor 模式（简化模式）
- 自动项目类型检测
- 技能库管理
- 状态持久化
- 质量门禁
- 并行执行（实验性）

---

**开始使用**: [快速开始](#-快速开始30秒) | [查看文档](#-完整文档) | [报告问题](https://github.com/puppyfront-web/work-by-roles/issues)

