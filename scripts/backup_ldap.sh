#!/bin/bash

# 配置变量
BACKUP_DIR="/var/backups/ldap"          # 备份文件存储目录
BACKUP_FILE="ldap_backup_$(date +%Y%m%d_%H%M%S).ldif"  # 备份文件名
LDAP_HOST="localhost"                   # LDAP 服务器地址
LDAP_PORT="389"                         # LDAP 端口
LDAP_BASE_DN="dc=kyligence,dc=io"        # LDAP 基础 DN
LDAP_BIND_DN="cn=admin,dc=kyligence,dc=io" # LDAP 管理员 DN
LDAP_BIND_PASSWORD="Kyligence2020!"     # LDAP 管理员密码
OSS_BUCKET="ldap-prod-backup"           # OSS Bucket 名称
OSS_PATH="ldap_backups/"                # OSS 存储路径

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份 LDAP 数据
echo "Starting LDAP backup..."
#slapcat -v -l "${BACKUP_DIR}/${BACKUP_FILE}" -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "$LDAP_BIND_DN" -w "$LDAP_BIND_PASSWORD" -b "$LDAP_BASE_DN"
docker exec openldap slapcat -v -l /${BACKUP_FILE}
docker cp openldap:/${BACKUP_FILE} ${BACKUP_DIR}/
docker exec openldap rm -f /${BACKUP_FILE}

# 检查备份是否成功
if [ $? -eq 0 ]; then
    echo "LDAP backup completed successfully: ${BACKUP_DIR}/${BACKUP_FILE}"
else
    echo "LDAP backup failed!"
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



# 恢复数据时根据提示去掉第一条数据
# slapadd -l backup.ldif
