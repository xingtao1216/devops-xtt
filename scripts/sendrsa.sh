#!/bin/bash

while read line
  do
    user="root"
    ip=`echo $line | cut -d " " -f 1`
    passwd="DevOps@2024#!@"
    expect <<EOF
      set timeout 10
      spawn ssh-copy-id -i /root/.ssh/id_rsa.pub $user@$ip
      expect {
        "yes/no" { send "yes\n";exp_continue }
        "password" { send "$passwd\n" }
      }
      expect "password" { send "$passwd\n" }
EOF
  done < /root/scripts/hosts/idc-hadoop.txt
