# KangaBase 5分钟体验方案 🦘

> 目标：从零开始，亲手走完 KangaBase 核心链路
> 预计时间：5-10 分钟
> 前置要求：Python 3.9+

---

## 第一步：一键启动（30秒）

```bash
cd kangabase
bash quickstart.sh --no-venv
```

会自动：安装依赖 → 跑 Demo → 跑测试 → 显示结果。

看到 `68 passed` 和 Demo 全流程输出就说明环境 OK。

---

## 第二步：交互式体验（3分钟）

打开 Python 交互环境：

```bash
cd kangabase
PYTHONPATH=.. python3
```

然后逐行粘贴，感受每一步：

```python
# === 1. 初始化 ===
from kangabase import KangaBase
db = KangaBase("try_it.db")
db.load_schema("examples/coupon/schemas/coupon.yaml")
db.load_contract("examples/coupon/contracts/coupon_ops.yaml")
db.load_policy("examples/coupon/policies/permissions.yaml")
# 此时：SQLite 文件已创建，Schema 已建表，契约和权限已加载

# === 2. 创建两个 Agent（不同角色）===
boss = db.agent("老板Agent", role="asB")    # 企业侧
user = db.agent("用户Agent", role="asC")    # 消费者侧

# === 3. 老板：创建营销活动 ===
r = boss.execute("create_campaign", {"name": "周年庆", "budget": 1000.0})
camp_id = r.result["id"]
print(f"活动创建: {r.success}, ID: {camp_id[:8]}...")

# === 4. 老板：激活活动 ===
r = boss.execute("activate_campaign", {"campaign_id": camp_id})
print(f"活动激活: {r.success}")

# === 5. 老板：发券 ===
r = boss.execute("issue_coupon", {
    "user_id": "大仙", "amount": 50.0,
    "min_order": 100.0, "campaign_id": camp_id
})
coupon_id = r.result["id"]
print(f"发券成功: 面额50元, ID: {coupon_id[:8]}...")

# === 6. 权限隔离验证 ===
# 用户 Agent 试图发券（越权）
r = user.execute("issue_coupon", {
    "user_id": "大仙", "amount": 50.0,
    "min_order": 100.0, "campaign_id": camp_id
})
print(f"用户发券: {r.success}")  # → False
print(f"拒绝原因: {r.error}")    # → denied

# === 7. 用户：正常用券 ===
r = user.execute("use_coupon", {"coupon_id": coupon_id, "user_id": "大仙"})
print(f"用券: {r.success}")  # → True

# === 8. 重复用券防护 ===
r = user.execute("use_coupon", {"coupon_id": coupon_id, "user_id": "大仙"})
print(f"重复用券: {r.success}")  # → False（已用过）

# === 9. 预算验证 ===
r = boss.execute("issue_coupon", {
    "user_id": "土豪", "amount": 99999.0,
    "min_order": 100.0, "campaign_id": camp_id
})
print(f"超额发券: {r.success}")  # → False（预算不足）
print(f"原因: {r.error}")

# === 10. 审计日志 ===
logs = db.audit.query(limit=10)
for log in logs:
    print(f"  [{log['timestamp'][:19]}] {log['agent_id']}: {log['intent_name']} → {log['status']}")

# === 11. 统计 ===
stats = db.audit.get_statistics()
print(f"\n总操作: {stats['total']}")
print(f"按Agent: {stats['by_agent']}")
print(f"按操作: {stats['by_operation']}")
```

---

## 第三步：WebUI 可视化（2分钟）

```bash
# 新开终端
cd kangabase
PYTHONPATH=.. python3 cli/main.py serve \
  --db try_it.db \
  --schema examples/coupon/schemas/coupon.yaml \
  --contract examples/coupon/contracts/coupon_ops.yaml \
  --policy examples/coupon/policies/permissions.yaml
```

浏览器打开 `http://127.0.0.1:8000`，逐页看：

| 页面 | 看什么 |
|------|--------|
| **Dashboard** | 刚才操作的统计概览 |
| **Schemas** | 优惠券和活动的字段定义 |
| **Contracts** | 6个操作的前置条件、步骤、补偿策略 |
| **Explorer** | 表数据浏览 + 在页面上直接执行操作 |
| **Audit** | 刚才所有操作的完整审计链路 |
| **Agents** | 老板/用户两个角色的权限对比 |

---

## 体验核查清单

完成后对照检查，这些核心能力是否都感受到了：

- [ ] **YAML 声明式**：Schema/Contract/Policy 全是 YAML，人类可读
- [ ] **操作白名单**：Agent 只能执行预定义操作，不能随意 SQL
- [ ] **权限隔离**：asB 能发券，asC 不能；asC 能用券，asB 不能
- [ ] **业务约束**：预算不足自动拒绝，重复用券自动拒绝
- [ ] **全链路审计**：每个操作都有记录，谁/什么时候/做了什么/结果
- [ ] **零配置**：一个 .db 文件就是全部，没装任何数据库服务
- [ ] **WebUI**：不用写代码就能浏览和操作

---

## 体验后的思考题

1. 如果把"优惠券"换成你业务中的场景（比如工单、审批），定义 Schema 和 Contract 的体感如何？
2. 权限模型（asB/asC）是否贴合 Agentic Commerce 的 Agent 角色划分？
3. WebUI 的信息密度和交互是否合适？缺什么？多什么？

---

*清理：体验完后 `rm try_it.db` 即可，零残留。*
