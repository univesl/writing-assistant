# AI 写作助手

一个基于 React + FastAPI 的智能写作辅助工具，提供多种写作功能和会话管理。

## 功能特性

### 📝 写作功能
- **快速写作**：输入关键词或主题，快速生成文章内容
- **步骤式写作**：基于产品特点、卖点等参数，分步骤生成营销文案
- **校对润色**：检查并优化现有文本，提升写作质量

### 💬 会话管理
- 创建、删除、重命名会话
- 多会话并行编辑
- 自动保存会话内容

### 🎨 用户界面
- 响应式设计，适配不同屏幕尺寸
- 简洁直观的操作界面
- 实时内容预览

## 技术栈

### 前端（frontend）
- **框架**：React 19
- **构建工具**：Vite 7
- **HTTP 客户端**：Axios
- **样式**：CSS3

### 后端（backend）
- **框架**：FastAPI
- **数据库**：SQLite (SQLAlchemy ORM)
- **AI 引擎**：OpenAI API
- **服务器**：Uvicorn

## 安装与运行

### 前置要求
- Node.js 16+ (前端)
- Python 3.8+ (后端)

### 1. 克隆仓库

```bash
git clone <仓库地址>
cd writing-assistant
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境（可选但推荐）
python -m venv venv

# 激活虚拟环境
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动后端服务器
python -m uvicorn app.main:app --reload
```

后端服务将在 `http://localhost:8000` 运行

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 启动前端开发服务器
npm run dev
```

前端应用将在 `http://localhost:5173` 运行

## 项目结构

```
writing-assistant/
├── frontend/              # 前端代码
│   ├── public/            # 静态资源
│   ├── src/               # 源代码
│   │   ├── api/           # API 调用模块
│   │   ├── components/    # React 组件
│   │   ├── assets/        # 图片等资源
│   │   ├── App.jsx        # 主应用组件
│   │   └── main.jsx       # 应用入口
│   ├── package.json       # 项目配置
│   └── vite.config.js     # Vite 配置
├── backend/               # 后端代码
│   ├── app/               # 主应用包
│   │   ├── routers/       # API 路由
│   │   ├── services/      # 业务逻辑服务
│   │   ├── models.py      # 数据库模型
│   │   ├── schemas.py     # 数据验证模式
│   │   └── main.py        # 应用入口
│   ├── requirements.txt   # 依赖列表
│   └── writing_assistant.db  # SQLite 数据库
└── .gitignore            # Git 忽略文件
```

## API 文档

启动后端服务后，可访问以下地址查看 API 文档：
- **Swagger UI**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

### 主要 API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/health | 检查服务健康状态 |
| GET | /api/sessions | 获取所有会话 |
| POST | /api/sessions | 创建新会话 |
| DELETE | /api/sessions/{session_id} | 删除指定会话 |
| PUT | /api/sessions/{session_id} | 重命名会话 |
| GET | /api/write/{session_id} | 获取会话内容 |
| POST | /api/write/{session_id} | 生成写作内容 |
| POST | /api/write/quick | 快速写作 |
| POST | /api/write/step | 步骤式写作 |
| POST | /api/write/polish | 校对润色 |

## 使用说明

1. **创建会话**：点击左侧栏的"新建会话"按钮
2. **选择写作模式**：在右侧面板选择快速写作、步骤式写作或校对润色
3. **输入参数**：根据选择的模式输入相应的参数
4. **生成内容**：点击生成按钮，等待AI生成内容
5. **编辑和保存**：内容生成后可以继续编辑，系统会自动保存

## 配置

### 后端配置

在 `backend/.env` 文件中配置以下环境变量（可选）：

```
# OpenAI API 密钥
OPENAI_API_KEY=your-openai-api-key

# 服务器端口
PORT=8000

# 数据库路径
DATABASE_URL=sqlite:///./writing_assistant.db
```

### 前端配置

前端 API 基础 URL 配置在 `frontend/src/api/axiosConfig.js` 中：

```javascript
// 默认 API 基础 URL
const API_BASE_URL = 'http://localhost:8000/api'
```

## 开发说明

### 前端开发

```bash
cd frontend

# 运行开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 代码检查
npm run lint
```

### 后端开发

```bash
cd backend

# 启动开发服务器（自动重载）
python -m uvicorn app.main:app --reload

# 运行测试
python -m pytest
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，请通过以下方式联系：
- 邮箱：your-email@example.com
- GitHub：https://github.com/your-username/writing-assistant
