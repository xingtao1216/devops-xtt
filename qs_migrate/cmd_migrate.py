"""migrate 子命令：跨区域迁移"""
import boto3
import csv
import json
import os
import time
import uuid
from datetime import datetime, timezone
from qs_common import log, paginate, chunk


class Migrator:
    def __init__(self, account_id, source_region, target_region, config, conflict_strategy):
        self.account_id = account_id
        self.source_region = source_region
        self.target_region = target_region
        self.config = config
        self.conflict_strategy = conflict_strategy
        self.src_qs = boto3.client("quicksight", region_name=source_region)
        self.dst_qs = boto3.client("quicksight", region_name=target_region)
        self.report = []

    def _report_add(self, rtype, rid, rname, status, detail=""):
        self.report.append({
            "resource_type": rtype, "resource_id": rid, "resource_name": rname,
            "status": status, "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def export_bundle(self, arns, job_id):
        log("INFO", f"启动导出 job: {job_id}, 资源数: {len(arns)}")
        self.src_qs.start_asset_bundle_export_job(
            AwsAccountId=self.account_id, AssetBundleExportJobId=job_id,
            ResourceArns=arns, ExportFormat="QUICKSIGHT_JSON",
            IncludeAllDependencies=True, IncludePermissions=True,
        )
        return self._wait_job(
            lambda: self.src_qs.describe_asset_bundle_export_job(
                AwsAccountId=self.account_id, AssetBundleExportJobId=job_id),
            "导出", job_id, url_key="DownloadUrl"
        )

    def _wait_job(self, describe_fn, label, job_id, url_key=None):
        while True:
            resp = describe_fn()
            status = resp["JobStatus"]
            log("WAIT", f"{label} {job_id}: {status}")
            if status == "SUCCESSFUL":
                return resp.get(url_key) if url_key else True
            if status in ("FAILED", "FAILED_ROLLBACK_COMPLETED", "FAILED_ROLLBACK_ERROR"):
                for e in resp.get("Errors", []):
                    log("ERR", f"  {e}")
                for e in resp.get("RollbackErrors", []):
                    log("ERR", f"  [rollback] {e}")
                return None if url_key else False
            time.sleep(10)

    def download_bundle(self, url, filepath):
        import urllib.request
        urllib.request.urlretrieve(url, filepath)
        log("OK", f"Bundle 已下载: {filepath}")

    def build_override(self):
        override = {}
        ds_creds = self.config.get("datasource_credentials", {})
        ds_params = self.config.get("datasource_parameters", {})
        vpc_map = self.config.get("vpc_connections", {})
        if ds_creds or ds_params:
            ds_map = {}
            for ds_id, cred in ds_creds.items():
                entry = ds_map.setdefault(ds_id, {"DataSourceId": ds_id})
                if cred.get("credential_type") == "CREDENTIAL_PAIR":
                    entry["Credentials"] = {"CredentialPair": {"Username": cred["username"], "Password": cred["password"]}}
            for ds_id, params in ds_params.items():
                entry = ds_map.setdefault(ds_id, {"DataSourceId": ds_id})
                entry["DataSourceParameters"] = params
            if ds_map:
                override["DataSources"] = list(ds_map.values())
        if vpc_map:
            override["VPCConnections"] = [{"VPCConnectionId": vid, **props} if isinstance(props, dict) else {"VPCConnectionId": props.rsplit("/", 1)[-1]} for vid, props in vpc_map.items()]
        return override or None

    def import_bundle(self, bundle_path, job_id, override):
        with open(bundle_path, "rb") as f:
            body = f.read()
        params = {
            "AwsAccountId": self.account_id, "AssetBundleImportJobId": job_id,
            "AssetBundleImportSource": {"Body": body}, "FailureAction": "ROLLBACK",
        }
        if override:
            params["OverrideParameters"] = override
        if self.conflict_strategy == "override":
            params["OverrideValidationStrategy"] = {"StrictModeForAllResources": False}
        log("INFO", f"启动导入 job: {job_id}")
        self.dst_qs.start_asset_bundle_import_job(**params)
        return self._wait_job(
            lambda: self.dst_qs.describe_asset_bundle_import_job(
                AwsAccountId=self.account_id, AssetBundleImportJobId=job_id),
            "导入", job_id
        )

    def apply_permissions(self, permissions):
        type_map = {
            "datasources": ("update_data_source_permissions", "DataSourceId"),
            "datasets": ("update_data_set_permissions", "DataSetId"),
            "analyses": ("update_analysis_permissions", "AnalysisId"),
            "dashboards": ("update_dashboard_permissions", "DashboardId"),
        }
        for coll_key, (method_name, id_key) in type_map.items():
            for res_id, perms in permissions.get(coll_key, {}).items():
                if not perms:
                    continue
                try:
                    getattr(self.dst_qs, method_name)(
                        AwsAccountId=self.account_id, **{id_key: res_id}, GrantPermissions=perms)
                    log("OK", f"权限已应用: {coll_key}/{res_id}")
                    self._report_add(coll_key, res_id, "", "PERMISSION_APPLIED")
                except Exception as e:
                    log("ERR", f"权限应用失败: {coll_key}/{res_id}: {e}")
                    self._report_add(coll_key, res_id, "", "PERMISSION_FAILED", str(e))

    def refresh_spice(self, dataset_ids):
        datasets = paginate(self.dst_qs.list_data_sets, "DataSetSummaries", AwsAccountId=self.account_id)
        spice_ids = {d["DataSetId"] for d in datasets if d.get("ImportMode") == "SPICE"}
        to_refresh = spice_ids & set(dataset_ids)
        if not to_refresh:
            log("INFO", "无 SPICE 数据集需要刷新")
            return
        log("INFO", f"需要刷新 {len(to_refresh)} 个 SPICE 数据集")
        ingestions = []
        for ds_id in to_refresh:
            ing_id = f"migrate-{uuid.uuid4().hex[:8]}"
            try:
                self.dst_qs.create_ingestion(AwsAccountId=self.account_id, DataSetId=ds_id, IngestionId=ing_id)
                log("OK", f"SPICE 刷新已触发: {ds_id}")
                ingestions.append((ds_id, ing_id))
                self._report_add("dataset", ds_id, "", "SPICE_REFRESH_TRIGGERED")
            except Exception as e:
                log("ERR", f"SPICE 刷新失败: {ds_id}: {e}")
                self._report_add("dataset", ds_id, "", "SPICE_REFRESH_FAILED", str(e))
        if ingestions:
            log("WAIT", "等待 30 秒后检查刷新状态...")
            time.sleep(30)
            for ds_id, ing_id in ingestions:
                try:
                    resp = self.dst_qs.describe_ingestion(AwsAccountId=self.account_id, DataSetId=ds_id, IngestionId=ing_id)
                    log("INFO", f"SPICE {ds_id}: {resp['Ingestion']['IngestionStatus']}")
                except Exception as e:
                    log("WARN", f"检查刷新状态失败: {ds_id}: {e}")

    def write_report(self, filepath):
        if not self.report:
            return
        fields = ["resource_type", "resource_id", "resource_name", "status", "detail", "timestamp"]
        with open(filepath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(self.report)
        log("OK", f"迁移报告已保存: {filepath}")

    def run(self, collected, permissions):
        work_dir = f"migrate_work_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(work_dir, exist_ok=True)

        all_arns = []
        for coll_key in ("datasources", "datasets", "analyses", "dashboards"):
            all_arns.extend(collected[coll_key].values())

        if not all_arns:
            log("ERR", "没有需要迁移的资源")
            return
        log("INFO", f"共 {len(all_arns)} 个资源待迁移")
        for arn in all_arns:
            log("INFO", f"  {arn}")

        # export
        batches = list(chunk(all_arns, 25))
        bundle_files = []
        for i, batch in enumerate(batches):
            job_id = f"migrate-export-{uuid.uuid4().hex[:8]}"
            url = self.export_bundle(batch, job_id)
            if url:
                fp = os.path.join(work_dir, f"bundle-{i+1}.qs.json")
                self.download_bundle(url, fp)
                bundle_files.append(fp)
                for arn in batch:
                    self._report_add("", arn.split("/")[-1], "", "EXPORTED")
            else:
                for arn in batch:
                    self._report_add("", arn.split("/")[-1], "", "EXPORT_FAILED")

        if not bundle_files:
            log("ERR", "所有导出均失败，终止")
            self.write_report(os.path.join(work_dir, "migration_report.csv"))
            return

        # import
        override = self.build_override()
        for bf in bundle_files:
            job_id = f"migrate-import-{uuid.uuid4().hex[:8]}"
            success = self.import_bundle(bf, job_id, override)
            self._report_add("bundle", os.path.basename(bf), "", "IMPORTED" if success else "IMPORT_FAILED")

        # permissions
        log("INFO", "开始应用权限...")
        self.apply_permissions(permissions)

        # spice
        log("INFO", "检查 SPICE 数据集...")
        self.refresh_spice(list(collected["datasets"].keys()))

        self.write_report(os.path.join(work_dir, "migration_report.csv"))
        log("OK", "迁移流程完成")


def collect_permissions(qs, account_id, collected):
    """收集源区域资源权限"""
    type_map = {
        "datasources": ("describe_data_source_permissions", "DataSourceId"),
        "datasets": ("describe_data_set_permissions", "DataSetId"),
        "analyses": ("describe_analysis_permissions", "AnalysisId"),
        "dashboards": ("describe_dashboard_permissions", "DashboardId"),
    }
    perms = {}
    for coll_key, (method_name, id_key) in type_map.items():
        perms[coll_key] = {}
        for res_id in collected[coll_key]:
            try:
                resp = getattr(qs, method_name)(AwsAccountId=account_id, **{id_key: res_id})
                p = resp.get("Permissions", [])
                if p:
                    perms[coll_key][res_id] = p
                    log("INFO", f"已获取权限: {coll_key}/{res_id} ({len(p)} 条)")
            except Exception as e:
                log("WARN", f"获取权限失败 {coll_key}/{res_id}: {e}")
    return perms
