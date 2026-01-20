---
name: Quality Assurance & Validation
description: Validates outputs, gates, and workflow compliance
id: quality_assurance
dimensions:
- gate_definition
- reporting
- automation
tools:
- pytest
- report_generators
constraints:
- must_record_findings
levels:
  1: Runs manual checks and reports results
  2: Automates gate execution and reporting
  3: Designs reusable validation suites and metrics
skill_type: "procedural"
side_effects:
  - "none"
deterministic: true
testable: true
---
# Quality Assurance & Validation

## 概述

Validates outputs, gates, and workflow compliance

## 能力维度

### Gate Definition

<!-- Add dimension-specific guidance here -->

### Reporting

<!-- Add dimension-specific guidance here -->

### Automation

<!-- Add dimension-specific guidance here -->

## 工具支持

- **pytest**: <!-- Add tool description -->
- **report_generators**: <!-- Add tool description -->

## 约束条件

- must_record_findings

## 能力等级

### Level 1

Runs manual checks and reports results

### Level 2

Automates gate execution and reporting

### Level 3

Designs reusable validation suites and metrics

