# 3 server 6 shili

# zhixing role

ansible-playbook -i redis.ini roles/role_redis.yml

# shiyong tags

ansible-playbook -i redis.ini --tags=up  roles/role_redis.yml




