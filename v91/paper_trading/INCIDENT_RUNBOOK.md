# Incident Runbook - Godfather V9.0 PT.4

## 数据缺失处理

### 症状
- 信号生成失败
- 市场数据缺失
- 预测数据不完整

### 处理步骤
1. 检查数据源连接
2. 确认数据文件完整性
3. 如果是单日缺失：跳过该日，记录 incident
4. 如果是连续缺失：触发 HALT，人工介入
5. 恢复前验证数据完整性

### 责任人
- 数据工程师

---

## Broker Reject 处理

### 症状
- 订单被拒绝
- Rejection rate 异常升高

### 处理步骤
1. 检查 rejection reason
2. 常见原因：
   - 资金不足：检查 cash constraint 逻辑
   - 停牌/不可交易：更新 tradable symbols list
   - Payload 错误：检查 broker adapter mapping
3. 单笔拒绝：记录并继续
4. 批量拒绝（>10%）：触发 HALT
5. 修复后通过 manual override 恢复

### 责任人
- 交易运维

---

## Partial Fill 处理

### 症状
- 订单部分成交
- Fill rate < 100%

### 处理步骤
1. 记录 partial fill 详情
2. 计算实际持仓 vs 目标持仓偏差
3. 如果偏差 < 5%：接受并继续
4. 如果偏差 >= 5%：
   - 标记为 WARN
   - 下一调仓日优先调整
5. 不触发 HALT（除非连续多日 partial fill）

### 责任人
- 组合经理

---

## Reconciliation Fail 处理

### 症状
- 对账不匹配
- Position diff / cash diff 超阈值

### 处理步骤
1. 立即触发 HALT
2. 检查三层对账：
   - Orders vs Fills
   - Expected positions vs Actual positions
   - Expected cash vs Actual cash
3. 定位差异来源：
   - 订单遗漏
   - 成交价格偏差
   - 费用计算错误
4. 人工核对 broker statement
5. 修正后更新 state
6. 通过 manual override 恢复

### 责任人
- 风控 + 交易运维

---

## 持仓不一致处理

### 症状
- Paper positions ≠ Shadow positions
- Position drift 持续扩大

### 处理步骤
1. 触发 HALT
2. 导出 paper positions 和 shadow positions
3. 逐票对比：
   - 数量差异
   - 成本差异
4. 定位根因：
   - Fill simulation 错误
   - State persistence 错误
   - Broker event 遗漏
5. 修正 state
6. 重新初始化 shadow broker
7. 通过 manual override 恢复

### 责任人
- 系统工程师

---

## 风控 HALT 后恢复

### 症状
- Risk state machine 进入 HALT 状态
- Can trade = False

### 处理步骤
1. 确认 HALT 原因：
   - 连续 WARN
   - 单日亏损超限
   - 回撤超限
   - Reconciliation fail
2. 评估是否已修复根因
3. 检查当前状态：
   - Positions
   - Cash
   - Risk metrics
   - Drift metrics
4. 如果根因已修复且状态正常：
   - 更新 risk_state_machine.json
   - 设置 manual_override = True
   - 重启系统
5. 观察 1-2 个调仓周期
6. 如果稳定，移除 manual_override

### 责任人
- 风控 + 组合经理

---

## Manual Override 权限

### 谁可以 Manual Override
- 组合经理（主要）
- 风控负责人（次要）
- CTO（紧急情况）

### Override 类型
1. **Soft Override**: 跳过单次 WARN
2. **Hard Override**: 从 HALT 恢复
3. **Degraded Mode**: 降级运行（仅观察，不下单）

### Override 流程
1. 记录 override reason
2. 更新 manual_override.json
3. 记录 audit log
4. 通知相关人员
5. 设置 review date

---

## 恢复前检查清单

### 数据层
- [ ] 市场数据完整
- [ ] 预测数据完整
- [ ] 历史数据可访问

### 状态层
- [ ] Positions 正确
- [ ] Cash 正确
- [ ] State files 完整

### 风控层
- [ ] Risk metrics 正常
- [ ] Drift metrics 正常
- [ ] No pending HALT

### 对账层
- [ ] Orders reconciled
- [ ] Fills reconciled
- [ ] Positions reconciled
- [ ] Cash reconciled

### 系统层
- [ ] No duplicate runs
- [ ] No stale locks
- [ ] Logs accessible
- [ ] Monitoring active

---

## 紧急联系人

- 组合经理: [CONTACT]
- 风控负责人: [CONTACT]
- 交易运维: [CONTACT]
- 系统工程师: [CONTACT]
- CTO: [CONTACT]

---

## Incident 升级路径

1. **Level 1 (INFO)**: 单笔订单问题，自动处理
2. **Level 2 (WARN)**: 多笔订单问题，需要关注
3. **Level 3 (HALT)**: 系统停止交易，需要人工介入
4. **Level 4 (CRITICAL)**: 资金/持仓严重不一致，立即升级至 CTO
