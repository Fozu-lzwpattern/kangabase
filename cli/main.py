"""
CLI Module - 命令行工具

Commands:
- init: 初始化项目
- schema: Schema 管理
- contract: Contract 管理
- query: 查询数据
- execute: 执行操作
- audit: 审计查询
- serve: 启动服务
"""

from __future__ import annotations

import click
import sys
from pathlib import Path

# 添加父目录到路径，使 kangabase 包可导入
_cli_dir = Path(__file__).parent
_kangabase_dir = _cli_dir.parent
_workspace_dir = _kangabase_dir.parent
for p in [str(_kangabase_dir), str(_workspace_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from kangabase import KangaBase


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """KangaBase - 轻如 SQLite、易如 Supabase、为 Agent 而生"""
    pass


@cli.command()
@click.argument("project_dir", type=click.Path(), default=".")
def init(project_dir):
    """初始化 KangaBase 项目"""
    project_path = Path(project_dir)
    
    # 创建目录结构
    dirs = [
        "schemas",
        "contracts", 
        "policies",
        "data",
    ]
    
    for d in dirs:
        (project_path / d).mkdir(parents=True, exist_ok=True)
    
    # 创建示例文件
    # TODO: 生成示例 schema 和 contract
    
    click.echo(f"Initialized KangaBase project in {project_path}")


@cli.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option("--db", default="./data/kangabase.db", help="Database path")
def schema(schema_file, db):
    """加载和应用 Schema"""
    with KangaBase(db) as kb:
        kb.load_schema(schema_file)
        kb.schema_mgr.apply_all()
        
        # 显示创建的表
        tables = kb.db.list_tables()
        click.echo(f"Created tables: {', '.join(tables)}")


@cli.command()
@click.argument("contract_file", type=click.Path(exists=True))
@click.option("--db", default="./data/kangabase.db", help="Database path")
def contract(contract_file, db):
    """加载 Contract"""
    with KangaBase(db) as kb:
        kb.load_contract(contract_file)
        
        ops = kb.contract_exec.list_operations()
        click.echo(f"Loaded operations: {', '.join(ops)}")


@cli.command()
@click.argument("sql")
@click.option("--db", default="./data/kangabase.db", help="Database path")
def query(sql, db):
    """执行 SQL 查询"""
    with KangaBase(db) as kb:
        result = kb.db.execute(sql)
        
        if result.columns:
            # 打印表头
            click.echo(" | ".join(result.columns))
            click.echo("-" * 60)
            
            # 打印数据
            for row in result.rows:
                click.echo(" | ".join(str(v) for v in row))
        else:
            click.echo(f"Affected rows: {result.rowcount}")


@cli.command()
@click.argument("intent")
@click.option("--params", "-p", multiple=True, help="Parameters (key=value)")
@click.option("--agent", default="cli_agent", help="Agent ID")
@click.option("--role", default="admin", help="Agent role")
@click.option("--db", default="./data/kangabase.db", help="Database path")
@click.option("--sandbox", is_flag=True, help="Use sandbox")
def execute(intent, params, agent, role, db, sandbox):
    """执行意图操作"""
    # 解析参数
    param_dict = {}
    for p in params:
        if "=" in p:
            key, value = p.split("=", 1)
            # 尝试转换类型
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            param_dict[key] = value
    
    with KangaBase(db) as kb:
        # 加载示例数据
        schema_path = Path(__file__).parent.parent / "examples" / "coupon" / "schemas" / "coupon.yaml"
        contract_path = Path(__file__).parent.parent / "examples" / "coupon" / "contracts" / "coupon_ops.yaml"
        policy_path = Path(__file__).parent.parent / "examples" / "coupon" / "policies" / "permissions.yaml"
        
        if schema_path.exists():
            kb.load_schema(schema_path)
            kb.schema_mgr.apply_all()
        
        if contract_path.exists():
            kb.load_contract(contract_path)
        
        if policy_path.exists():
            kb.load_policy(policy_path)
        
        # 创建 Agent
        agent_instance = kb.agent(agent, role)
        
        # 执行
        result = agent_instance.execute(intent, param_dict, use_sandbox=sandbox)
        
        # 输出结果
        if result.success:
            click.echo(f"✓ Success ({result.execution_ms:.1f}ms)")
            click.echo(f"  Result: {result.result}")
        else:
            click.echo(f"✗ Failed: {result.error}")
            if result.risk_score > 0:
                click.echo(f"  Risk: {result.risk_score}")


@cli.command()
@click.option("--agent", "-a", help="Filter by agent")
@click.option("--intent", "-i", help="Filter by intent")
@click.option("--status", "-s", help="Filter by status")
@click.option("--limit", "-n", default=10, help="Limit results")
@click.option("--db", default="./data/kangabase.db", help="Database path")
def audit(agent, intent, status, limit, db):
    """查询审计日志"""
    with KangaBase(db) as kb:
        entries = kb.audit.query(
            agent_id=agent,
            intent_name=intent,
            status=status,
            limit=limit,
        )
        
        if not entries:
            click.echo("No audit entries found")
            return
        
        for entry in entries:
            click.echo(f"[{entry.timestamp}] {entry.agent_id}: {entry.intent_name} - {entry.status}")
            if entry.error_message:
                click.echo(f"  Error: {entry.error_message}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host")
@click.option("--port", default=8080, help="Port")
@click.option("--db", default="./data/kangabase.db", help="Database path")
@click.option("--schema", "schema_path", type=click.Path(exists=True), help="Schema YAML file")
@click.option("--contract", "contract_path", type=click.Path(exists=True), help="Contract YAML file")
@click.option("--policy", "policy_path", type=click.Path(exists=True), help="Policy YAML file")
@click.option("--reload", is_flag=True, help="Auto-reload on changes")
def serve(host, port, db, schema_path, contract_path, policy_path, reload):
    """启动 KangaBase WebUI"""
    import uvicorn

    # Import the web app factory
    from kangabase.web.app import create_app

    # Build kwargs for create_app
    kwargs = {
        "data_dir": db,
    }

    if schema_path:
        kwargs["schema_path"] = schema_path

    if contract_path:
        kwargs["contract_path"] = contract_path

    if policy_path:
        kwargs["policy_path"] = policy_path

    # Try to load default example files if they exist
    examples_dir = Path(__file__).parent.parent / "examples" / "coupon"
    if not schema_path:
        default_schema = examples_dir / "schemas" / "coupon.yaml"
        if default_schema.exists():
            kwargs["schema_path"] = str(default_schema)

    if not contract_path:
        default_contract = examples_dir / "contracts" / "coupon_ops.yaml"
        if default_contract.exists():
            kwargs["contract_path"] = str(default_contract)

    if not policy_path:
        default_policy = examples_dir / "policies" / "permissions.yaml"
        if default_policy.exists():
            kwargs["policy_path"] = str(default_policy)

    # Create app
    app = create_app(**kwargs)

    click.echo(f"Starting KangaBase WebUI on http://{host}:{port}")
    click.echo("Press Ctrl+C to stop")

    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def main():
    cli()


if __name__ == "__main__":
    main()
