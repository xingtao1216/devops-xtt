#!/bin/bash


HOST=`hostname -i`
MEM=`free -g |grep -i mem |awk '{print$1,$2}'`
MEMINFO=`cat /proc/meminfo |grep MemTotal`
CPU=`lscpu |grep -w "CPU(s):"`
DISK=`lsblk |grep disk`
OS_VERSION=`cat /etc/redhat-release`

echo "............服务器ip 为 $HOST............."
echo "此服务器内存信息如下："
echo "$MEM"
echo "$MEMINFO"
echo "此服务器 cpu 信息如下："
echo "$CPU"
echo "此服务器磁盘信息如下："
echo "$DISK"
echo "此服务器OS 版本如下："
echo "$OS_VERSION"

echo "----------------------------------------"
