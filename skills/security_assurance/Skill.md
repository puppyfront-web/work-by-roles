---
name: Security Assurance
description: Ensures system security through audits and automated scans
id: security_assurance
dimensions:
- threat_modelling
- vulnerability_scanning
- security_auditing
tools:
- bandit
- owasp-zap
- snyk
constraints:
- must_report_all_vulnerabilities
levels:
  1: Performs basic vulnerability scans
  2: Conducts threat modelling and security code reviews
  3: Designs secure architectures and leads response efforts

skill_type: "procedural"
side_effects:
  - "none"
deterministic: true
testable: true
---
# Security Assurance

## 概述

Ensures system security through audits and automated scans

## 能力维度

### Threat Modelling

<!-- Add dimension-specific guidance here -->

### Vulnerability Scanning

<!-- Add dimension-specific guidance here -->

### Security Auditing

<!-- Add dimension-specific guidance here -->

## 工具支持

- **bandit**: <!-- Add tool description -->
- **owasp-zap**: <!-- Add tool description -->
- **snyk**: <!-- Add tool description -->

## 约束条件

- must_report_all_vulnerabilities

## 能力等级

### Level 1

Performs basic vulnerability scans

### Level 2

Conducts threat modelling and security code reviews

### Level 3

Designs secure architectures and leads response efforts

