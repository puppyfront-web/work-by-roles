# Contributor License Agreement

DRAFT — the maintainer must have counsel review this text before it is treated as binding. The CLA Assistant workflow points at this file.

This draft describes the intended grant. It is not a substitute for the finished agreement.

## 中文

向本仓库提交贡献（issue 里的代码建议除外，以 Pull Request 为准），即表示你同意：

1. 你有权贡献这些内容。
2. 对 `wbr/`、`studio/` 以及其他不在 `ee/` 下的贡献，你授予维护者及仓库接收方一项永久、全球、非独占、免版税、可再许可的许可，以便在 MIT 许可下使用、修改和再分发。
3. 对将来放入 `ee/` 的贡献（当前目录还没有功能代码），你授予同样范围的许可，以便维护者按 `ee/LICENSE` 定稿后的商业条款使用。在 `ee/LICENSE` 仍是草稿时，请不要向 `ee/` 提交功能。
4. 你没有把雇主或其他第三方的未授权代码放进来。

维护者邮箱：puppy.front@gmail.com

机器人会在 Pull Request 上要求评论：

```text
I have read the CLA Document and I hereby sign the CLA
```

签名记录写在分支 `cla-signatures` 的 `signatures/version1/cla.json`，不进 `main`。

## English

By opening a pull request you agree that you can grant the project a perpetual, worldwide, non-exclusive, royalty-free, sublicensable license to use your contribution. Contributions outside `ee/` are distributed under MIT. Contributions intended for `ee/` (none yet) may be used under the commercial terms the maintainer finalizes in `ee/LICENSE`.

This document is a placeholder. The maintainer must replace it with a reviewed CLA before relying on it.

The check is `.github/workflows/cla.yml` (contributor-assistant/github-action@v2.6.1). Upstream archived that action in March 2026. If GitHub stops running its Node.js 20 runtime, pin a maintained fork and keep `path-to-document` pointed at this file.
