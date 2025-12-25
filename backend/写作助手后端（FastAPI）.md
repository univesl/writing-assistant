## 1）环境安装（Windows + Anaconda）
打开 **Anaconda Prompt**：

```bat
cd /d D:\writing-assistant-backend
conda create -n writing-backend python=3.11 -y
conda activate writing-backend
pip install -r requirements.txt
```

## 2）启动后端

```bat
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 3）接口文档与测试入口

- Swagger： [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
    
- OpenAPI： [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
    
- Health： [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
    

## 4）自动化自测

保持后端服务在运行（不要关闭启动窗口），再打开 **另一个** Anaconda Prompt：

```bat
cd /d D:\writing-assistant-backend
conda activate writing-backend
pip install httpx
python smoke_test.py --base-url http://127.0.0.1:8000/api
```

看到 `ALL TESTS PASSED` 即表示后端核心接口（含 SSE 流式）可用。

## 5）接入大模型的修改位置

大模型接入统一在 `app/services/llm.py` 中完成。将文件内的 `build_quick_output`、`build_step_output`、`polish_text` 三个函数替换为真实的大模型调用（例如 OpenAI / 本地 vLLM / Ollama 等），接口层 `app/routers/write.py` 通常不需要修改。