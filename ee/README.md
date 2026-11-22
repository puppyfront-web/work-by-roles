# ee/ 企业目录

这里是商业许可代码的边界，不是功能目录。阶段 1 不在这里放任何实现。

## 开源核心（MIT）

- `wbr/`：契约、会审、审计协议、模板、适配器
- `studio/`：自托管产品壳（账号、加密的自带密钥、团队、运行、Postgres 审计链、界面）
- 文档、示例、内核测试

这些目录可以按仓库根目录的 MIT 许可使用。

## 商业目录（本目录）

计划中的企业能力放在这里，例如组织与席位、SSO、审计导出包、保留策略。许可文本是 `ee/LICENSE`，目前是给维护者替换的草稿，还不能当成已经生效的商业合同。

约束：

- `wbr/` 和 `studio/` 不导入 `ee`
- 未替换 `ee/LICENSE` 之前不往这里提交功能
- 外部补丁如果只改开源核心，按 `CLA.md` 签署；不要把企业功能混进 MIT 目录

## English

`ee/` is the commercial-license boundary. It has no features yet. The MIT grant covers `wbr/` and `studio/`. `ee/LICENSE` is a placeholder the maintainer must finalize before any enterprise code is added. Open-core packages must not import `ee`.
