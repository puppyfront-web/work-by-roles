# Roles and Skills Relationship Guide

> This document details the relationship between Roles and Skills in the Work-by-Roles framework, and how to configure and use them.

## 📋 Table of Contents

- [Core Concepts](#core-concepts)
- [Relationship Structure](#relationship-structure)
- [Configuration Methods](#configuration-methods)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [FAQ](#faq)

## Core Concepts

### What is a Role?

**Role** defines "who" executes tasks, describing:
- Role responsibilities and boundaries
- Allowed and forbidden actions
- **Required skills** (defined through `required_skills`)
- Validation rules

### What is a Skill?

**Skill** defines "how" to execute tasks, describing:
- Skill capabilities and description
- Skill dimensions
- Skill levels (levels: 1-3)
- Tools used
- Constraints

### Relationship Essence

**Role is the consumer of skills, Skill is the provider of capabilities.**

- Role declares which skills are needed through `required_skills`
- Skill is an independent, reusable capability definition
- One Role can require multiple Skills
- One Skill can be used by multiple Roles

## Relationship Structure

### Data Models

```python
# Role Model
@dataclass
class Role:
    id: str
    name: str
    description: str
    required_skills: List[SkillRequirement]  # Key: List of skills required by role
    constraints: Dict[str, List[str]]
    validation_rules: List[str]

# SkillRequirement Model
@dataclass
class SkillRequirement:
    skill_id: str          # Reference to skill ID in Skill Library
    min_level: int         # Minimum skill level requirement (1-3)
    focus: Optional[List[str]]  # Optional skill focus areas

# Skill Model
@dataclass
class Skill:
    id: str
    name: str
    description: str
    dimensions: List[str]   # Skill dimensions
    levels: Dict[int, str]  # Skill level definitions
    tools: List[str]        # Tools used
    constraints: List[str]  # Constraints
```

### Relationship Diagram

```
┌─────────────────┐
│   Role          │
│                 │
│ required_skills │──┐
│   (List)        │  │
└─────────────────┘  │
                     │ Reference
                     ▼
         ┌───────────────────────┐
         │  SkillRequirement      │
         │                        │
         │  skill_id: "xxx"       │──┐
         │  min_level: 2          │  │
         │  focus: [...]          │  │
         └───────────────────────┘  │
                                    │ Lookup
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

## Configuration Methods

### 1. Define Skill Library

Define all available skills in `skill_library.yaml`:

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

### 2. Define Roles

Define roles in `role_schema.yaml` and reference skills:

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
    # Key: Reference skills through required_skills
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

### 3. Skill Bundles (Optional)

Package multiple skills for easy reuse:

```yaml
# In skill_library.yaml
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

# Reference bundle in role_schema.yaml
roles:
  - id: "full_stack_developer"
    required_skills:
      # Method 1: Direct bundle reference (will auto-expand)
      - skill_id: "web_delivery_bundle"
        min_level: 1
      # Method 2: Can also mix
      - skill_id: "test_driven_development"
        min_level: 2
```

### 4. Skill Workflows (Advanced Feature)

Define execution order and dependencies for multiple skills:

```yaml
# In skill_library.yaml
skill_workflows:
  - id: "feature_delivery"
    name: "Feature Delivery Process"
    description: "Complete feature delivery workflow from requirements to implementation"
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

## Usage Examples

### Example 1: Basic Configuration

**Scenario**: Create a product analyst role requiring requirements analysis skill

**Step 1**: Define skill in `skill_library.yaml`

```yaml
skills:
  - id: "requirements_analysis"
    name: "Requirements Analysis"
    description: "Analyze user requirements and generate requirements document"
    dimensions: ["elicitation", "scope_alignment"]
    levels:
      1: "Understand basic templates and capture user needs"
      2: "Can model flows, risks, and non-functional requirements"
      3: "Lead complex discovery, reconcile conflicting stakeholders"
    tools: ["markdown", "diagrams"]
```

**Step 2**: Define role in `role_schema.yaml` and reference skill

```yaml
roles:
  - id: "product_analyst"
    name: "Product Analyst"
    description: "Define requirements and scope"
    required_skills:
      - skill_id: "requirements_analysis"
        min_level: 2
    constraints:
      allowed_actions: ["define_requirements"]
      forbidden_actions: ["write_code"]
```

**Step 3**: Use role

```bash
# Execute task using role
workflow role-execute product_analyst "Analyze user login feature requirements"
```

### Example 2: Multi-Skill Role

**Scenario**: Create a system architect role requiring multiple skills

```yaml
roles:
  - id: "system_architect"
    name: "System Architect"
    description: "Design system architecture"
    required_skills:
      - skill_id: "system_design"
        min_level: 2
      - skill_id: "schema_design"
        min_level: 2
      - skill_id: "requirements_analysis"  # Also needs requirements analysis skill
        min_level: 1
    constraints:
      allowed_actions: ["design_architecture", "define_schemas"]
```

### Example 3: Using Skill Bundles

**Scenario**: Quickly configure a full-stack developer role

```yaml
# 1. First define skill bundle (in skill_library.yaml)
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

# 2. Reference in role (in role_schema.yaml)
roles:
  - id: "full_stack_developer"
    name: "Full Stack Developer"
    required_skills:
      - skill_id: "full_stack_bundle"
        min_level: 1
```

### Example 4: Skill Level Requirements

**Scenario**: Different roles have different level requirements for the same skill

```yaml
# Junior developer only needs level 1
roles:
  - id: "junior_developer"
    required_skills:
      - skill_id: "python_engineering"
        min_level: 1  # Only needs basic level

# Senior developer needs level 2
roles:
  - id: "senior_developer"
    required_skills:
      - skill_id: "python_engineering"
        min_level: 2  # Needs advanced level
```

## Best Practices

### 1. Skill Design Principles

- **Single Responsibility**: Each skill should focus on one clear capability area
- **Reusability**: Skills should be designed to be shared across multiple roles
- **Clear Description**: Skill descriptions should clearly state what they can do
- **Level Definition**: Clearly define differences between levels 1-3 for role selection

### 2. Role Design Principles

- **Clear Responsibilities**: Each role should have clear responsibility boundaries
- **Skill Matching**: Role skills should match their responsibilities
- **Reasonable Levels**: Choose appropriate skill level requirements based on role responsibilities
- **Clear Constraints**: Clearly define allowed and forbidden actions

### 3. Organization Suggestions

```
teams/
  your-team/
    role_schema.yaml      # Define roles
    skill_library.yaml    # Define skill library
    skills/               # Skill implementations (Anthropic format)
      requirements_analysis/
        Skill.md
      system_design/
        Skill.md
```

### 4. Validation and Testing

The system automatically validates:
- ✅ Whether skills referenced by roles exist in the skill library
- ✅ Whether skill levels are valid (1-3)
- ✅ Whether skills in skill bundles exist

If validation fails, the system will throw `ValidationError` and indicate specific issues.

## FAQ

### Q1: How many skills can a role require?

**A**: No hard limit, but recommended:
- Simple roles: 1-3 skills
- Complex roles: 3-5 skills
- If more than 5, consider using Skill Bundles

### Q2: What's the difference between skill levels 1, 2, and 3?

**A**: Level definitions are in the skill library, for example:

```yaml
levels:
  1: "Basic level - Understand basic templates and capture user needs"
  2: "Intermediate level - Can model flows, risks, and non-functional requirements"
  3: "Advanced level - Lead complex discovery, reconcile conflicting stakeholders"
```

Roles specify minimum requirements through `min_level`.

### Q3: How to know what skills a role has available?

**A**: Use commands to view:

```bash
# View all roles
workflow list-roles

# View detailed role information (including skills)
workflow role-info <role_id>
```

### Q4: What's the difference between Skill and Skill Workflow?

**A**: 
- **Skill**: Single capability unit that can be referenced by roles
- **Skill Workflow**: Combination of multiple skills, defining execution order, dependencies, and data flow

Skill workflows are suitable for complex scenarios requiring multiple skills in a specific order.

### Q5: How to add a new skill?

**A**: Steps:

1. Add skill definition in `skill_library.yaml`
2. Create skill implementation in `skills/` directory (Anthropic format)
3. Add `required_skills` in roles that need this skill

### Q6: Can roles inherit skills from other roles?

**A**: Currently not supported, but similar effects can be achieved through:

1. Use Skill Bundles to define common skill combinations
2. Multiple roles reference the same skill bundle

### Q7: How to verify configuration is correct?

**A**: The system automatically validates when loading configuration:

```bash
# Automatically validates during initialization
workflow init

# If configuration has errors, detailed error messages will be displayed
```

### Q8: Can skills be dynamically selected at runtime?

**A**: Yes! The system supports dynamic skill selection:

- `SkillSelector` intelligently selects the most suitable skill based on task description, history, and context
- Skill workflows support `dynamic_skill` configuration, allowing skill selection at runtime based on conditions

## Summary

**Key Points**:

1. **Role references Skill through `required_skills`**
2. **Skill is defined in `skill_library.yaml`**
3. **Role is defined in `role_schema.yaml`**
4. **System automatically validates skill existence**
5. **Can use skill bundles and workflows to organize complex scenarios**

**Quick Checklist**:

- [ ] Skills defined in `skill_library.yaml`
- [ ] Roles defined in `role_schema.yaml`
- [ ] `skill_id` in role's `required_skills` exists in skill library
- [ ] Skill level requirements are reasonable (1-3)
- [ ] Configuration has passed validation

---

📚 **Related Documentation**:
- [Quick Start Guide](QUICKSTART.md)
- [Architecture Documentation](docs/ARCHITECTURE.md)
- [API Documentation](docs/API.md)
