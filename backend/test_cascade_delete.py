import sqlite3

# 连接到数据库
conn = sqlite3.connect('writing_assistant.db')
cursor = conn.cursor()

print('=== 测试级联删除功能 ===')

# 创建一个测试会话
print('\n1. 创建一个新的测试会话')
cursor.execute("INSERT INTO sessions (session_name, created_at) VALUES (?, datetime('now'))", ('测试会话',))
test_session_id = cursor.lastrowid
conn.commit()
print(f'   创建的会话ID: {test_session_id}')

# 为该会话添加测试内容
print('2. 为测试会话添加内容')
test_content_ids = []
for i in range(3):
    content_text = f'测试内容 {i+1} 属于会话 {test_session_id}'
    cursor.execute("INSERT INTO contents (session_id, content, content_type, created_at) VALUES (?, ?, ?, datetime('now'))", 
                  (test_session_id, content_text, 'quick'))
    test_content_ids.append(cursor.lastrowid)
conn.commit()
print(f'   添加了3条测试内容，ID分别为: {test_content_ids}')

# 查看创建的会话
print(f'\n3. 创建的测试会话:')
cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (test_session_id,))
test_session = cursor.fetchone()
print(f'   {test_session}')

print(f'\n4. 删除测试会话 (ID: {test_session_id})')
cursor.execute("DELETE FROM sessions WHERE session_id = ?", (test_session_id,))
conn.commit()
print('   会话已删除')

# 验证会话是否被删除
print(f'\n5. 验证会话 {test_session_id} 是否被删除:')
cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (test_session_id,))
remaining_session = cursor.fetchone()
if not remaining_session:
    print('   ✓ 会话已被删除')
else:
    print(f'   ✗ 会话未被删除: {remaining_session}')

# 验证内容是否被自动删除
print(f'\n6. 验证测试会话的内容是否被级联删除:')
cursor.execute("SELECT * FROM contents WHERE content_id IN (?, ?, ?)", tuple(test_content_ids))
remaining_contents = cursor.fetchall()
if not remaining_contents:
    print('   ✓ 测试通过：所有关联的内容已被自动删除')
else:
    print(f'   ✗ 测试失败：仍有 {len(remaining_contents)} 条内容未被删除')
    for content in remaining_contents:
        print(f'      {content}')

# 清理临时文件
conn.close()
print('\n=== 测试完成 ===')