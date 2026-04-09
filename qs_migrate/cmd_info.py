"""info 子命令：查询资源详细信息及依赖链"""
from qs_common import log, ResourceResolver


def _ds_name_map(resolver):
    """DataSourceId -> Name"""
    return {d["DataSourceId"]: d["Name"] for d in resolver.datasources()}


def _dset_name_map(resolver):
    return {d["DataSetId"]: d["Name"] for d in resolver.datasets()}


def _analysis_name_map(resolver):
    return {d["AnalysisId"]: d["Name"] for d in resolver.analyses()}


def show_info(qs, account_id, resource_type, values):
    resolver = ResourceResolver(qs, account_id)
    ds_names = _ds_name_map(resolver)
    dset_names = _dset_name_map(resolver)
    an_names = _analysis_name_map(resolver)

    for val in values:
        print(f"\n{'='*60}")
        if resource_type == "dashboard":
            _show_dashboard(resolver, qs, account_id, val, ds_names, dset_names, an_names)
        elif resource_type == "analysis":
            _show_analysis(resolver, qs, account_id, val, ds_names, dset_names)
        elif resource_type == "dataset":
            _show_dataset(resolver, qs, account_id, val, ds_names)
        elif resource_type == "datasource":
            _show_datasource(resolver, qs, account_id, val)


def _show_dashboard(resolver, qs, account_id, val, ds_names, dset_names, an_names):
    items = resolver.find_dashboards(val)
    if not items:
        log("ERR", f"未找到 Dashboard: {val}")
        return
    for db in items:
        db_id = db["DashboardId"]
        print(f"📊 Dashboard: {db['Name']}")
        print(f"   ID:  {db_id}")
        print(f"   ARN: {db['Arn']}")

        # Analysis
        an_arn = resolver.get_dashboard_analysis(db_id)
        if an_arn:
            an_id = an_arn.split("/")[-1]
            print(f"\n   📈 关联 Analysis:")
            print(f"      {an_names.get(an_id, '(未知)')} ({an_id})")
        else:
            print(f"\n   📈 关联 Analysis: 无")

        # DataSets
        ds_arns = resolver.get_dashboard_dataset_arns(db_id)
        if ds_arns:
            print(f"\n   📦 关联 DataSet ({len(ds_arns)}):")
            for arn in sorted(ds_arns):
                did = arn.split("/")[-1]
                print(f"      {dset_names.get(did, '(未知)')} ({did})")
                # DataSource for each dataset
                src_arns = resolver.get_dataset_datasource_arns(did)
                for sa in sorted(src_arns):
                    sid = sa.split("/")[-1]
                    print(f"        └─ DataSource: {ds_names.get(sid, '(未知)')} ({sid})")
        else:
            print(f"\n   📦 关联 DataSet: 无")


def _show_analysis(resolver, qs, account_id, val, ds_names, dset_names):
    items = resolver.find_analyses(val)
    if not items:
        log("ERR", f"未找到 Analysis: {val}")
        return
    for an in items:
        an_id = an["AnalysisId"]
        print(f"📈 Analysis: {an['Name']}")
        print(f"   ID:  {an_id}")
        print(f"   ARN: {an['Arn']}")

        ds_arns = resolver.get_analysis_dataset_arns(an_id)
        if ds_arns:
            print(f"\n   📦 关联 DataSet ({len(ds_arns)}):")
            for arn in sorted(ds_arns):
                did = arn.split("/")[-1]
                print(f"      {dset_names.get(did, '(未知)')} ({did})")
                src_arns = resolver.get_dataset_datasource_arns(did)
                for sa in sorted(src_arns):
                    sid = sa.split("/")[-1]
                    print(f"        └─ DataSource: {ds_names.get(sid, '(未知)')} ({sid})")
        else:
            print(f"\n   📦 关联 DataSet: 无")


def _show_dataset(resolver, qs, account_id, val, ds_names):
    items = resolver.find_datasets(val)
    if not items:
        log("ERR", f"未找到 DataSet: {val}")
        return
    for ds in items:
        ds_id = ds["DataSetId"]
        print(f"📦 DataSet: {ds['Name']}")
        print(f"   ID:  {ds_id}")
        print(f"   ARN: {ds['Arn']}")
        print(f"   ImportMode: {ds.get('ImportMode', '未知')}")

        src_arns = resolver.get_dataset_datasource_arns(ds_id)
        if src_arns:
            print(f"\n   🔌 关联 DataSource ({len(src_arns)}):")
            for sa in sorted(src_arns):
                sid = sa.split("/")[-1]
                print(f"      {ds_names.get(sid, '(未知)')} ({sid})")
        else:
            print(f"\n   🔌 关联 DataSource: 无")


def _show_datasource(resolver, qs, account_id, val):
    items = resolver.find_datasources(val)
    if not items:
        log("ERR", f"未找到 DataSource: {val}")
        return
    for ds in items:
        print(f"🔌 DataSource: {ds['Name']}")
        print(f"   ID:   {ds['DataSourceId']}")
        print(f"   ARN:  {ds['Arn']}")
        print(f"   Type: {ds.get('Type', '未知')}")
