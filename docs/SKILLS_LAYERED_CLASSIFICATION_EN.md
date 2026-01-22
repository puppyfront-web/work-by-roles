# Layered Skills Classification

## Classification Criteria

- **Shared Skills**: Cross-role common, tool/methodology oriented, weak role position dependency.
- **Role-Cohesive Skills**: Strong role position/decision boundaries/output artifact binding.
- **Skills Requiring Splitting**: Describe multi-stage processes, multiple outputs, or overlapping responsibilities, recommended to split into multiple atomic skills or combine as workflow.

## Classification Results (All Skill.md)

| skill_id | Current Location | Suggested Category | Reason | Suggested Location |
| --- | --- | --- | --- | --- |
| requirements_analysis | `skills/requirements_analysis/Skill.md` + templates + teams | Shared | Capability description is generic requirements gathering and acceptance criteria definition, not bound to specific role position | `skills/requirements_analysis/` |
| system_design | `skills/system_design/Skill.md` + templates + teams | Shared | Architecture and system decomposition methodology, reusable across roles/teams | `skills/system_design/` |
| schema_design | `skills/schema_design/Skill.md` + templates + teams | Shared | DSL/Schema design methodology, highly generic | `skills/schema_design/` |
| python_engineering | `skills/python_engineering/Skill.md` + templates + teams | Shared | Tool-oriented engineering capability, emphasizes toolchain and practices | `skills/python_engineering/` |
| test_driven_development | `skills/test_driven_development/Skill.md` + templates + teams | Shared | Testing methodology and tool operations, reusable across roles | `skills/test_driven_development/` |
| quality_assurance | `skills/quality_assurance/Skill.md` + templates + teams | Shared | Generic quality verification processes and capabilities, not bound to single role position | `skills/quality_assurance/` |
| security_assurance | `skills/security_assurance/Skill.md` + templates | Shared | Security audit/scanning capability, can be reused by security roles or engineering roles | `skills/security_assurance/` |

## Skills Requiring Splitting

Currently scanned skill descriptions are all capability dimensions and constraint definitions, no obvious "multi-stage process/multiple responsibility overlap" content found, no skills requiring splitting discovered yet.

## Migration and Deduplication Recommendations

- Use `skills/` as the main source for shared skills.
- `teams/**/skills` and `templates/**/skills` can be considered initialization snapshots or override sources (if differentiation is needed).
- If role-specific "cognitive stance" skills appear later, they can remain in team/role directories without moving to shared layer.
