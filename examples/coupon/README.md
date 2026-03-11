# KangaBase Coupon Demo

优惠券系统示例 - 展示 KangaBase 的核心功能

## 功能演示

1. **Schema 加载**: 从 YAML 定义创建 SQLite 表
2. **Contract 加载**: 加载操作契约定义
3. **Policy 配置**: 加载权限策略
4. **Agent 操作**: 通过 Agent SDK 执行业务操作
5. **审计日志**: 查看操作历史

## 快速开始

```bash
# 在项目根目录运行
bash quickstart.sh

# 或直接运行 demo
python examples/coupon/demo.py
```

## 文件说明

- `schemas/coupon.yaml` - 实体定义（Coupon、Campaign）
- `contracts/coupon_ops.yaml` - 操作契约（发券、用券、查询等）
- `policies/permissions.yaml` - 权限策略（enterprise_agent、consumer_agent）
- `demo.py` - 完整演示脚本

## 角色说明

| 角色 | 身份 | 允许操作 |
|------|------|----------|
| enterprise_agent | asB (企业方) | 创建活动、发券、查询、过期 |
| consumer_agent | asC (消费者) | 使用券、查询 |
| admin_agent | admin | 全部操作 |
