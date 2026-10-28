# closed-loop-skills

**跨代理、跨项目的诊断与修复工作流：先区分源数据与当前代码问题，再确认方案、修复、验证返工，最后交人工验收。**

适用于后端 API、前端、数据处理、命令行工具、自动化任务和文档生成。不要求使用某一种模型、开发语言、截图工具或发布系统。

## 核心逻辑

异常结果 → 追溯实际输入、需求契约、代码/配置/环境：

- 数据问题：带证据反馈用户或上游，不靠代码掩盖。
- 代码问题：具体原因、方案、预期效果 → 用户确认 → 修改 → 实际验证 → 未通过则有界返工 → 候选就绪 → 用户验收。
- 混合问题：拆分数据与代码责任，分别处理。
- 无法确定：补证据或对齐期望，不盲改。

归因依据契约判断。错误 CSV 导致按约定拒绝导入，可以反馈数据问题；接口本应返回校验错误却崩溃，仍存在代码缺陷。不要给程序应有的校验和容错责任免责。

非视觉任务用测试、返回值、日志或计算结果验证；视觉任务才需要截图。自动门禁通过只代表 ready_for_human，不代表已获用户验收或已部署。

## 快速使用

下载仓库，完整保留 skills/closed-loop-repair/ 目录，让代理读取：

```text
读取 <本机路径>/closed-loop-repair/SKILL.md，按需加载它引用的文件。
检查 <项目路径> 的 <异常>，先判断源数据还是当前代码、配置或环境问题，
给出根因证据、修复方案和预期效果。确认后修改，自己验证并返工，
通过项目门禁后再交给我验收。缺少工具能力时明确说明，不虚构验证结果。
```

| 使用环境 | 使用方式 | 验证情况 |
| --- | --- | --- |
| Codex | 原生安装完整 skill 目录，或直接读取文件；安装后调用技能名称 | skill 格式与本地 Python 门禁已检查；未验证真实跨项目修复效果 |
| WorkBuddy、DeepSeek 驱动的其他客户端 | 先使用本地文件读取入口；原生导入以所用版本文档为准 | 未实机验证原生导入或完整闭环 |
| 其他支持本地文件的 AI 代理 | 显式加载 SKILL.md，按能力执行 | 需在对应宿主验证 |

具体安装、调用与能力降级见 [跨代理使用](skills/closed-loop-repair/references/portability.md)。模型名称不决定客户端是否支持 skills，不宣称任何客户端均可一键导入。

## 项目接入

沿用项目规则、复现方法和已有门禁，明确输入、代码、结果和完成标准。参见 [项目接入](skills/closed-loop-repair/references/project-adapter.md)。

examples/project.json 与 examples/issue.json 是无需截图的 CSV 金额转换案例，全部为自造示例，不是实际执行证据。视觉项目可设置 visual 为 true，添加 visual_check 与 before/after 截图路径。

## 可选证据检查器

scripts/evidence_gate.py 位于 skill 目录，使用 Python 3.9+ 标准库，无需 pip、API key、MCP 或网络。检查源码、输入、候选与报告版本，阻止未确认方案、版本漂移、未声明修改及旧报告沿用。

它不执行项目测试、不判断截图或诊断语义、不认证确认者身份。日志、结果查看与人工确认必须真实发生。没有 Python 时仍可使用 skill，保留同样的事实记录并使用项目门禁；不能声称已运行未执行的脚本。详见 [门禁说明](skills/closed-loop-repair/references/gate-usage.md)。

## 验证与限制

```text
python -m unittest discover -s tests -v
```

测试使用隔离临时项目，覆盖证据门禁行为，不证明任何模型都能正确归因或修复。真实客户端试跑使用 [跨领域行为场景](skills/closed-loop-repair/references/behavior-scenarios.md)，尚未实跑的场景明确标为待验证。

examples/github-actions-test.yml 是 Windows/Linux CI 示例，尚未启用；需要时放入 .github/workflows/ 并使用具备权限的凭据推送。

Skill 是工作流指导，不是独立运行的后台系统。完整执行依赖宿主的读取/编辑、命令执行和结果查看能力。仓库不含客户数据、业务源码或内部地址。
