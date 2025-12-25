import sqlite3

# 连接到数据库
conn = sqlite3.connect('writing_assistant.db')
cursor = conn.cursor()

# 查看所有会话
print('所有会话:')
cursor.execute('SELECT * FROM sessions;')
sessions = cursor.fetchall()
for session in sessions:
    print(session)

# 查看所有内容
print('\n所有内容:')
cursor.execute('SELECT * FROM contents;')
contents = cursor.fetchall()
for content in contents:
    print(content)

# 关闭连接
conn.close()