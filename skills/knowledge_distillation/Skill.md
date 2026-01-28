---
name: Knowledge Distillation
description: Distills iteration lessons, categorizes them, and injects them into the most relevant Skill.md files with deduplication.
id: knowledge_distillation
dimensions:
  - classification
  - deduplication
  - skill_injection
tools:
  - markdown
  - file_read
  - file_write
  - code_search
constraints:
  - must_identify_target_skill_accurately
  - must_check_existing_lessons_to_prevent_duplicates
  - must_maintain_consistent_lesson_format
  - must_only_modify_lessons_learned_section
input_schema:
  type: object
  required:
    - task_context
    - execution_artifacts
    - available_skills
  properties:
    task_context:
      type: object
      description: Original goals, requirements, and user feedback.
    execution_artifacts:
      type: object
      description: Logs, diffs, errors, and retry traces.
    available_skills:
      type: array
      items:
        type: string
      description: List of available Skill IDs or paths that can be updated.
output_schema:
  type: object
  required:
    - updates
  properties:
    updates:
      type: array
      items:
        type: object
        required:
          - target_skill_id
          - action
          - lesson_content
        properties:
          target_skill_id:
            type: string
          action:
            type: string
            enum: ["add", "merge", "update", "ignore"]
          lesson_content:
            type: object
            required: ["context", "lesson", "impact", "evidence"]
            properties:
              context: {type: string}
              lesson: {type: string}
              impact: {type: string}
              evidence: {type: string}
skill_type: "cognitive"
side_effects:
  - "file_write"
deterministic: false
testable: true
metadata:
  execution_mode: "analysis"
  execution_tools:
    - file_read
    - file_write
    - code_search
  execution_capabilities:
    - "skill_categorization"
    - "knowledge_deduplication"
    - "automated_skill_evolution"
---
# Knowledge Distillation

## 概述

Analyze iteration data to extract reusable lessons, categorize them into the most relevant skills, and perform idempotent updates to Skill.md files.

## 能力维度

### Classification

Determine which specific skill (e.g., `python_engineering`, `schema_design`) a lesson most accurately belongs to.

### Deduplication

Analyze existing "Lessons Learned" sections in target skills to ensure new entries provide unique value and don't replicate existing knowledge.

### Skill Injection

Precisely inject or merge structured lessons into the target Skill.md files while preserving the overall file structure.

## 工具支持

- **markdown**: Parse and generate formatted Markdown for Skill sections.
- **file_read**: Load existing Skill.md files for context and deduplication checks.
- **file_write**: Apply targeted updates to Skill.md files.
- **code_search**: Cross-reference lessons with actual code implementation for validation.

## 约束条件

- must_identify_target_skill_accurately
- must_check_existing_lessons_to_prevent_duplicates
- must_maintain_consistent_lesson_format
- must_only_modify_lessons_learned_section

## 能力等级

### Level 1
Identifies obvious lessons and adds them to a generic "General" skill or log.

### Level 2
Correctly categorizes lessons into specific functional skills and avoids exact duplicates.

### Level 3
Performs semantic deduplication, merges related lessons into more powerful generalized rules, and maintains a highly optimized Skill library.
