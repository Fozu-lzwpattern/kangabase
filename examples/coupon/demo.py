"""
KangaBase Coupon Demo

演示 KangaBase 的核心功能：
1. Schema 加载和应用
2. Contract 加载
3. Policy 配置
4. Agent 执行操作
5. 审计日志
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from kangabase import KangaBase


def main():
    print("=" * 60)
    print("KangaBase Coupon Demo")
    print("=" * 60)
    
    # 路径设置
    base_dir = Path(__file__).parent
    db_path = base_dir / "data" / "coupon.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 初始化 KangaBase
    print("\n[1] 初始化 KangaBase...")
    kb = KangaBase(str(db_path))
    
    # 加载 Schema
    print("\n[2] 加载 Schema...")
    schema_path = base_dir / "schemas" / "coupon.yaml"
    kb.load_schema(schema_path)
    kb.schema_mgr.apply_all()
    
    tables = kb.db.list_tables()
    print(f"    创建的表: {tables}")
    
    # 加载 Contract
    print("\n[3] 加载 Contract...")
    contract_path = base_dir / "contracts" / "coupon_ops.yaml"
    kb.load_contract(contract_path)
    
    operations = kb.contract_exec.list_operations()
    print(f"    加载的操作: {operations}")
    
    # 加载 Policy
    print("\n[4] 加载 Policy...")
    policy_path = base_dir / "policies" / "permissions.yaml"
    kb.load_policy(policy_path)
    
    # 创建活动
    print("\n[5] 创建营销活动...")
    agent = kb.agent("enterprise_agent", role="asB")
    
    result = agent.execute("create_campaign", {
        "name": "春节大促",
        "budget": 10000.0,
    })
    
    if result.success:
        campaign_id = result.result.get("id")
        print(f"    ✓ 活动创建成功: {campaign_id}")
    else:
        print(f"    ✗ 失败: {result.error}")
        return
    
    # 激活活动
    print("\n[6] 激活活动...")
    result = agent.execute("activate_campaign", {
        "campaign_id": campaign_id,
    })
    
    if result.success:
        print(f"    ✓ 活动激活成功")
    else:
        print(f"    ✗ 失败: {result.error}")
    
    # 发放优惠券
    print("\n[7] 发放优惠券...")
    result = agent.execute("issue_coupon", {
        "user_id": "user_001",
        "amount": 10.0,
        "min_order": 50.0,
        "campaign_id": campaign_id,
    })
    
    if result.success:
        coupon_id = result.result.get("id")
        print(f"    ✓ 优惠券发放成功: {coupon_id}")
    else:
        print(f"    ✗ 失败: {result.error}")
    
    # 查询优惠券
    print("\n[8] 查询用户优惠券...")
    result = agent.execute("query_coupons", {
        "user_id": "user_001",
    })
    
    if result.success:
        print(f"    查询结果: {result.result}")
    
    # 模拟消费者使用券
    print("\n[9] 消费者使用券...")
    consumer = kb.agent("consumer_agent", role="asC")
    result = consumer.execute("use_coupon", {
        "coupon_id": coupon_id,
        "user_id": "user_001",
    })
    
    if result.success:
        print(f"    ✓ 券使用成功")
    else:
        print(f"    ✗ 失败: {result.error}")
    
    # 审计日志
    print("\n[10] 查看审计日志...")
    entries = kb.audit.query(limit=5)
    for entry in entries:
        print(f"    [{entry.timestamp}] {entry.agent_id}: {entry.intent_name} - {entry.status}")
    
    # 统计信息
    print("\n[11] 统计信息...")
    stats = kb.audit.get_statistics()
    print(f"    总操作数: {stats['total']}")
    print(f"    按状态: {stats['by_status']}")
    print(f"    按 Agent: {stats['by_agent']}")
    print(f"    按操作: {stats['by_operation']}")
    
    # 清理
    kb.close()
    
    print("\n" + "=" * 60)
    print("Demo 完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
