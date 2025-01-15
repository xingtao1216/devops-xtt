#!/bin/bash

# 配置变量
BACKUP_DIR="/var/backups/mysql"          # 备份文件存储目录
BACKUP_FILE="mysql_backup_$(date +%Y%m%d_%H%M%S).sql"  # 备份文件名
MYSQL_USER="root"                       # MySQL 用户名
MYSQL_PASSWORD="your_password"          # MySQL 密码
MYSQL_DATABASE="your_database"          # 需要备份的数据库名称
OSS_BUCKET="mysql-prod-backup"          # OSS Bucket 名称
OSS_PATH="mysql_backups/"               # OSS 存储路径

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份 MySQL 数据
echo "Starting MySQL backup..."
mysqldump -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" > "${BACKUP_DIR}/${BACKUP_FILE}"

# 检查备份是否成功
if [ $? -eq 0 ]; then
    echo "MySQL backup completed successfully: ${BACKUP_DIR}/${BACKUP_FILE}"
else
    echo "MySQL backup failed!"
    exit 1
fi

# 上传备份文件到 OSS
echo "Uploading backup to OSS..."
ossutil cp "${BACKUP_DIR}/${BACKUP_FILE}" "oss://${OSS_BUCKET}/${OSS_PATH}${BACKUP_FILE}"

# 检查上传是否成功
if [ $? -eq 0 ]; then
    echo "Backup uploaded to OSS successfully: oss://${OSS_BUCKET}/${OSS_PATH}${BACKUP_FILE}"
else
    echo "OSS upload failed!"
    exit 1
fi

# 清理本地备份文件（可选）
echo "Cleaning up local backup files..."
rm -f "${BACKUP_DIR}/${BACKUP_FILE}"

echo "Backup process completed!"
