# 角色与技能关系指南

> 本文档详细说明 Work-by-Roles 框架中角色（Role）和技能（Skill）的关系，以及如何配置和使用它们。

## 📋 目录

- [核心概念](#核心概念)
- [关系结构](#关系结构)
- [配置方式](#配置方式)
- [使用示例](#使用示例)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

## 核心概念

### 什么是角色（Role）？

**角色（Role）** 定义了"谁"来执行任务，它描述了：
- 角色的职责和边界
- 允许和禁止的操作
- **需要的技能**（通过 `required_skills` 定义）
- 验证规则

### 什么是技能（Skill）？

**技能（Skill）** 定义了"如何"执行任务，它描述了：
- 技能的能力和描述
- 技能的维度（dimensions）
- 技能的级别（levels: 1-3）
- 使用的工具（tools）
- 约束条件（constraints）

### 关系本质

**Role 是技能的消费者，Skill 是能力的提供者。**

- Role 通过 `required_skills` 声明需要哪些技能
- Skill 是独立的、可复用的能力定义
- 一个 Role 可以需要多个 Skill
- 一个 Skill 可以被多个 Role 使用

## 关系结构

### 数据模型

```python
# Role 模型
@dataclass
class Role:
    id: str
    name: str
    description: str
    required_skills: List[SkillRequirement]  # 关键：角色需要的技能列表
    constraints: Dict[str, List[str]]
    validation_rules: List[str]

# SkillRequirement 模型
@dataclass
class SkillRequirement:
    skill_id: str          # 引用 Skill Library 中的技能 ID
    min_level: int         # 最低技能级别要求（1-3）
    focus: Optional[List[str]]  # 可选的技能重点领域

# Skill 模型
@dataclass
class Skill:
    id: str
    name: str
    description: str
    dimensions: List[str]   # 技能维度
    levels: Dict[int, str]  # 技能级别定义
    tools: List[str]        # 使用的工具
    constraints: List[str]  # 约束条件
```

### 关系图

```
┌─────────────────┐
│   Role          │
│                 │
│ required_skills │──┐
│   (List)        │  │
└─────────────────┘  │
                     │ 引用
                     ▼
         ┌───────────────────────┐
         │  SkillRequirement      │
         │                        │
         │  skill_id: "xxx"       │──┐
         │  min_level: 2          │  │
         │  focus: [...]          │  │
         └───────────────────────┘  │
                                    │ 查找
                                    ▼
                        ┌───────────────────┐
                        │  Skill Library     │
                        │                   │
                        │  skills:          │
                        │    - id: "xxx"    │
                        │    - levels: {...}│
                        │    - tools: [...] │
                        └───────────────────┘
```

## 配置方式

### 1. 定义技能库（Skill Library）

在 `skill_library.yaml` 中定义所有可用的技能：

```yaml
schema_version: "1.0"
skills:
  - id: "requirements_analysis"
    name: "Requirements Analysis"
    description: "Ability to elicit, structure, and validate requirements"
    dimensions:
      - "elicitation"
      - "scope_alignment"
      - "acceptance_criteria"
    levels:
      1: "Understands basic templates and can capture user needs"
      2: "Can model flows, risks, and non-functional needs"
      3: "Leads complex discovery, reconciles conflicting stakeholders"
    tools:
      - "markdown"
      - "diagrams"
    constraints:
      - "must_define_acceptance_criteria"
      - "must_document_risks"

  - id: "system_design"
    name: "System Architecture"
    description: "Architect systems with clear separation of concerns"
    dimensions:
      - "componentization"
      - "data_flow"
      - "quality_attributes"
    levels:
      1: "Defines core components and interactions"
      2: "Covers resiliency, extensibility, and validation flows"
      3: "Optimizes for scale, evolution, and governance"
    tools:
      - "mermaid"
      - "architecture_decision_records"
    constraints:
      - "must_define_quality_gates"
```

### 2. 定义角色（Role）

在 `role_schema.yaml` 中定义角色，并引用技能：

```yaml
schema_version: "1.0"
roles:
  - id: "product_analyst"
    name: "Product Analyst"
    description: "Defines requirements and scope"
    constraints:
      allowed_actions:
        - "define_requirements"
        - "define_scope"
      forbidden_actions:
        - "write_code"
    # 关键：通过 required_skills 引用技能
    required_skills:
      - skill_id: "requirements_analysis"
        min_level: 2
        focus:
          - "acceptance_criteria"
          - "scope_alignment"
    validation_rules:
      - "must_produce_requirements_doc"

  - id: "system_architect"
    name: "System Architect"
    description: "Designs architecture and DSL"
    constraints:
      allowed_actions:
        - "design_architecture"
        - "define_schemas"
    required_skills:
      - skill_id: "system_design"
        min_level: 2
      - skill_id: "schema_design"
        min_level: 2
    validation_rules:
      - "must_produce_architecture_doc"
```

### 3. 技能包（Skill Bundles）- 可选

可以将多个技能打包，方便复用：

```yaml
# 在 skill_library.yaml 中
skill_bundles:
  - id: "web_delivery_bundle"
    name: "Web Delivery"
    description: "Standard bundle for web application delivery"
    skills:
      - skill_id: "requirements_analysis"
        min_level: 2
      - skill_id: "schema_design"
        min_level: 2
      - skill_id: "python_engineering"
        min_level: 2

# 在 role_schema.yaml 中引用 bundle
roles:
  - id: "full_stack_developer"
    required_skills:
      # 方式1：直接引用 bundle（会自动展开）
      - skill_id: "web_delivery_bundle"
        min_level: 1
      # 方式2：也可以混合使用
      - skill_id: "test_driven_development"
        min_level: 2
```

### 4. 技能工作流（Skill Workflows）- 高级功能

定义多个技能的执行顺序和依赖关系：

```yaml
# 在 skill_library.yaml 中
skill_workflows:
  - id: "feature_delivery"
    name: "功能交付流程"
    description: "从需求到实现的完整功能交付工作流"
    trigger:
      stage_id: "implementation"
      condition: "auto"
    steps:
      - step_id: "analyze_requirements"
        skill_id: "requirements_analysis"
        order: 1
        inputs:
          goal: "{{workflow.inputs.goal}}"
        outputs:
          - "requirements_doc"
      
      - step_id: "design_schema"
        skill_id: "schema_design"
        order: 2
        depends_on:
          - "analyze_requirements"
        inputs:
          requirements: "{{steps.analyze_requirements.outputs.requirements_doc}}"
        outputs:
          - "data_schema"
      
      - step_id: "implement_code"
        skill_id: "python_engineering"
        order: 3
        depends_on:
          - "design_schema"
        inputs:
          schema: "{{steps.design_schema.outputs.data_schema}}"
        outputs:
          - "source_code"
```

## 使用示例

### 示例 1: 基本配置

**场景**：创建一个需要需求分析技能的产品分析师角色

**步骤 1**: 在 `skill_library.yaml` 中定义技能

```yaml
skills:
  - id: "requirements_analysis"
    name: "Requirements Analysis"
    description: "分析用户需求并生成需求文档"
    dimensions: ["elicitation", "scope_alignment"]
    levels:
      1: "理解基本模板并捕获用户需求"
      2: "能够建模流程、风险和非功能性需求"
      3: "领导复杂发现，协调冲突的利益相关者"
    tools: ["markdown", "diagrams"]
```

**步骤 2**: 在 `role_schema.yaml` 中定义角色并引用技能

```yaml
roles:
  - id: "product_analyst"
    name: "Product Analyst"
    description: "定义需求和范围"
    required_skills:
      - skill_id: "requirements_analysis"
        min_level: 2
    constraints:
      allowed_actions: ["define_requirements"]
      forbidden_actions: ["write_code"]
```

**步骤 3**: 使用角色

```bash
# 使用角色执行任务
workflow role-execute product_analyst "分析用户登录功能需求"
```

### 示例 2: 多技能角色

**场景**：创建一个需要多个技能的系统架构师角色

```yaml
roles:
  - id: "system_architect"
    name: "System Architect"
    description: "设计系统架构"
    required_skills:
      - skill_id: "system_design"
        min_level: 2
      - skill_id: "schema_design"
        min_level: 2
      - skill_id: "requirements_analysis"  # 也需要需求分析技能
        min_level: 1
    constraints:
      allowed_actions: ["design_architecture", "define_schemas"]
```

### 示例 3: 使用技能包

**场景**：快速配置一个全栈开发角色

```yaml
# 1. 先定义技能包（在 skill_library.yaml）
skill_bundles:
  - id: "full_stack_bundle"
    name: "Full Stack Bundle"
    skills:
      - skill_id: "requirements_analysis"
        min_level: 1
      - skill_id: "system_design"
        min_level: 2
      - skill_id: "python_engineering"
        min_level: 2
      - skill_id: "test_driven_development"
        min_level: 2

# 2. 在角色中引用（在 role_schema.yaml）
roles:
  - id: "full_stack_developer"
    name: "Full Stack Developer"
    required_skills:
      - skill_id: "full_stack_bundle"
        min_level: 1
```

### 示例 4: 技能级别要求

**场景**：不同角色对同一技能有不同级别要求

```yaml
# 初级开发者只需要级别 1
roles:
  - id: "junior_developer"
    required_skills:
      - skill_id: "python_engineering"
        min_level: 1  # 只需要基础级别

# 高级开发者需要级别 2
roles:
  - id: "senior_developer"
    required_skills:
      - skill_id: "python_engineering"
        min_level: 2  # 需要高级别
```

## 最佳实践

### 1. 技能设计原则

- **单一职责**：每个技能应该专注于一个明确的能力领域
- **可复用性**：技能应该设计为可在多个角色间共享
- **清晰描述**：技能描述应该清楚地说明它能做什么
- **级别定义**：明确定义 1-3 级的区别，便于角色选择合适的级别

### 2. 角色设计原则

- **职责明确**：每个角色应该有清晰的职责边界
- **技能匹配**：角色的技能应该与其职责相匹配
- **级别合理**：根据角色职责选择合适的技能级别要求
- **约束清晰**：明确定义允许和禁止的操作

### 3. 组织建议

```
teams/
  your-team/
    role_schema.yaml      # 定义角色
    skill_library.yaml    # 定义技能库
    skills/               # 技能实现（Anthropic 格式）
      requirements_analysis/
        Skill.md
      system_design/
        Skill.md
```

### 4. 验证和测试

系统会自动验证：
- ✅ 角色引用的技能是否存在于技能库中
- ✅ 技能级别是否有效（1-3）
- ✅ 技能包中的技能是否存在

如果验证失败，系统会抛出 `ValidationError` 并提示具体问题。

## 常见问题

### Q1: 一个角色可以需要多少个技能？

**A**: 没有硬性限制，但建议：
- 简单角色：1-3 个技能
- 复杂角色：3-5 个技能
- 如果超过 5 个，考虑使用技能包（Skill Bundle）

### Q2: 技能级别 1、2、3 有什么区别？

**A**: 级别定义在技能库中，例如：

```yaml
levels:
  1: "基础级别 - 理解基本模板并捕获用户需求"
  2: "中级级别 - 能够建模流程、风险和非功能性需求"
  3: "高级级别 - 领导复杂发现，协调冲突的利益相关者"
```

角色通过 `min_level` 指定最低要求。

### Q3: 如何知道一个角色有哪些可用技能？

**A**: 使用命令查看：

```bash
# 查看所有角色
workflow list-roles

# 查看角色的详细信息（包括技能）
workflow role-info <role_id>
```

### Q4: 技能和技能工作流（Skill Workflow）有什么区别？

**A**: 
- **Skill**: 单个能力单元，可以被角色引用
- **Skill Workflow**: 多个技能的组合，定义执行顺序、依赖关系和数据流

技能工作流适用于需要按特定顺序执行多个技能的复杂场景。

### Q5: 如何添加新技能？

**A**: 步骤：

1. 在 `skill_library.yaml` 中添加技能定义
2. 在 `skills/` 目录下创建技能实现（Anthropic 格式）
3. 在需要该技能的角色中添加 `required_skills`

### Q6: 角色可以继承其他角色的技能吗？

**A**: 目前不支持技能继承，但可以通过以下方式实现类似效果：

1. 使用技能包（Skill Bundle）定义常用技能组合
2. 多个角色引用同一个技能包

### Q7: 如何验证配置是否正确？

**A**: 系统在加载配置时会自动验证：

```bash
# 初始化时会自动验证
workflow init

# 如果配置有误，会显示详细的错误信息
```

### Q8: 技能可以在运行时动态选择吗？

**A**: 是的！系统支持动态技能选择：

- `SkillSelector` 会根据任务描述、历史记录和上下文智能选择最合适的技能
- 技能工作流支持 `dynamic_skill` 配置，可以在运行时根据条件选择技能

## 总结

**核心要点**：

1. **Role 通过 `required_skills` 引用 Skill**
2. **Skill 定义在 `skill_library.yaml` 中**
3. **Role 定义在 `role_schema.yaml` 中**
4. **系统会自动验证技能是否存在**
5. **可以使用技能包和工作流组织复杂场景**

**快速检查清单**：

- [ ] 技能已定义在 `skill_library.yaml` 中
- [ ] 角色已定义在 `role_schema.yaml` 中
- [ ] 角色的 `required_skills` 中的 `skill_id` 存在于技能库中
- [ ] 技能级别要求合理（1-3）
- [ ] 配置已通过验证

---

📚 **相关文档**：
- [快速开始指南](QUICKSTART.md)
- [架构文档](docs/ARCHITECTURE.md)
- [API 文档](docs/API.md)
- [技能指南](docs/SKILLS_GUIDE.md)

