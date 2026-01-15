---
name: Test Driven Development
description: Designs tests in {{project.paths.tests}} before implementation
id: test_driven_development
dimensions:
- unit_tests
- integration_tests
- coverage_goals
tools:
- '{{project.standards.pytest or ''pytest''}}'
- coverage
constraints:
- must_block_on_test_failure
levels:
  1: Writes unit tests for core logic
  2: Covers edge cases and negative paths
  3: Designs executable specifications and fixtures
metadata:
  execution_mode: "implementation"
  execution_tools:
    - file_write
    - file_modify
    - file_read
    - command_execute
  execution_capabilities:
    - "write_tests"
    - "create_test_files"
    - "run_tests"
    - "verify_test_coverage"
---
# Test Driven Development

## 概述

Designs tests in {{project.paths.tests}} before implementation

## 能力维度

### Unit Tests

<!-- Add dimension-specific guidance here -->

### Integration Tests

<!-- Add dimension-specific guidance here -->

### Coverage Goals

<!-- Add dimension-specific guidance here -->

## 工具支持

- **{{project.standards.pytest or 'pytest'}}**: <!-- Add tool description -->
- **coverage**: <!-- Add tool description -->

## 约束条件

- must_block_on_test_failure

## 能力等级

### Level 1

Writes unit tests for core logic

### Level 2

Covers edge cases and negative paths

### Level 3

Designs executable specifications and fixtures

