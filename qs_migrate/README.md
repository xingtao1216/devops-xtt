# QuickSight 跨区域迁移工具

同账号跨区域迁移，源区域和目标区域可配置。

## 使用前准备

1. 安装依赖:
   ```bash
   pip install boto3 openpyxl
   ```
2. 配置 AWS 凭证，确保有 QuickSight 管理员权限
3. 如有数据源凭证或 VPC 映射，准备 JSON 配置文件（参考 `config_example.json`）

## 子命令一览

| 子命令 | 功能 |
|---|---|
| `migrate` | 跨区域迁移资源（含权限、依赖、SPICE 刷新） |
| `info` | 查询资源详细信息及依赖链 |
| `deps` | 导出资源依赖关系到 Excel |

---

## migrate — 跨区域迁移

### 命令格式

```bash
python qs_migrate.py migrate \
  --account-id <AWS账号ID> \
  --source-region <源区域> \
  --target-region <目标区域> \
  --resource-type <资源类型> \
  --resources <资源ID或名称...> \
  [--config <配置文件路径>] \
  [--conflict-strategy override|skip|fail]
```

### 依赖打包规则

| 选择的资源类型 | 自动打包范围 |
|---|---|
| Dashboard | Dashboard + Analysis + DataSet + DataSource |
| Analysis | Analysis + DataSet + DataSource |
| DataSet | DataSet + DataSource |
| DataSource | 仅 DataSource |

### 示例

```bash
# 迁移 Dashboard（自动打包全链路依赖）
python qs_migrate.py migrate \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --source-region SOURCE_REGION \
  --target-region TARGET_REGION \
  --resource-type dashboard \
  --resources "dashboard-id-1" "dashboard-id-2"

# 迁移 Analysis（含 DataSet + DataSource）
python qs_migrate.py migrate \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --source-region SOURCE_REGION \
  --target-region TARGET_REGION \
  --resource-type analysis \
  --resources "analysis-id"

# 按名称迁移 DataSet（含 DataSource）
python qs_migrate.py migrate \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --source-region SOURCE_REGION \
  --target-region TARGET_REGION \
  --resource-type dataset \
  --resources "your_dataset_name"

# 带配置文件迁移 DataSource
python qs_migrate.py migrate \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --source-region SOURCE_REGION \
  --target-region TARGET_REGION \
  --resource-type datasource \
  --resources "datasource-id" \
  --config config_example.json
```

### 输出

- 运行日志：实时打印到终端，包含时间戳和状态图标
- 迁移报告：CSV 格式，保存在 `migrate_work_<timestamp>/migration_report.csv`
- 导出 Bundle：保存在 `migrate_work_<timestamp>/` 目录下

---

## info — 查询资源信息

查询指定资源的详细信息及完整依赖链。支持批量查询。

### 命令格式

```bash
python qs_migrate.py info \
  --account-id <AWS账号ID> \
  --region <区域> \
  --resource-type <资源类型> \
  --resources <资源ID或名称...>
```

### 示例

```bash
# 查询 Dashboard 信息（含关联的 Analysis、DataSet、DataSource）
python qs_migrate.py info \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --region SOURCE_REGION \
  --resource-type dashboard \
  --resources "dashboard-id"

# 批量查询多个 DataSet
python qs_migrate.py info \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --region SOURCE_REGION \
  --resource-type dataset \
  --resources "dataset-id-1" "dataset-id-2"

# 查询 DataSource 信息
python qs_migrate.py info \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --region SOURCE_REGION \
  --resource-type datasource \
  --resources "datasource-id"
```

### 输出示例

```
============================================================
📊 Dashboard: Sample Dashboard Name
   ID:  dashboard-id
   ARN: arn:aws:quicksight:SOURCE_REGION:YOUR_AWS_ACCOUNT_ID:dashboard/dashboard-id...

   📈 关联 Analysis:
      Sample Analysis Name (analysis-id...)

   📦 关联 DataSet (1):
      sample_dataset_name (dataset-id...)
        └─ DataSource: sample_datasource_name (datasource-id...)
```

如果某个依赖不存在，会显示"无"。

---

## deps — 导出依赖关系

导出资源依赖关系到 Excel 文件（.xlsx），包含三个 Sheet：
- Dashboard Dependencies
- Analysis Dependencies
- DataSet Dependencies

### 命令格式

```bash
# 导出全量依赖关系（不指定 --resource-type 和 --resources）
python qs_migrate.py deps \
  --account-id <AWS账号ID> \
  --region <区域> \
  [--output dependencies.xlsx]

# 导出指定资源的依赖关系
python qs_migrate.py deps \
  --account-id <AWS账号ID> \
  --region <区域> \
  --resource-type <资源类型> \
  --resources <资源ID或名称...> \
  [--output my_deps.xlsx]
```

### 示例

```bash
# 导出整个区域的全量依赖关系
python qs_migrate.py deps \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --region SOURCE_REGION \
  --output all_dependencies.xlsx

# 仅导出指定 Dashboard 的依赖关系
python qs_migrate.py deps \
  --account-id YOUR_AWS_ACCOUNT_ID \
  --region SOURCE_REGION \
  --resource-type dashboard \
  --resources "dashboard-id" \
  --output dashboard_deps.xlsx
```

---

## 配置文件格式

参考 `config_example.json`：

```json
{
  "datasource_credentials": {
    "<DataSourceId>": {
      "credential_type": "CREDENTIAL_PAIR",
      "username": "<用户名>",
      "password": "<密码>"
    }
  },
  "vpc_connections": {
    "<源VPC连接ID>": "<目标VPC连接ARN>"
  }
}
```

## 参数说明

| 参数 | 适用子命令 | 说明 |
|---|---|---|
| `--account-id` | 全部 | AWS 账号 ID |
| `--source-region` | migrate | 源区域 |
| `--target-region` | migrate | 目标区域 |
| `--region` | info, deps | 查询区域 |
| `--resource-type` | 全部 | `dashboard` / `analysis` / `dataset` / `datasource` |
| `--resources` | migrate, info, deps(可选) | 资源 ID 或名称，空格分隔 |
| `--config` | migrate | JSON 配置文件路径 |
| `--conflict-strategy` | migrate | `override`(默认) / `skip` / `fail` |
| `--output` | deps | Excel 输出路径（默认 `dependencies.xlsx`） |

## 注意事项

- 资源名称有重复时，工具会提示并要求使用 ID 指定
- SPICE 数据集迁移后会自动触发刷新，DIRECT_QUERY 模式无需刷新
- 冲突策略建议使用默认的 `override`，适合重复执行和失败重试场景
- deps 子命令需要 `openpyxl` 库：`pip install openpyxl`

## 目录结构

```
script/
├── qs_migrate.py       # 主入口（子命令路由）
├── qs_common.py        # 公共模块（日志、分页、ResourceResolver）
├── cmd_migrate.py      # migrate 子命令
├── cmd_info.py         # info 子命令
├── cmd_deps.py         # deps 子命令
├── config_example.json # 配置文件示例
└── README.md
```
