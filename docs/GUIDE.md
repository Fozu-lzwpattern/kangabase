# KangaBase 使用指南 🦘

> *从零开始，手把手带你用 KangaBase 构建 Agent-Native 数据系统*

---

## 目录

- [前言](#前言)
- [1. 安装](#1-安装)
- [2. 5 分钟快速上手](#2-5-分钟快速上手)
- [3. 核心概念详解](#3-核心概念详解)
- [4. CLI 使用指南](#4-cli-使用指南)
- [5. 实战案例：优惠券系统](#5-实战案例优惠券系统)
- [6. 高级主题](#6-高级主题)
- [7. FAQ](#7-faq)
- [8. 故障排查](#8-故障排查)

---

## 前言

### 这个项目解决什么问题？

当你的 AI Agent 需要操作数据（增删改查），你会怎么做？

- **让 Agent 直接写 SQL？** 太危险了——Agent 可能生成 `DROP TABLE`
- **套一层 ORM？** ORM 是为人类开发者设计的，Agent 不需要那些抽象
- **用 Text2SQL？** 每次都要 LLM 推理，慢、贵、不可控

KangaBase 提供了第四种选择：**定义好操作菜单，让 Agent 点菜。**

你用 YAML 定义数据模型（Schema）和合法操作（Contract），Agent 通过 SDK 调用这些操作。安全、可控、可审计。

### 给谁用？

- **Agent/AI 应用开发者**：需要让 Agent 安全地操作数据
- **Multi-Agent 系统架构师**：需要多 Agent 共享数据且权限隔离
- **快速原型开发者**：需要几分钟搭建一个可用的数据系统
- **对 Agent 安全敏感的团队**：需要完整的操作白名单和审计追踪

---

## 1. 安装

### 方式一：pip 安装（推荐）

```bash
pip install kangabase
```

### 方式二：从源码安装

```bash
git clone https://github.com/kangabase/kangabase.git
cd kangabase
pip install -e .
```

### 方式三：一键脚本

```bash
curl -sSL https://raw.githubusercontent.com/kangabase/kangabase/main/quickstart.sh | bash
```

### 系统要求

- Python 3.9+
- 无其他外部依赖（SQLite 是 Python 内建模块）

验证安装：

```bash
kangabase --version
# kangabase 0.3.0

python -c "import kangabase; print('✅ KangaBase 安装成功')"
```

---

## 2. 5 分钟快速上手

### 2.1 初始化项目

```bash
# 创建项目目录
mkdir my-agent-db && cd my-agent-db

# 初始化 KangaBase 项目结构
kangabase init
```

执行后你会得到：

```
my-agent-db/
├── schemas/           # 数据模型定义
│   └── example.yaml
├── contracts/         # 操作契约定义
│   └── example_ops.yaml
├── policies/          # 权限策略
│   └── default.yaml
└── kangabase.yaml     # 项目配置
```

### 2.2 定义第一个 Schema

编辑 `schemas/todo.yaml`：

```yaml
# schemas/todo.yaml
# 定义一个待办事项的数据模型

entity: todo
description: "待办事项"

fields:
  - name: id
    type: integer
    primary: true
    auto_increment: true
    description: "唯一标识"

  - name: title
    type: text
    required: true
    description: "待办标题"
    constraints:
      max_length: 200

  - name: done
    type: integer
    default: 0
    description: "是否完成（0=未完成，1=已完成）"
    constraints:
      enum: [0, 1]

  - name: created_at
    type: text
    default: "CURRENT_TIMESTAMP"
    description: "创建时间"

# 语义信息：帮助 Agent 理解这个实体
synonyms:
  待办: todo
  任务: todo
  to-do: todo
  task: todo

metrics:
  - name: total_todos
    description: "总待办数"
    sql: "SELECT COUNT(*) FROM todo"
  - name: done_rate
    description: "完成率"
    sql: "SELECT ROUND(100.0 * SUM(done) / COUNT(*), 1) FROM todo"
```

### 2.3 定义第一个 Contract

编辑 `contracts/todo_ops.yaml`：

```yaml
# contracts/todo_ops.yaml
# 定义 Agent 可以对 todo 执行的操作

contract: todo_operations
description: "待办事项的操作契约"

operations:
  - name: add_todo
    description: "添加新待办"
    risk_level: low
    params:
      - name: title
        type: text
        required: true
        description: "待办标题"
    steps:
      - action: insert
        entity: todo
        values:
          title: "{{ title }}"
          done: 0

  - name: complete_todo
    description: "完成待办"
    risk_level: low
    params:
      - name: id
        type: integer
        required: true
    preconditions:
      - "EXISTS (SELECT 1 FROM todo WHERE id = {{ id }} AND done = 0)"
    steps:
      - action: update
        entity: todo
        set:
          done: 1
        where: "id = {{ id }}"

  - name: list_todos
    description: "查询待办列表"
    risk_level: low
    params:
      - name: status
        type: text
        required: false
        description: "过滤条件：all/active/done"
        default: "all"
    steps:
      - action: query
        entity: todo
        conditions:
          all: "1=1"
          active: "done = 0"
          done: "done = 1"
        condition_key: "{{ status }}"

  - name: delete_todo
    description: "删除待办"
    risk_level: medium
    params:
      - name: id
        type: integer
        required: true
    preconditions:
      - "EXISTS (SELECT 1 FROM todo WHERE id = {{ id }})"
    steps:
      - action: delete
        entity: todo
        where: "id = {{ id }}"
    on_failure:
      compensate: null  # 删除操作无法补偿
```

### 2.4 创建 Agent 并执行

```python
# main.py
import kangabase as kb

# 第一步：打开数据库
db = kb.open("todo.db")

# 第二步：加载定义
db.load_schema("schemas/todo.yaml")
db.load_contract("contracts/todo_ops.yaml")

# 第三步：创建 Agent
agent = db.agent("todo_bot")

# 添加待办
agent.execute("add_todo", title="写 KangaBase 文档")
agent.execute("add_todo", title="跑一遍测试")
agent.execute("add_todo", title="提交 PR")

# 查看所有待办
todos = agent.execute("list_todos")
print(todos)
# [{'id': 1, 'title': '写 KangaBase 文档', 'done': 0, ...},
#  {'id': 2, 'title': '跑一遍测试', 'done': 0, ...},
#  {'id': 3, 'title': '提交 PR', 'done': 0, ...}]

# 完成一个
agent.execute("complete_todo", id=1)

# 用自然语言也行
agent.ask("帮我把'跑一遍测试'标记为完成")

# 查看统计
print(db.metric("done_rate"))
# 66.7
```

运行：

```bash
python main.py
```

🎉 **恭喜！你已经用 KangaBase 构建了第一个 Agent-Native 数据系统。**

---

## 3. 核心概念详解

### 3.1 Schema — 数据是什么

Schema 用 YAML 描述数据模型。它不只定义字段和类型，还携带**语义信息**。

```yaml
entity: coupon
description: "优惠券"

fields:
  - name: id
    type: integer
    primary: true
    auto_increment: true

  - name: user_id
    type: text
    required: true
    description: "持券用户ID"

  - name: amount
    type: real
    required: true
    description: "面额（元）"
    constraints:
      min: 0
      max: 100

  - name: status
    type: text
    default: "active"
    description: "状态"
    constraints:
      enum: ["active", "used", "expired"]

  - name: expire_at
    type: text
    description: "过期时间"

# 同义词：Agent 可能用不同的词指代同一个实体
synonyms:
  优惠券: coupon
  折扣券: coupon
  券: coupon
  coupon: coupon

# 指标：预定义的统计查询
metrics:
  - name: active_count
    description: "有效券数量"
    sql: "SELECT COUNT(*) FROM coupon WHERE status = 'active'"

  - name: total_amount
    description: "发放总金额"
    sql: "SELECT SUM(amount) FROM coupon"
```

**关键特性：**

| 特性 | 说明 |
|---|---|
| `fields` | 字段定义，支持 integer / text / real / blob 类型 |
| `constraints` | 字段约束：min, max, max_length, enum, pattern (正则) |
| `synonyms` | 同义词映射，帮助 NL Parser 理解不同表达 |
| `metrics` | 预定义指标，Agent 可以直接查询业务指标 |

加载 Schema 时，KangaBase 自动在 SQLite 中创建对应的表：

```python
db.load_schema("schemas/coupon.yaml")
# 自动执行: CREATE TABLE IF NOT EXISTS coupon (id INTEGER PRIMARY KEY AUTOINCREMENT, ...)
```

### 3.2 Contract — 能做什么

Contract 定义了 Agent 可以执行的所有操作。**不在 Contract 中的操作，不存在。**

```yaml
contract: coupon_operations
description: "优惠券操作契约"

operations:
  - name: issue_coupon
    description: "发放优惠券"
    risk_level: low
    params:
      - name: user_id
        type: text
        required: true
      - name: amount
        type: real
        required: true
        constraints: { min: 1, max: 100 }
      - name: campaign_id
        type: text
        required: false

    preconditions:
      - "{{ amount }} > 0"
      - "{{ amount }} <= 100"

    steps:
      - action: insert
        entity: coupon
        values:
          user_id: "{{ user_id }}"
          amount: "{{ amount }}"
          status: "active"

    on_failure:
      compensate: >
        DELETE FROM coupon
        WHERE user_id = '{{ user_id }}'
        AND rowid = last_insert_rowid()
      notify: ["admin"]
```

**操作定义的组成：**

| 字段 | 说明 |
|---|---|
| `name` | 操作名称（唯一标识） |
| `description` | 操作描述（供 Agent 和人类理解） |
| `risk_level` | 风险等级：low / medium / high / critical |
| `params` | 参数列表，包含类型和约束 |
| `preconditions` | 前置条件，执行前检查 |
| `steps` | 执行步骤，支持 insert / update / delete / query |
| `on_failure` | 失败处理：补偿操作、通知列表 |

**风险等级的含义：**

```
low      → 读操作、单条写入（发券、添加记录）
medium   → 批量修改、条件删除
high     → 涉及金额变更、状态不可逆转换
critical → 数据清除、表结构变更
```

Policy 中可以设置 Agent 的最大风险等级阈值。

### 3.3 Intent — 意图路由

Intent Registry 是连接 Agent 和 Contract 的桥梁。

**结构化调用**直接匹配：

```python
# Agent 明确说出操作名和参数
agent.execute("issue_coupon", user_id="12345", amount=10)
#               ↓
# Intent Registry: "issue_coupon" → 匹配 Contract 中的 issue_coupon 操作
```

**自然语言调用**经 NL Parser 解析后匹配：

```python
# Agent 用自然语言表达意图
agent.ask("给用户12345发一张10元优惠券")
#               ↓
# NL Parser: 提取意图="发放优惠券"，参数={user_id: "12345", amount: 10}
#               ↓
# Intent Registry: "发放优惠券" → 匹配 synonyms → 匹配 issue_coupon
```

**Intent Registry 的匹配优先级：**

1. 精确匹配操作名
2. 模式匹配（支持通配符）
3. 同义词匹配
4. NL 语义匹配（调用 NL Parser）

```python
# 注册自定义意图模式
db.register_intent(
    pattern="发*券*",
    operation="issue_coupon",
    param_mapping={"用户": "user_id", "金额": "amount"}
)
```

### 3.4 Policy — 权限策略

Policy 控制不同角色的 Agent 能做什么、不能做什么。

```yaml
# policies/permissions.yaml
policies:
  - role: asC
    description: "消费者侧 Agent"
    allowed_operations:
      - query_coupon
      - use_coupon
    max_risk_level: low
    constraints:
      query_coupon:
        user_id: "{{ agent.context.user_id }}"  # 只能查自己的券

  - role: asB
    description: "商家侧 Agent"
    allowed_operations:
      - issue_coupon
      - query_coupon
      - expire_coupon
    max_risk_level: medium
    constraints:
      issue_coupon:
        amount: { max: 50 }  # 最多发50元

  - role: admin
    description: "管理员"
    allowed_operations: ["*"]
    max_risk_level: critical
```

**权限检查流程：**

```python
agent = db.agent("coupon_bot", role="asB")

# ✅ 允许：asB 角色有 issue_coupon 权限
agent.execute("issue_coupon", user_id="123", amount=10)

# ❌ 拒绝：amount 超出 asB 的约束（max: 50）
agent.execute("issue_coupon", user_id="123", amount=100)
# PolicyError: Constraint violation: amount(100) exceeds max(50) for role 'asB'

# ❌ 拒绝：asB 角色没有 delete_all_coupons 权限
agent.execute("delete_all_coupons")
# PolicyError: Operation 'delete_all_coupons' not allowed for role 'asB'
```

### 3.5 Agent — 身份与调用

Agent 是操作数据的"人"。每个 Agent 有名称和角色。

```python
# 创建 Agent
agent = db.agent("coupon_bot", role="asB")

# 结构化调用：直接指定操作名和参数
result = agent.execute("issue_coupon",
    user_id="12345",
    amount=10,
    campaign_id="spring"
)

# 自然语言调用：用自然语言描述意图
result = agent.ask("给用户12345发一张10元优惠券")

# 查询指标
rate = agent.metric("active_count")

# 带上下文的 Agent（上下文会传递到 Policy 约束中）
agent = db.agent("user_agent", role="asC", context={"user_id": "12345"})
# 这个 Agent 只能查询 user_id="12345" 的数据
```

**执行结果：**

```python
result = agent.execute("issue_coupon", user_id="12345", amount=10)

print(result.success)        # True
print(result.operation)      # "issue_coupon"
print(result.affected_rows)  # 1
print(result.data)           # 查询操作时返回数据
print(result.audit_id)       # 审计记录ID
```

### 3.6 Sandbox — 沙箱预执行

每个写操作在真正执行前，先在内存沙箱中 dry-run。

```python
# 沙箱模式：只预执行，不真正写入
result = agent.execute("issue_coupon",
    user_id="12345",
    amount=10,
    dry_run=True
)

print(result.sandbox_passed)  # True — 沙箱验证通过
print(result.preview)         # 预览将要执行的操作
# Preview: INSERT INTO coupon (user_id, amount, status) VALUES ('12345', 10, 'active')
```

**沙箱检查项：**

1. SQL 语法是否正确
2. 前置条件是否满足
3. 约束是否违反（字段约束、Policy 约束）
4. 影响行数是否在预期范围内
5. 是否触发外键冲突或唯一约束冲突

**当沙箱检测到风险：**

```python
# 尝试删除所有数据（假设 Contract 中定义了 clear_all，风险等级 critical）
result = agent.execute("clear_all", dry_run=True)

print(result.sandbox_passed)  # False
print(result.warnings)
# ["⚠️ This operation will affect ALL rows (estimated: 15000)",
#  "⚠️ Risk level 'critical' exceeds agent's max risk 'medium'"]
```

### 3.7 Audit — 审计日志

每次操作自动记录审计日志，无需额外配置。

```python
# 查看审计日志
logs = db.audit.query(
    agent="coupon_bot",
    operation="issue_coupon",
    since="2026-03-01",
    limit=10
)

for log in logs:
    print(f"[{log.timestamp}] {log.agent} → {log.operation} → {log.result}")
# [2026-03-11 10:00:00] coupon_bot → issue_coupon → success
# [2026-03-11 10:01:00] coupon_bot → issue_coupon → success
# [2026-03-11 10:02:00] coupon_bot → issue_coupon → failed(PolicyError)

# 审计统计
stats = db.audit.stats()
print(stats)
# {
#   "total_operations": 1523,
#   "success_rate": 0.987,
#   "top_operations": [("issue_coupon", 800), ("query_coupon", 600)],
#   "top_agents": [("coupon_bot", 1200), ("admin_bot", 323)],
#   "risk_distribution": {"low": 1400, "medium": 100, "high": 23}
# }
```

### 3.8 Events — 事件订阅

KangaBase 内建事件系统，支持订阅操作事件。

```python
# 订阅事件
@db.on("after_execute")
def on_coupon_issued(event):
    if event.operation == "issue_coupon":
        print(f"🎫 新优惠券发放: 用户{event.params['user_id']}, 金额{event.params['amount']}")
        # 可以在这里触发通知、同步、统计等

@db.on("on_error")
def on_error(event):
    print(f"❌ 操作失败: {event.operation} - {event.error}")
    # 可以在这里发送告警

@db.on("before_execute")
def on_before(event):
    print(f"⏳ 即将执行: {event.operation}")
    # 可以在这里做额外验证，返回 False 可阻止执行
```

**支持的事件类型：**

| 事件 | 触发时机 |
|---|---|
| `before_execute` | 操作执行前（可阻止） |
| `after_execute` | 操作成功执行后 |
| `on_error` | 操作失败时 |
| `on_sandbox` | 沙箱预执行后 |
| `on_audit` | 审计日志写入后 |
| `on_policy_deny` | 权限拒绝时 |

---

## 4. CLI 使用指南

KangaBase 提供命令行工具，方便开发和调试。

### 初始化项目

```bash
kangabase init [project_name]
# 创建标准项目结构
```

### Schema 管理

```bash
# 验证 Schema 文件
kangabase schema validate schemas/coupon.yaml

# 查看 Schema 信息
kangabase schema show schemas/coupon.yaml

# 应用 Schema（创建/更新表结构）
kangabase schema apply schemas/coupon.yaml --db shop.db
```

### Contract 管理

```bash
# 验证 Contract 文件
kangabase contract validate contracts/coupon_ops.yaml

# 查看 Contract 中定义的操作列表
kangabase contract list contracts/coupon_ops.yaml

# 查看某个操作的详情
kangabase contract show contracts/coupon_ops.yaml --operation issue_coupon
```

### 查询数据

```bash
# 直接查询（需要有对应的查询操作在 Contract 中）
kangabase query --db shop.db --operation list_coupons --status active

# 查看指标
kangabase query --db shop.db --metric active_count
```

### 执行操作

```bash
# 执行操作
kangabase execute --db shop.db --operation issue_coupon \
  --param user_id=12345 \
  --param amount=10

# Dry-run 模式
kangabase execute --db shop.db --operation issue_coupon \
  --param user_id=12345 \
  --param amount=10 \
  --dry-run
```

### 审计查询

```bash
# 查看审计日志
kangabase audit --db shop.db --limit 20

# 按 Agent 过滤
kangabase audit --db shop.db --agent coupon_bot

# 查看统计
kangabase audit --db shop.db --stats
```

---

## 5. 实战案例：优惠券系统

让我们从零搭建一个完整的优惠券系统。

### 5.1 项目结构

```bash
kangabase init coupon-system && cd coupon-system
```

### 5.2 定义 Schema

```yaml
# schemas/coupon.yaml
entity: coupon
description: "优惠券"

fields:
  - name: id
    type: integer
    primary: true
    auto_increment: true
  - name: code
    type: text
    required: true
    unique: true
    description: "券码"
    constraints: { pattern: "^[A-Z0-9]{8}$" }
  - name: user_id
    type: text
    required: true
    description: "持券用户"
  - name: amount
    type: real
    required: true
    description: "面额（元）"
    constraints: { min: 1, max: 200 }
  - name: min_purchase
    type: real
    default: 0
    description: "最低消费门槛"
  - name: status
    type: text
    default: "active"
    constraints: { enum: ["active", "used", "expired", "revoked"] }
  - name: campaign_id
    type: text
    description: "活动ID"
  - name: issued_at
    type: text
    default: "CURRENT_TIMESTAMP"
  - name: used_at
    type: text
  - name: expire_at
    type: text
    required: true

synonyms:
  优惠券: coupon
  折扣券: coupon
  代金券: coupon

metrics:
  - name: active_count
    description: "有效券数量"
    sql: "SELECT COUNT(*) FROM coupon WHERE status = 'active'"
  - name: total_issued_amount
    description: "累计发放金额"
    sql: "SELECT COALESCE(SUM(amount), 0) FROM coupon"
  - name: usage_rate
    description: "使用率"
    sql: >
      SELECT ROUND(100.0 * COUNT(CASE WHEN status='used' THEN 1 END) / NULLIF(COUNT(*), 0), 1)
      FROM coupon
```

### 5.3 定义 Contract

```yaml
# contracts/coupon_ops.yaml
contract: coupon_operations
description: "优惠券完整操作契约"

operations:
  - name: issue_coupon
    description: "发放优惠券"
    risk_level: low
    params:
      - { name: user_id, type: text, required: true }
      - { name: amount, type: real, required: true, constraints: { min: 1, max: 200 } }
      - { name: min_purchase, type: real, required: false, default: 0 }
      - { name: campaign_id, type: text, required: false }
      - { name: expire_days, type: integer, required: false, default: 30 }
    steps:
      - action: insert
        entity: coupon
        values:
          code: "{{ generate_code(8) }}"
          user_id: "{{ user_id }}"
          amount: "{{ amount }}"
          min_purchase: "{{ min_purchase }}"
          campaign_id: "{{ campaign_id }}"
          expire_at: "{{ datetime_offset(expire_days, 'days') }}"
    on_failure:
      compensate: "DELETE FROM coupon WHERE code = '{{ result.code }}'"

  - name: use_coupon
    description: "使用优惠券"
    risk_level: medium
    params:
      - { name: code, type: text, required: true }
      - { name: order_amount, type: real, required: true }
    preconditions:
      - "EXISTS (SELECT 1 FROM coupon WHERE code = '{{ code }}' AND status = 'active')"
      - "{{ order_amount }} >= (SELECT min_purchase FROM coupon WHERE code = '{{ code }}')"
      - "(SELECT expire_at FROM coupon WHERE code = '{{ code }}') > datetime('now')"
    steps:
      - action: update
        entity: coupon
        set:
          status: "used"
          used_at: "CURRENT_TIMESTAMP"
        where: "code = '{{ code }}'"
    on_failure:
      compensate: "UPDATE coupon SET status = 'active', used_at = NULL WHERE code = '{{ code }}'"

  - name: query_user_coupons
    description: "查询用户的优惠券"
    risk_level: low
    params:
      - { name: user_id, type: text, required: true }
      - { name: status, type: text, required: false }
    steps:
      - action: query
        entity: coupon
        where: "user_id = '{{ user_id }}'"
        and_if:
          status: "status = '{{ status }}'"

  - name: expire_coupons
    description: "批量过期到期的优惠券"
    risk_level: medium
    params: []
    steps:
      - action: update
        entity: coupon
        set:
          status: "expired"
        where: "status = 'active' AND expire_at < datetime('now')"

  - name: revoke_coupon
    description: "撤销优惠券"
    risk_level: high
    params:
      - { name: code, type: text, required: true }
      - { name: reason, type: text, required: true }
    preconditions:
      - "EXISTS (SELECT 1 FROM coupon WHERE code = '{{ code }}' AND status = 'active')"
    steps:
      - action: update
        entity: coupon
        set:
          status: "revoked"
        where: "code = '{{ code }}'"
```

### 5.4 定义权限策略

```yaml
# policies/permissions.yaml
policies:
  - role: asC
    description: "消费者Agent —— 只能查看和使用自己的券"
    allowed_operations: [query_user_coupons, use_coupon]
    max_risk_level: medium
    constraints:
      query_user_coupons:
        user_id: "{{ agent.context.user_id }}"
      use_coupon:
        code: "must_belong_to({{ agent.context.user_id }})"

  - role: asB
    description: "商家Agent —— 可以发券、查券、过期"
    allowed_operations: [issue_coupon, query_user_coupons, expire_coupons]
    max_risk_level: medium
    constraints:
      issue_coupon:
        amount: { max: 50 }

  - role: admin
    description: "管理员 —— 全权限"
    allowed_operations: ["*"]
    max_risk_level: high
```

### 5.5 运行完整 Demo

```python
# demo.py
import kangabase as kb

# 初始化
db = kb.open("coupon_system.db")
db.load_schema("schemas/coupon.yaml")
db.load_contract("contracts/coupon_ops.yaml")
db.load_policy("policies/permissions.yaml")

# 注册事件
@db.on("after_execute")
def log_event(event):
    print(f"  📝 {event.agent} → {event.operation} → {event.result}")

# 商家 Agent 发券
print("=== 商家发券 ===")
merchant = db.agent("merchant_bot", role="asB")
merchant.execute("issue_coupon", user_id="user_001", amount=10, campaign_id="spring")
merchant.execute("issue_coupon", user_id="user_001", amount=20, campaign_id="spring")
merchant.execute("issue_coupon", user_id="user_002", amount=15, campaign_id="spring")

# 消费者 Agent 查券
print("\n=== 消费者查券 ===")
consumer = db.agent("consumer_bot", role="asC", context={"user_id": "user_001"})
my_coupons = consumer.execute("query_user_coupons", user_id="user_001")
print(f"  user_001 的优惠券: {len(my_coupons.data)} 张")
for c in my_coupons.data:
    print(f"    - {c['code']}: ¥{c['amount']} ({c['status']})")

# 消费者使用优惠券
print("\n=== 使用优惠券 ===")
code = my_coupons.data[0]['code']
consumer.execute("use_coupon", code=code, order_amount=50)

# 查看统计
print("\n=== 系统统计 ===")
print(f"  有效券数: {db.metric('active_count')}")
print(f"  累计发放: ¥{db.metric('total_issued_amount')}")
print(f"  使用率: {db.metric('usage_rate')}%")

# 查看审计
print("\n=== 审计日志 ===")
for log in db.audit.query(limit=5):
    print(f"  [{log.timestamp}] {log.agent}({log.role}) → {log.operation} → {log.result}")
```

运行：

```bash
python demo.py
```

输出示例：

```
=== 商家发券 ===
  📝 merchant_bot → issue_coupon → success
  📝 merchant_bot → issue_coupon → success
  📝 merchant_bot → issue_coupon → success

=== 消费者查券 ===
  user_001 的优惠券: 2 张
    - AB3F9K2X: ¥10.0 (active)
    - PQ7M4N8Y: ¥20.0 (active)

=== 使用优惠券 ===
  📝 consumer_bot → use_coupon → success

=== 系统统计 ===
  有效券数: 2
  累计发放: ¥45.0
  使用率: 33.3%

=== 审计日志 ===
  [2026-03-11 10:00:01] merchant_bot(asB) → issue_coupon → success
  [2026-03-11 10:00:02] merchant_bot(asB) → issue_coupon → success
  [2026-03-11 10:00:03] merchant_bot(asB) → issue_coupon → success
  [2026-03-11 10:00:04] consumer_bot(asC) → query_user_coupons → success
  [2026-03-11 10:00:05] consumer_bot(asC) → use_coupon → success
```

---

## 6. 高级主题

### 6.1 自定义事件处理

```python
# 发券超过一定金额时告警
@db.on("after_execute")
def high_amount_alert(event):
    if event.operation == "issue_coupon":
        amount = event.params.get("amount", 0)
        if amount > 30:
            print(f"⚠️ 高额发券告警: {event.agent} 发放了 ¥{amount} 优惠券")
            # 可接入实际告警系统
            # alert_service.send(...)

# 统计每分钟操作数
import time
operation_counter = {}

@db.on("after_execute")
def count_ops(event):
    minute = time.strftime("%Y-%m-%d %H:%M")
    key = f"{minute}:{event.operation}"
    operation_counter[key] = operation_counter.get(key, 0) + 1
```

### 6.2 Schema 迁移

当数据模型需要变更时：

```yaml
# schemas/coupon_v2.yaml
entity: coupon
version: 2  # 版本号

fields:
  # ... 原有字段 ...
  - name: category
    type: text
    description: "券类别"
    default: "general"
    migration: "ALTER TABLE coupon ADD COLUMN category TEXT DEFAULT 'general'"
```

```python
# 执行迁移
db.migrate_schema("schemas/coupon_v2.yaml")
# 自动检测版本差异，执行 migration 中定义的 SQL
```

### 6.3 性能调优

KangaBase 支持通过 PRAGMA 配置优化 SQLite 性能：

```python
db = kb.open("shop.db", pragmas={
    "journal_mode": "WAL",        # Write-Ahead Logging，提升并发读性能
    "synchronous": "NORMAL",       # 平衡安全性和速度
    "cache_size": -64000,          # 64MB 缓存
    "temp_store": "MEMORY",        # 临时表在内存中
    "mmap_size": 268435456,        # 256MB 内存映射
})
```

**常用 PRAGMA 推荐：**

| PRAGMA | 推荐值 | 说明 |
|---|---|---|
| `journal_mode` | WAL | 允许并发读，写不阻塞读 |
| `synchronous` | NORMAL | WAL 模式下安全且快速 |
| `cache_size` | -64000 | 64MB 页缓存（负数=KB） |
| `busy_timeout` | 5000 | 锁等待超时 5 秒 |
| `foreign_keys` | ON | 启用外键约束 |

---

## 7. FAQ

### Q: KangaBase 和 LangChain 的 SQL Agent 有什么区别？

**LangChain SQL Agent** 让 LLM 直接生成 SQL。灵活但不安全——LLM 可能生成任意 SQL。

**KangaBase** 预定义操作白名单，Agent 只能选择+填参数。安全但需要预先定义操作。

简单说：LangChain SQL Agent 是"自由发挥"，KangaBase 是"从菜单点菜"。

### Q: 可以同时用多个 Schema 和 Contract 吗？

当然可以。一个数据库可以加载多个 Schema（多个实体）和多个 Contract：

```python
db.load_schema("schemas/coupon.yaml")
db.load_schema("schemas/order.yaml")
db.load_schema("schemas/user.yaml")

db.load_contract("contracts/coupon_ops.yaml")
db.load_contract("contracts/order_ops.yaml")
```

### Q: NL Parser 用的什么模型？

内置的 NL Parser 使用规则引擎（正则匹配 + 关键词提取），不依赖外部 LLM，零延迟、零成本。

如果你需要更强的语义理解能力，可以插入自定义的 NL Parser：

```python
from kangabase.nl.parser import NLParser

class MyParser(NLParser):
    def parse(self, text):
        # 接入你自己的 LLM 或 NLU 服务
        ...

db.set_nl_parser(MyParser())
```

### Q: 支持关联查询（JOIN）吗？

当前版本通过 Contract 中的 `steps` 定义多步操作来实现类似效果。原生 JOIN 支持在 Roadmap 中。

### Q: 数据库文件可以复制给别人用吗？

可以。SQLite 数据库就是一个文件，复制即分享。Schema 和 Contract 也是文件。整个项目目录打包就是一个完整的 Agent 数据系统。

### Q: 生产环境可以用吗？

当前版本（v0.3）适合原型开发和中小规模应用。对于生产环境：
- 低并发场景（<100 TPS 写）：完全可以
- 高并发场景：等 libSQL/Turso 适配（Roadmap v0.5-v0.6）

---

## 8. 故障排查

### 常见问题

**问题：`ModuleNotFoundError: No module named 'kangabase'`**

```bash
# 确认安装
pip install kangabase

# 确认 Python 版本
python --version  # 需要 3.9+

# 如果用了虚拟环境，确认激活
source venv/bin/activate
```

**问题：`SchemaError: Invalid YAML syntax`**

```bash
# 验证 YAML 语法
kangabase schema validate schemas/your_schema.yaml

# 常见原因：
# 1. 缩进不一致（YAML 用空格不用 Tab）
# 2. 特殊字符未加引号
# 3. 冒号后没有空格
```

**问题：`PolicyError: Operation not allowed`**

```python
# 检查 Agent 的角色
print(agent.role)  # 看看是什么角色

# 检查该角色的权限
print(db.policy.get_permissions(agent.role))

# 检查操作的风险等级是否超过角色阈值
print(db.contract.get_operation("your_op").risk_level)
```

**问题：`SandboxError: Precondition failed`**

```python
# 沙箱预执行失败，说明前置条件不满足
# 用 dry_run 查看详情
result = agent.execute("your_op", dry_run=True, **params)
print(result.errors)  # 查看具体哪个前置条件失败
```

**问题：`DatabaseError: database is locked`**

```python
# SQLite 写锁冲突，设置超时
db = kb.open("shop.db", pragmas={"busy_timeout": 5000})

# 或使用 WAL 模式减少锁冲突
db = kb.open("shop.db", pragmas={"journal_mode": "WAL"})
```

### 调试模式

```python
import kangabase as kb
import logging

# 开启详细日志
logging.basicConfig(level=logging.DEBUG)
kb.set_log_level("DEBUG")

# 或者只看特定模块
logging.getLogger("kangabase.core.intent").setLevel(logging.DEBUG)
logging.getLogger("kangabase.core.sandbox").setLevel(logging.DEBUG)
```

### 获取帮助

- 📖 [设计理念](DESIGN.md) — 理解为什么这样设计
- 🐛 [GitHub Issues](https://github.com/kangabase/kangabase/issues) — 报告问题
- 💬 [Discussions](https://github.com/kangabase/kangabase/discussions) — 提问和讨论

---

<div align="center">

**🦘 KangaBase — 给 Agent 一个安全的家**

*[返回 README](../README.md) · [设计理念](DESIGN.md)*

</div>
