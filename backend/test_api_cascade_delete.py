import requests
import time

BASE_URL = "http://localhost:8000/api"

print('=== 测试API级联删除功能 ===')

# 创建一个测试会话
print('\n1. 创建一个新的测试会话')
create_response = requests.post(f"{BASE_URL}/session/create", json={"session_name": "API测试会话"})
if create_response.status_code == 200:
    session_data = create_response.json()
    test_session_id = session_data["data"]["session_id"]
    print(f'   ✓ 会话创建成功，ID: {test_session_id}')
else:
    print(f'   ✗ 会话创建失败: {create_response.text}')
    exit(1)

# 为该会话添加测试内容
print('2. 为测试会话添加内容')
content_texts = ["API测试内容1", "API测试内容2", "API测试内容3"]
added_content_ids = []

for i, content_text in enumerate(content_texts):
    # 我们需要通过write API来添加内容，但为了简化测试，我们直接使用数据库操作
    # 这里我们先跳过，直接测试删除功能
    print(f'   添加内容 {i+1}: {content_text}')

# 使用自定义的API来添加测试内容（为了测试目的）
print('   使用write API添加内容...')
for content_text in content_texts:
    write_response = requests.post(f"{BASE_URL}/write/quick", json={
        "session_id": test_session_id,
        "input_text": content_text
    })
    if write_response.status_code == 200:
        print(f'     ✓ 添加内容成功')
    else:
        print(f'     ✗ 添加内容失败: {write_response.text}')

# 检查会话内容
print(f'\n3. 检查会话 {test_session_id} 的内容:')
content_response = requests.get(f"{BASE_URL}/content/get/{test_session_id}")
if content_response.status_code == 200:
    content_data = content_response.json()
    contents = content_data["data"]
    print(f'   ✓ 找到 {len(contents)} 条内容:')
    for content in contents:
        print(f'     - {content["content"]}')
else:
    print(f'   ✗ 获取内容失败: {content_response.text}')

# 删除测试会话
print(f'\n4. 删除测试会话 (ID: {test_session_id})')
delete_response = requests.delete(f"{BASE_URL}/session/delete/{test_session_id}")
if delete_response.status_code == 200:
    print('   ✓ 会话删除成功')
else:
    print(f'   ✗ 会话删除失败: {delete_response.text}')
    exit(1)

# 验证会话是否被删除
print(f'\n5. 验证会话 {test_session_id} 是否被删除:')
sessions_response = requests.get(f"{BASE_URL}/session/list")
if sessions_response.status_code == 200:
    sessions_data = sessions_response.json()
    sessions = sessions_data["data"]
    session_exists = any(session["session_id"] == test_session_id for session in sessions)
    if not session_exists:
        print('   ✓ 会话已被删除')
    else:
        print(f'   ✗ 会话未被删除')
else:
    print(f'   ✗ 获取会话列表失败: {sessions_response.text}')

# 验证内容是否被自动删除
print(f'\n6. 验证会话 {test_session_id} 的内容是否被删除:')
content_response = requests.get(f"{BASE_URL}/content/get/{test_session_id}")
if content_response.status_code == 200:
    content_data = content_response.json()
    contents = content_data["data"]
    if not contents:
        print('   ✓ 测试通过：所有关联的内容已被自动删除')
    else:
        print(f'   ✗ 测试失败：仍有 {len(contents)} 条内容未被删除')
        for content in contents:
            print(f'     - {content["content"]}')
else:
    print(f'   ✗ 获取内容失败: {content_response.text}')

print('\n=== 测试完成 ===')