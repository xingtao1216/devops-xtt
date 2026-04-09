#!/usr/bin/env python3
"""
QuickSight 跨区域迁移工具（同账号）

子命令:
  migrate  - 跨区域迁移资源
  info     - 查询资源详细信息及依赖链
  deps     - 导出资源依赖关系到 Excel
"""
import argparse
import json
import sys
import boto3
from qs_common import log, ResourceResolver


def add_common_args(p):
    p.add_argument("--account-id", required=True, help="AWS 账号 ID")
    p.add_argument("--region", required=True, help="区域，如 us-west-2")


def add_resource_args(p):
    p.add_argument("--resource-type", required=True,
                    choices=["dashboard", "analysis", "dataset", "datasource"],
                    help="资源类型")
    p.add_argument("--resources", required=True, nargs="+",
                    help="资源 ID 或名称（支持多个，空格分隔）")


def main():
    parser = argparse.ArgumentParser(description="QuickSight 跨区域迁移工具",
                                     formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", help="子命令")

    # ---- migrate ----
    p_migrate = sub.add_parser("migrate", help="跨区域迁移资源")
    p_migrate.add_argument("--account-id", required=True, help="AWS 账号 ID")
    p_migrate.add_argument("--source-region", required=True, help="源区域")
    p_migrate.add_argument("--target-region", required=True, help="目标区域")
    add_resource_args(p_migrate)
    p_migrate.add_argument("--config", default=None, help="JSON 配置文件路径")
    p_migrate.add_argument("--conflict-strategy", default="override",
                           choices=["override", "skip", "fail"], help="冲突策略（默认 override）")

    # ---- info ----
    p_info = sub.add_parser("info", help="查询资源详细信息及依赖链")
    add_common_args(p_info)
    add_resource_args(p_info)

    # ---- deps ----
    p_deps = sub.add_parser("deps", help="导出资源依赖关系到 Excel")
    add_common_args(p_deps)
    p_deps.add_argument("--resource-type", default=None,
                        choices=["dashboard", "analysis", "dataset", "datasource"],
                        help="资源类型（不指定则导出全量）")
    p_deps.add_argument("--resources", default=None, nargs="+",
                        help="资源 ID 或名称（不指定则导出全量）")
    p_deps.add_argument("--output", default="dependencies.xlsx", help="输出文件路径（默认 dependencies.xlsx）")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "migrate":
        config = {}
        if args.config:
            with open(args.config) as f:
                config = json.load(f)
            log("OK", f"已加载配置: {args.config}")

        log("INFO", f"迁移方向: {args.source_region} → {args.target_region}")
        src_qs = boto3.client("quicksight", region_name=args.source_region)
        resolver = ResourceResolver(src_qs, args.account_id)
        collected = resolver.resolve(args.resource_type, args.resources)

        total = sum(len(v) for v in collected.values())
        log("INFO", f"解析完成，共 {total} 个资源（含依赖）:")
        for k, v in collected.items():
            if v:
                log("INFO", f"  {k}: {len(v)}")
        if total == 0:
            log("ERR", "未解析到任何资源，退出")
            sys.exit(1)

        log("INFO", "收集源区域资源权限...")
        from cmd_migrate import collect_permissions, Migrator
        permissions = collect_permissions(src_qs, args.account_id, collected)

        migrator = Migrator(args.account_id, args.source_region, args.target_region,
                            config, args.conflict_strategy)
        migrator.run(collected, permissions)

    elif args.command == "info":
        from cmd_info import show_info
        qs = boto3.client("quicksight", region_name=args.region)
        show_info(qs, args.account_id, args.resource_type, args.resources)

    elif args.command == "deps":
        from cmd_deps import export_deps
        qs = boto3.client("quicksight", region_name=args.region)
        export_deps(qs, args.account_id, args.resource_type, args.resources, args.output)


if __name__ == "__main__":
    main()
