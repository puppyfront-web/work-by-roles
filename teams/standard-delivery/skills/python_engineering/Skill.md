---
name: Python Engineering
description: Build production-grade Python in {{project.paths.src}} with typing and
  testing
id: python_engineering
dimensions:
- typing
- testing
- error_handling
tools:
- '{{project.standards.ruff or ''ruff''}}'
- '{{project.standards.mypy or ''mypy''}}'
- '{{project.standards.pytest or ''pytest''}}'
constraints:
- must_use_type_hints
- must_cover_tests in {{project.paths.tests}}
levels:
  1: Writes typed functions and basic tests
  2: Designs modules with dataclasses and robust errors
  3: Delivers frameworks with strong contracts and tooling
skill_type: "procedural"
side_effects:
  - "file_write"
deterministic: false
testable: true
metadata:
  execution_mode: "implementation"
  execution_tools:
    - file_write
    - file_modify
    - file_read
    - code_search
    - command_execute
  execution_capabilities:
    - "write_code"
    - "modify_code"
    - "create_modules"
    - "implement_functions"
    - "select_programming_language"
---
# Python Engineering

## 概述

Build production-grade Python in {{project.paths.src}} with typing and testing

## 能力维度

### Typing

<!-- Add dimension-specific guidance here -->

### Testing

<!-- Add dimension-specific guidance here -->

### Error Handling

<!-- Add dimension-specific guidance here -->

## 工具支持

- **{{project.standards.ruff or 'ruff'}}**: <!-- Add tool description -->
- **{{project.standards.mypy or 'mypy'}}**: <!-- Add tool description -->
- **{{project.standards.pytest or 'pytest'}}**: <!-- Add tool description -->

## 约束条件

- must_use_type_hints
- must_cover_tests in {{project.paths.tests}}

## 能力等级

### Level 1

Writes typed functions and basic tests

### Level 2

Designs modules with dataclasses and robust errors

### Level 3

Delivers frameworks with strong contracts and tooling

