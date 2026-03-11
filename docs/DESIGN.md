# KangaBase 设计理念 🦘

> *为什么世界需要一个 Agent-Native 的数据库？*

这份文档是 KangaBase 的灵魂。如果你想了解我们为什么做了这些设计决策、为什么不做另一些选择，请花 15 分钟读完它。

---

## 目录

- [1. 缘起：为什么需要一个新的数据库范式](#1-缘起)
- [2. 设计哲学](#2-设计哲学)
- [3. 核心设计决策](#3-核心设计决策)
- [4. 安全模型](#4-安全模型)
- [5. 扩展路径](#5-扩展路径)

---

## 1. 缘起

### 1.1 3A 范式下 Agent 对数据的新需求

2024年，**3A 范式**（Assistant × Autopilot × Avatar）的提出重新定义了企业级 AI Agent 的顶层设计：

- **Assistant**：辅助人类决策——Agent 需要读取数据、分析数据
- **Autopilot**：自主执行任务——Agent 需要写入数据、修改状态
- **Avatar**：代表用户行动——Agent 需要以特定身份操作数据

这三个层级对数据层提出了递进的要求：

| 层级 | 数据需求 | 传统方案能否满足 |
|---|---|---|
| Assistant | 只读查询 | ✅ 勉强可以（但缺乏语义理解） |
| Autopilot | 读写操作 | ⚠️ 危险（Agent 直接写 SQL？） |
| Avatar | 身份化操作 | ❌ 完全不支持 |

当 Agent 从"读数据"进化到"写数据"再到"代表某个身份操作数据"，传统的数据库交互方式就彻底不够用了。

### 1.2 Agentic Commerce 的挑战

商业模式正在从 toC/toB 演进到 **asC/asB**，最终走向 **A2A**（Agent-to-Agent）：

```
toC / toB  →  asC / asB  →  A2A
人操作系统    Agent代人操作   Agent之间直接交易
```

在 Agentic Commerce 中，一个 Agent 可能需要：

- 查询库存、下单购买、确认支付——**跨多个操作的事务**
- 代表用户操作但受权限约束——**身份和权限管理**
- 自主决策但可追溯——**完整的审计记录**
- 与其他 Agent 协作——**并发安全**

这些需求叠加在一起，现有的数据访问方案没有一个是为这个场景设计的。

### 1.3 现有方案的不足

**传统 RDBMS（MySQL / PostgreSQL）**
- ❌ 不理解 Agent 的"意图"，只看到 SQL 语句
- ❌ 权限模型面向人类用户，不面向 Agent 角色
- ❌ 没有操作契约的概念，Agent 可以执行任意 SQL
- ❌ 需要部署和运维数据库服务

**ORM（SQLAlchemy / Django ORM）**
- ❌ 为人类开发者设计，不是为 Agent 设计
- ❌ 没有操作白名单，Agent 可以调用任意 ORM 方法
- ❌ 缺少沙箱预执行和审计追踪
- ❌ 语义层薄弱，不携带同义词/指标等 Agent 需要的信息

**Text2SQL**
- ❌ 让 Agent 生成 SQL——等于给了 Agent 无限权力
- ❌ 生成的 SQL 可能错误、低效甚至危险（DROP TABLE）
- ❌ 难以约束输出范围，无法保证安全
- ❌ 每次都要 LLM 推理，成本高、延迟大

**文件系统（JSON / YAML 文件）**
- ❌ 无事务支持，并发下数据可能损坏
- ❌ 无查询能力，只能全量读取
- ❌ 无权限控制，文件权限粒度太粗
- ✅ 但适合配置层——这也是 KangaBase 用 YAML 做 Schema/Contract 的原因

**结论：我们需要一个专门为 Agent 设计的数据库范式。**

---

## 2. 设计哲学

### 2.1 "轻如 SQLite"

SQLite 是世界上部署最广泛的数据库——手机里有它、浏览器里有它、嵌入式设备里也有它。它成功的核心原因：**零配置、单文件、嵌入式**。

KangaBase 继承了这种哲学：

```python
import kangabase as kb
db = kb.open("shop.db")  # 就一行，数据库就好了
```

没有服务要启动，没有配置要改，没有端口要监听。`pip install` 之后就能用。

> 如果一个 Agent 需要先学会部署 PostgreSQL 才能存数据，那这个方案就已经失败了。

### 2.2 "易如 Supabase"

Supabase 让后端开发变得像"搭积木"——声明式的、SDK 友好的、开箱即用的。

KangaBase 追求同等的开发者体验：

- **YAML 声明式**：数据模型和操作契约都用 YAML 定义，人类可读、版本可控
- **SDK 友好**：Python SDK 设计直觉化，`agent.execute()` 或 `agent.ask()` 一行搞定
- **开箱即用**：内置权限、沙箱、审计，不需要自己搭配中间件

```yaml
# 看到这个 YAML，你就知道这个系统能做什么、不能做什么
contract: coupon_operations
operations:
  - name: issue_coupon
    risk_level: low
    params: [user_id, amount, campaign_id]
```

### 2.3 "为 Agent 而生"

这是 KangaBase 和其他所有数据库最本质的区别。我们不是给人类用的，我们是给 Agent 用的。

**意图路由**：Agent 表达"我想做什么"，KangaBase 理解并路由到正确的操作。不是 Agent 自己拼 SQL。

**操作白名单**：Contract 定义了所有合法操作，Agent 只能从中选择。这不是限制，是保护。

**安全沙箱**：操作先在内存中预执行，确认不会破坏数据后才真正落盘。

**身份追踪**：每个 Agent 有名称和角色，每次操作都记录是谁、什么时候、做了什么。

> 类比：传统数据库是开放式厨房，谁都能进来炒菜；KangaBase 是餐厅，有菜单、有服务员、有厨房隔离。

---

## 3. 核心设计决策

### 3.1 为什么选 YAML 不选 JSON / DSL

| | YAML | JSON | 自定义 DSL |
|---|---|---|---|
| 人类可读性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 注释支持 | ✅ | ❌ | 取决于实现 |
| 多行字符串 | ✅ 原生支持 | ❌ 需转义 | 取决于实现 |
| 生态系统 | 广泛（K8s, GitHub Actions） | 广泛 | 需要自建 |
| Agent 可理解 | ✅ 语义清晰 | ✅ 但噪音多 | ❌ 需要学习 |
| 版本控制友好 | ✅ diff 友好 | ⚠️ 尚可 | 取决于实现 |

YAML 的核心优势：**它看起来就像自然语言的结构化版本**。Agent 和人类都能轻松读懂。

```yaml
# 这段 YAML，即使不看文档也能理解
operation: issue_coupon
description: "发放优惠券给用户"
risk_level: low
params:
  - name: user_id
    type: text
    required: true
```

### 3.2 为什么操作契约而不是 Text2SQL

这是 KangaBase 最核心的设计决策。

**Text2SQL 的模式**：
```
Agent → (自然语言) → LLM → (SQL) → 数据库
```

问题：
1. **安全不可控**：LLM 可能生成 `DROP TABLE`、`DELETE *` 等危险 SQL
2. **结果不可预测**：同一个意图可能生成不同的 SQL，结果不一致
3. **成本高**：每次操作都要 LLM 推理
4. **调试困难**：出了问题，你不知道是 LLM 理解错了还是 SQL 写错了

**KangaBase 的模式**：
```
Agent → (意图+参数) → Intent Registry → (匹配) → Contract → (执行) → SQLite
```

优势：
1. **安全可控**：操作范围由 Contract 白名单限定，不可能越权
2. **结果确定**：同一个操作+参数=同样的结果，100% 可复现
3. **成本低**：意图匹配是规则引擎，不需要 LLM（自然语言调用时才需要 NL Parser）
4. **可调试**：每一步都有明确的日志——意图是什么、匹配到哪个操作、执行了什么

> **核心隐喻：从菜单点菜 vs 进厨房做菜。**
>
> 你去餐厅吃饭，不会自己跑进厨房炒菜。你看菜单、点菜、服务员送到厨房。
> 菜单就是 Contract，服务员就是 Intent Registry，厨房就是 SQLite。

### 3.3 为什么 Intent Registry 是架构枢纽

在 KangaBase 的架构中，Intent Registry 是连接一切的中心节点：

```
Schema ──→ Intent Registry ←── Contract
               ↕
           NL Parser
               ↕
         Agent SDK
               ↕
     Policy ──→ Sandbox ──→ Database
               ↕
            Audit
```

**为什么它是枢纽而不是某个模块的附属？**

1. **统一入口**：无论 Agent 是结构化调用还是自然语言调用，都经过 Intent Registry 路由
2. **解耦 Schema 和 Contract**：Schema 定义数据长什么样，Contract 定义能做什么，Intent Registry 把它们连起来
3. **可插拔**：NL Parser 可以替换（正则 → ML 模型 → LLM），但 Intent Registry 的接口不变
4. **审计友好**：所有操作都经过同一个点，天然适合记录审计日志

### 3.4 为什么 SQLite 不选 PostgreSQL

| 考量 | SQLite | PostgreSQL |
|---|---|---|
| 部署复杂度 | 零（文件即数据库） | 高（需要服务） |
| 适合嵌入 | ✅ 天然嵌入式 | ❌ C/S 架构 |
| 单 Agent 场景 | ⭐ 完美 | 杀鸡用牛刀 |
| 多 Agent 并发写 | ⚠️ 单写（WAL 模式可缓解） | ✅ 原生支持 |
| Agent 可携带 | ✅ 一个文件走天下 | ❌ 需要连接信息 |

KangaBase 的目标用户是 **Agent**，不是 DBA。Agent 需要的是"拎包入住"的体验，不是"先装修再入住"。

SQLite 完美契合这个需求。而对于需要高并发的场景，我们规划了 libSQL → Turso 的渐进升级路径（见第 5 节）。

### 3.5 文件系统 vs Agentic DB 的定位

一个常见的问题：既然 Schema 和 Contract 都是 YAML 文件，为什么运行时数据不也用文件？

**答案：配置层用文件，运行时用数据库。**

```
配置层（YAML 文件）          运行时（SQLite 数据库）
├── schemas/                 ├── 业务数据（优惠券、订单...）
│   └── coupon.yaml          ├── 审计日志
├── contracts/               └── Agent 会话状态
│   └── coupon_ops.yaml
└── policies/
    └── permissions.yaml
```

| | 文件系统 | 数据库 |
|---|---|---|
| 适合存储 | Schema、Contract、Policy（变更少、需要版本控制） | 业务数据（变更频繁、需要事务和查询） |
| 事务 | ❌ 无 | ✅ ACID |
| 并发 | ❌ 不安全 | ✅ 锁机制 |
| 查询 | ❌ 只能全量读 | ✅ SQL |
| 版本控制 | ✅ Git 友好 | ❌ 不适合 |

**类比**：菜单（Menu）印在纸上就好，不需要存数据库；但点单记录（Orders）必须存数据库，因为需要查询、统计、事务保护。

---

## 4. 安全模型

### 4.1 "Agent 只能从菜单点菜"

这是 KangaBase 安全模型的核心哲学。

传统数据库的安全模型基于**权限**——你能访问哪些表、哪些列。但这对 Agent 不够：

- Agent 能访问 `coupon` 表 ≠ Agent 应该能 `DELETE * FROM coupon`
- 列级权限太细，表级权限太粗，都不是 Agent 需要的粒度

KangaBase 的安全模型基于**操作白名单**：

```
Agent 能做什么 = Contract 中定义的操作集合
```

不在 Contract 中的操作，Agent 根本看不到、调不了、做不到。这不是"限制你不能做什么"，而是"只有这些能做"。

### 4.2 四层安全防线

```
Agent 发起操作
    │
    ▼
[Layer 1] Policy — 这个 Agent 有权执行这个操作吗？
    │                角色检查 → 参数约束检查 → 风险等级检查
    ▼
[Layer 2] Contract — 这个操作合法吗？
    │                  操作存在性 → 参数类型 → 前置条件
    ▼
[Layer 3] Sandbox — 预执行安全吗？
    │                内存沙箱 dry-run → 检查影响范围
    ▼
[Layer 4] Audit — 全链路记录
                   谁 → 什么时候 → 做了什么 → 结果如何
```

**Layer 1 - Policy（权限引擎）**

```yaml
policies:
  - role: asB
    allowed_operations: ["issue_coupon", "query_coupon"]
    max_risk_level: medium
    constraints:
      issue_coupon:
        amount: { max: 50 }  # asB 角色最多发50元券
  - role: admin
    allowed_operations: ["*"]
    max_risk_level: high
```

**Layer 2 - Contract（操作契约）**

每个操作有完整的前置条件和补偿逻辑：

```yaml
operations:
  - name: issue_coupon
    preconditions:
      - "user_id IS NOT NULL"
      - "amount > 0 AND amount <= 100"
    steps:
      - action: insert
        entity: coupon
        values: { user_id: "{{ user_id }}", amount: "{{ amount }}" }
    on_failure:
      compensate: "DELETE FROM coupon WHERE ..."
```

**Layer 3 - Sandbox（沙箱预执行）**

操作先在内存数据库中执行一遍。如果预执行失败或影响范围超出预期，真实操作不会执行。

```python
# 内部流程
sandbox_result = sandbox.dry_run(operation, params)
if sandbox_result.safe:
    real_result = database.execute(operation, params)
else:
    raise UnsafeOperationError(sandbox_result.reason)
```

**Layer 4 - Audit（审计追踪）**

每次操作自动记录：

```json
{
  "timestamp": "2026-03-11T10:00:00Z",
  "agent": "coupon_bot",
  "role": "asB",
  "operation": "issue_coupon",
  "params": {"user_id": "12345", "amount": 10},
  "result": "success",
  "affected_rows": 1,
  "sandbox_passed": true
}
```

---

## 5. 扩展路径

### SQLite → libSQL → Turso

KangaBase 选择 SQLite 作为起点，但不止步于 SQLite：

```
Phase 1: SQLite（当前）
├── 单文件、零配置
├── 适合单 Agent / 少量 Agent
└── 本地嵌入式

Phase 2: libSQL（计划中）
├── SQLite 的开源分支，完全兼容
├── 支持 HTTP 访问和更好的并发
└── 仍然可以单文件部署

Phase 3: Turso（远期）
├── 基于 libSQL 的云服务
├── 全球边缘部署、低延迟
├── Multi-Agent 分布式协作
└── 数据自动同步和备份
```

**关键设计：Storage Adapter 模式**

KangaBase 的存储层通过 `database.py` 中的 Storage Adapter 抽象。上层代码（Schema、Contract、Intent、Policy）完全不感知底层用的是 SQLite 还是 libSQL 还是 Turso。

```python
# 现在
db = kb.open("shop.db")                    # SQLite

# 未来
db = kb.open("libsql://localhost:8080")     # libSQL
db = kb.open("turso://my-db.turso.io")      # Turso
```

上层的 Schema、Contract、Agent SDK——一行代码都不用改。

---

## 后记

KangaBase 不是要取代 PostgreSQL 或 MySQL。它们在各自的领域无可替代。

KangaBase 要做的是：**在 Agent 时代，给数据操作一个新的范式。**

传统数据库为人类设计，KangaBase 为 Agent 设计。不是更好，是不同。

就像 SQLite 没有取代 Oracle，但它填补了"嵌入式数据库"这个空白；KangaBase 要填补的是"Agent-Native 数据库"这个空白。

给 Agent 一个安全的家 🦘

---

*[返回 README](../README.md) · [阅读使用指南](GUIDE.md)*
