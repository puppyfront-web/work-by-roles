---
name: Schema and DSL Design
description: Design structured schemas and DSLs with validation rules
id: schema_design
dimensions:
- structure_modelling
- validation_rules
- extensibility
tools:
- yaml
- jsonschema
constraints:
- must_define_schema_version
- must_define_validation_rules
levels:
  1: Designs simple schemas with required fields
  2: Adds validation, versioning, and compatibility rules
  3: Designs evolvable DSLs with backward compatibility
metadata:
  execution_mode: "analysis"
  execution_tools:
    - file_write
    - file_read
    - code_search
  execution_capabilities:
    - "write_schema_documents"
    - "define_data_structures"
    - "create_validation_rules"
---
# Schema and DSL Design

## 概述

Design structured schemas and DSLs with validation rules

## 能力维度

### Structure Modelling

<!-- Add dimension-specific guidance here -->

### Validation Rules

<!-- Add dimension-specific guidance here -->

### Extensibility

<!-- Add dimension-specific guidance here -->

## 工具支持

- **yaml**: <!-- Add tool description -->
- **jsonschema**: <!-- Add tool description -->

## 约束条件

- must_define_schema_version
- must_define_validation_rules

## 能力等级

### Level 1

Designs simple schemas with required fields

### Level 2

Adds validation, versioning, and compatibility rules

### Level 3

Designs evolvable DSLs with backward compatibility

