# 分层技能分类清单

## 分类标准

- **共享型技能**：跨角色通用、工具性/方法论、弱角色立场依赖。
- **角色内聚技能**：强角色立场/决策边界/输出工件绑定。
- **需拆分技能**：描述多阶段流程、多个输出或职责叠加，建议拆为多个原子技能或改为 workflow 组合。

## 分类结论（全量 Skill.md）

| skill_id | 当前位置 | 建议归类 | 理由 | 建议落位 |
| --- | --- | --- | --- | --- |
| requirements_analysis | `skills/requirements_analysis/Skill.md` + templates + teams | 共享 | 能力描述为通用需求获取与验收标准制定，不绑定特定角色立场 | `skills/requirements_analysis/` |
| system_design | `skills/system_design/Skill.md` + templates + teams | 共享 | 架构与系统分解方法论，跨角色/团队复用 | `skills/system_design/` |
| schema_design | `skills/schema_design/Skill.md` + templates + teams | 共享 | DSL/Schema 设计方法论，通用性强 | `skills/schema_design/` |
| python_engineering | `skills/python_engineering/Skill.md` + templates + teams | 共享 | 工具性工程能力，强调工具链与实践 | `skills/python_engineering/` |
| test_driven_development | `skills/test_driven_development/Skill.md` + templates + teams | 共享 | 测试方法论与工具操作，跨角色复用 | `skills/test_driven_development/` |
| quality_assurance | `skills/quality_assurance/Skill.md` + templates + teams | 共享 | 质量验证通用流程与能力，不绑定单一角色立场 | `skills/quality_assurance/` |
| security_assurance | `skills/security_assurance/Skill.md` + templates | 共享 | 安全审计/扫描能力，可被安全角色或工程角色复用 | `skills/security_assurance/` |

## 需拆分技能

当前扫描到的技能描述均为能力维度与约束定义，没有明显“多阶段流程/多职责叠加”的内容，暂未发现需要拆分的技能。

## 迁移与去重建议

- 以 `skills/` 作为共享技能的主来源。
- `teams/**/skills` 与 `templates/**/skills` 可视为初始化快照或覆盖来源（如需差异化）。
- 若后续出现角色专属“认知姿态”技能，可保留在团队/角色目录，不必上移共享层。
