"""公共工具函数和资源解析器"""
import boto3
from datetime import datetime, timezone


def log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    icons = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERR": "❌", "WAIT": "⏳"}
    print(f"[{ts}] {icons.get(level, '')} [{level}] {msg}")


def paginate(method, key, **kwargs):
    items, token = [], None
    while True:
        resp = method(**kwargs, **({"NextToken": token} if token else {}))
        items.extend(resp.get(key, []))
        token = resp.get("NextToken")
        if not token:
            break
    return items


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


class ResourceResolver:
    """从指定区域解析资源及其依赖链"""

    def __init__(self, qs, account_id):
        self.qs = qs
        self.account_id = account_id
        self._datasources = None
        self._datasets = None
        self._analyses = None
        self._dashboards = None

    def datasources(self):
        if self._datasources is None:
            self._datasources = paginate(self.qs.list_data_sources, "DataSources", AwsAccountId=self.account_id)
        return self._datasources

    def datasets(self):
        if self._datasets is None:
            self._datasets = paginate(self.qs.list_data_sets, "DataSetSummaries", AwsAccountId=self.account_id)
        return self._datasets

    def analyses(self):
        if self._analyses is None:
            self._analyses = paginate(self.qs.list_analyses, "AnalysisSummaryList", AwsAccountId=self.account_id)
        return self._analyses

    def dashboards(self):
        if self._dashboards is None:
            self._dashboards = paginate(self.qs.list_dashboards, "DashboardSummaryList", AwsAccountId=self.account_id)
        return self._dashboards

    def _find(self, items, id_key, name_key, value):
        by_id = [i for i in items if i[id_key] == value]
        if by_id:
            return by_id
        by_name = [i for i in items if i[name_key] == value]
        if len(by_name) > 1:
            log("WARN", f"名称 '{value}' 匹配到 {len(by_name)} 个资源，请使用 ID:")
            for i in by_name:
                log("WARN", f"  {i[id_key]}  {i[name_key]}")
            return []
        return by_name

    def find_dashboards(self, v):
        return self._find(self.dashboards(), "DashboardId", "Name", v)

    def find_analyses(self, v):
        return self._find(self.analyses(), "AnalysisId", "Name", v)

    def find_datasets(self, v):
        return self._find(self.datasets(), "DataSetId", "Name", v)

    def find_datasources(self, v):
        return self._find(self.datasources(), "DataSourceId", "Name", v)

    def get_dataset_datasource_arns(self, dataset_id):
        arns = set()
        try:
            resp = self.qs.describe_data_set(AwsAccountId=self.account_id, DataSetId=dataset_id)
            for table in resp["DataSet"].get("PhysicalTableMap", {}).values():
                for src in table.values():
                    if "DataSourceArn" in src:
                        arns.add(src["DataSourceArn"])
        except Exception as e:
            log("WARN", f"获取 DataSet {dataset_id} 依赖失败: {e}")
        return arns

    def get_analysis_dataset_arns(self, analysis_id):
        arns = set()
        try:
            resp = self.qs.describe_analysis(AwsAccountId=self.account_id, AnalysisId=analysis_id)
            for arn in resp["Analysis"].get("DataSetArns", []):
                arns.add(arn)
        except Exception as e:
            log("WARN", f"获取 Analysis {analysis_id} 依赖失败: {e}")
        return arns

    def get_dashboard_dataset_arns(self, dashboard_id):
        arns = set()
        try:
            resp = self.qs.describe_dashboard(AwsAccountId=self.account_id, DashboardId=dashboard_id)
            for arn in resp["Dashboard"].get("Version", {}).get("DataSetArns", []):
                arns.add(arn)
        except Exception as e:
            log("WARN", f"获取 Dashboard {dashboard_id} 依赖失败: {e}")
        return arns

    def get_dashboard_analysis(self, dashboard_id):
        """获取 Dashboard 关联的 Analysis ARN"""
        try:
            resp = self.qs.describe_dashboard(AwsAccountId=self.account_id, DashboardId=dashboard_id)
            source_arn = resp["Dashboard"].get("Version", {}).get("SourceEntityArn", "")
            if ":analysis/" in source_arn:
                return source_arn
        except Exception as e:
            log("WARN", f"获取 Dashboard {dashboard_id} 关联 Analysis 失败: {e}")
        return None

    def resolve(self, resource_type, values):
        collected = {"datasources": {}, "datasets": {}, "analyses": {}, "dashboards": {}}

        def add_datasource(arn):
            collected["datasources"][arn.split("/")[-1]] = arn

        def add_dataset(arn):
            ds_id = arn.split("/")[-1]
            if ds_id in collected["datasets"]:
                return
            collected["datasets"][ds_id] = arn
            for a in self.get_dataset_datasource_arns(ds_id):
                add_datasource(a)

        def add_analysis(arn):
            an_id = arn.split("/")[-1]
            if an_id in collected["analyses"]:
                return
            collected["analyses"][an_id] = arn
            for a in self.get_analysis_dataset_arns(an_id):
                add_dataset(a)

        def add_dashboard(arn):
            db_id = arn.split("/")[-1]
            if db_id in collected["dashboards"]:
                return
            collected["dashboards"][db_id] = arn
            # analysis
            an_arn = self.get_dashboard_analysis(db_id)
            if an_arn:
                add_analysis(an_arn)
            # datasets (in case analysis missed some)
            for a in self.get_dashboard_dataset_arns(db_id):
                add_dataset(a)

        for val in values:
            finder = {
                "dashboard": (self.find_dashboards, add_dashboard, "DashboardId", "Arn"),
                "analysis": (self.find_analyses, add_analysis, "AnalysisId", "Arn"),
                "dataset": (self.find_datasets, add_dataset, "DataSetId", "Arn"),
                "datasource": (self.find_datasources, add_datasource, "DataSourceId", "Arn"),
            }[resource_type]
            find_fn, add_fn, id_key, arn_key = finder
            items = find_fn(val)
            for i in items:
                log("INFO", f"解析 {resource_type}: {i.get('Name', '')} ({i[id_key]})")
                add_fn(i[arn_key])
            if not items:
                log("ERR", f"未找到 {resource_type}: {val}")

        return collected
