# 任务记录

使用 examples/issue.json 的字段，或者保留项目已有格式并记录相同事实。

- `root_cause`：data / implementation / mixed / undetermined。
- `diagnosis`：可验证的归因说明。
- `diagnosis_evidence`：项目内证据文件相对路径，不能只有一段没有来源的结论。
- `plan`：拟改位置、机制、预期效果、影响和验证方案。
- `approval`：`plan_sha256`、真实用户原话 `quote`、会话引用 `reference`。检查器只能核对字段和哈希，不能认证人类身份；代理不得代写确认。
- `changed_files`：实际修改的源码文件，须与基线到候选的差异完全一致。
- `artifacts`：命名证据文件；至少 baseline、candidate，视觉任务还需 before、after。
- `checks`：每个必需检查指向一个 JSON 报告。报告含 status、summary、source_digest 和 artifacts_digest。
- `status`：diagnosing / awaiting_plan_confirmation / implementing / verifying / ready_for_human / accepted / reported_data_issue / blocked / manual_review / error。
- `next_action`、`attempts`：恢复线索与实际返工次数。

哈希绑定防止沿用旧报告，不证明诊断正确。人工验收必须来自真实对话，且绑定具体候选；此版本的检查器不记录 accepted 或执行部署。
