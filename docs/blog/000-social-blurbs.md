# 短文案组（社交媒体发布用）

## 即刻 / 朋友圈版

折腾了一周末的事：给自己的开源项目搭了条 AI 内容流水线——三个 AI 写手按"故事型/干货型/案例型"竞稿，AI 主编合成终稿，发布前再过一遍"事实核查+平台合规+转化力"评审。

结果终稿被自己的评审团拒了：①"一行 pip 就能装"——包还没发 PyPI，虚假陈述；②"评论区扣『治理』发资料"——诱导互动+私域引流；③"GitHub 求 star"——站外导流高风险。连"改不翻车"和"改一行 prompt 全崩"的自相矛盾都被揪出来了。

这就是我做 work-by-roles（LLM 专家团治理系统）的原因：像管理代码一样管理 AI 角色——契约版本化、运行时强制、结论带证据、变更有回归。首跑还抓出我引擎 3 个 bug，全靠审计留痕定位的。

GitHub 搜 work-by-roles，391 个测试全绿，MIT。你的日常里哪个环节需要"多视角+一道把关"，哪个环节就值得一个专家团。

## X / Twitter 版（英文）

I built an AI content pipeline with my own open-source project:
3 writers compete → chief editor synthesizes → a review panel gates before publishing.

The panel REJECTED the final draft:
- "installable via pip" → the package isn't on PyPI. False claim.
- "comment 'X' to get the doc" → engagement bait, platform red line
- "give us a star" → off-site diversion, high severity
- even caught a self-contradiction I missed

Governance isn't bureaucracy. It's the editor who doesn't nod along.

work-by-roles: contracts, review paradigm, regression gates, full-chain audit.
391 tests green, MIT. ⬇️

## V2EX 版开头（替换主稿第一段，其余同掘金稿）

写这个贴主要是两个目的：一是发布一个周末折腾出来的东西，二是记录一个挺有意思的过程——我用自己写的多 Agent 治理库给自己搭了条内容流水线，结果它的评审团把我让 AI 写的推广稿拒了，拒得我心服口服（细节见正文）。技术讨论和拍砖都欢迎。

## 发布清单（发布前逐项确认）

- [ ] 替换文中「你的仓库名」为实际 GitHub 链接（3 处：主稿 CTA、即刻版、X 版）
- [ ] 录制画布运行 GIF（30~45 秒：导入模板 → 跑会审 → 分歧高亮 → 导审计包），插入主稿"30 秒上手"之后
- [ ] PyPI 发布完成后：删除主稿"诚实声明"中的未发布披露，并改回 `pip install work-by-roles`
- [ ] 评论区准备一个"完整运行记录"的置顶回复（可直接链接 docs/REAL_WORLD_VALIDATION.md §7）
- [ ] Key 轮换确认：验证用的 DeepSeek Key 已作废换新，新 Key 只存在于环境变量
