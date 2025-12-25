import sqlite3

# 连接到数据库
conn = sqlite3.connect('writing_assistant.db')
cursor = conn.cursor()

print('=== 检查数据库表结构和外键约束 ===')

# 查看表结构
print('\n1. 查看sessions表结构:')
cursor.execute("PRAGMA table_info(sessions)")
sessions_info = cursor.fetchall()
for info in sessions_info:
    print(f'   {info}')

print('\n2. 查看contents表结构:')
cursor.execute("PRAGMA table_info(contents)")
contents_info = cursor.fetchall()
for info in contents_info:
    print(f'   {info}')

# 查看外键约束
print('\n3. 查看contents表的外键约束:')
cursor.execute("PRAGMA foreign_key_list(contents)")
fk_list = cursor.fetchall()
if fk_list:
    for fk in fk_list:
        print(f'   {fk}')
else:
    print('   没有发现外键约束')

# 检查外键约束是否启用
print('\n4. 检查外键约束是否启用:')
cursor.execute("PRAGMA foreign_keys")
fk_enabled = cursor.fetchone()[0]
if fk_enabled:
    print('   ✓ 外键约束已启用')
else:
    print('   ✗ 外键约束未启用')

# 关闭连接
conn.close()
print('\n=== 检查完成 ===')