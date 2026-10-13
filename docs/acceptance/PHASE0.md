# 阶段0 验收报告（PHASE0）

> 日期：2026-10-14 · 依据：SPEC-001 · 结论：**通过，进入阶段1**

## 1. 验收标准核对

| SPEC-001 验收标准 | 证据 | 结果 |
|---|---|---|
| 目录结构完全对齐 SPEC-000 §5 | `tests/wbr/phase0/test_structure.py::test_directory_structure_aligned` | ✅ |
| 可直接 import 所有 core 模块 | `test_phase0_modules_importable`（7 模块） | ✅ |
| Core 依赖纯净（D-01，AST 静态扫描） | `test_core_import_purity`（仅 stdlib+pydantic+wbr 自身） | ✅ |
| 全局异常统一（code/trace_id/序列化） | `test_exceptions.py` 18 用例 | ✅ |
| TraceID 唯一性与上下文传播语义 | `test_context.py`（1000 唯一 + 跨线程隔离 + span 作用域） | ✅ |
| 配置 YAML+代码双通道、overlay 不可变、未知键告警 | `test_config.py` 7 用例 | ✅ |
| 日志 JSON 单行含 trace_id、setup 幂等 | `test_logging.py` | ✅ |
| 审计总线不阻塞、溢出丢弃计数、有序广播、单例 | `test_audit_bus.py` 6 用例 | ✅ |
| `pip install -e .` 后 `import wbr` 可用、版本 0.1.0 | `test_packaging.py`（editable 安装 + metadata 校验） | ✅ |
| 存量回归不新增失败 | 见 §2 | ✅ |

**阶段0 测试统计：38 passed / 0 failed**（`.venv/bin/python -m pytest tests/wbr/phase0`）

## 2. 存量回归基线（重要记录）

回归标准（SPEC-000 §4.7）：不因本方案改动新增失败。实测对比：

| 运行 | 环境 | 结果 |
|---|---|---|
| 改动后（当前工作区） | venv Py3.13 | 14 failed / 7 errors / 176 passed |
| **stash 全部改动后（基线）** | venv Py3.13 | **14 failed / 7 errors / 176 passed（完全一致）** |
| 基线 | 系统 Py3.14 | 12 failed / 7 errors / 178 passed |

失败均为先于本方案存在的环境性问题：① legacy CLI 测试以 `python -m work_by_roles.cli` 启动子进程，但该包无 `__main__`；② 异步用例依赖 pytest-asyncio 未安装。**结论：本方案改动零回归。**（R17 记录的 test_learning_module_config 亦在其中）

## 3. 交付物清单
- 代码：`wbr/`（exceptions/context/constants/config/logging/audit_bus）、`wbr/config_loader.py`、pyproject（分层依赖 + packages.find）
- 测试：`tests/wbr/phase0/`（6 文件 38 用例）+ `tests/wbr/conftest.py`
- 文档：SPEC-000/001、本报告

## 4. 遗留事项
- 修复 legacy CLI/async 测试环境问题不在本方案范围（存量包冻结原则 D-02），已如实记录。
