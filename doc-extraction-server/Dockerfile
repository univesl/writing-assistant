# ============================================================
# doc-extraction 公文解析服务 Dockerfile
#
# 镜像包含：Python 3.11 + pandoc（DOCX 解析）+ 全部 Python 依赖（含可选 OCR）。
# 配置通过运行时挂载的 .env 注入（见 docker-compose.yml），镜像本身不含密钥。
# ============================================================

FROM docker.1ms.run/library/python:3.11-slim

# pandoc: DOCX 解析必需；libgomp1: onnxruntime（OCR）运行库
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
    || sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list \
    ; apt-get update \
    && apt-get install -y --no-install-recommends pandoc libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存：代码改动不触发重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 代码
COPY app ./app

EXPOSE 8050

# 日志写到容器 stdout/stderr，由 docker logs 收集（时间/耗时由应用中间件输出）
CMD ["python", "-m", "uvicorn", "app.extractor_main:app", "--host", "0.0.0.0", "--port", "8050"]
