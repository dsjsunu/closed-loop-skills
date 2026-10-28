# 证据检查器

纯 Python 标准库，无自动执行任意命令、无网络、无部署。先实际运行项目验证并观察产物，再记录报告；禁止为凑 PASS 生成虚构结论。

以下命令在 skill 目录运行；路径参数均指向项目内文件。每个任务使用单独工作目录，例如 `.closed-loop/demo/`。

```text
python scripts/evidence_gate.py plan-hash --root PROJECT --issue .closed-loop/demo/issue.json
python scripts/evidence_gate.py capture --root PROJECT --config project.json --issue .closed-loop/demo/issue.json --out .closed-loop/demo/baseline.json
```

修改前 capture baseline。capture 不要求此时已产生候选，因此只捕获当时存在的 artifacts；diagnosis 阶段检查证据可用：

```text
python scripts/evidence_gate.py check --stage diagnosis --root PROJECT --config project.json --issue .closed-loop/demo/issue.json
```

用户确认方案后，把真实确认与 plan-hash 输出关联；完成修改和候选产物后 capture candidate：

```text
python scripts/evidence_gate.py capture --root PROJECT --config project.json --issue .closed-loop/demo/issue.json --out .closed-loop/demo/candidate.json
```

capture 打印 source_digest 和 artifacts_digest。实际检查该版本后，每个必需检查保存 JSON 报告（路径由 issue.checks 指定）：

```json
{"status":"PASS","summary":"实际执行的方法、覆盖案例与观察结果","source_digest":"capture 输出值","artifacts_digest":"capture 输出值"}
```

若外部验证器能直接生成该报告，优先使用；手工整理也必须忠实于真实执行。报告应引用详细日志/截图位置；脚本不独立证明报告内容属实。

```text
python scripts/evidence_gate.py check --stage ready --root PROJECT --config project.json --issue .closed-loop/demo/issue.json --baseline .closed-loop/demo/baseline.json --candidate .closed-loop/demo/candidate.json
```

ready 检查：已确认的实施方案、输入保护、实际修改清单、基线证据未被替换、候选及源码仍匹配、必需报告全部 PASS 且绑定同一版本。通过输出 `ready_for_human`，不修改任务记录、不代替用户验收。

证据文件在项目根内，拒绝路径越界、符号链接和目录联接。缺少配置根、空验证列表、混合/未定根因、文件漂移或报告失败均不放行。mixed 须拆成可独立归因的子任务；data 在诊断后走反馈分支，不进 ready。

这是协作一致性检查，不是防恶意篡改系统：能改脚本/快照的人可以绕过它。基线应在修改前保存，不重写来迁就候选；人工仍负责确认来源和可信度。
