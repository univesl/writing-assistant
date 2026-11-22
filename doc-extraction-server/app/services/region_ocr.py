"""第一页左上角收文章识别（qwen VLM 版）。

2026-11-22: 由本地 RapidOCR 切换为 qwen 视觉模型——收文登记章的红章小字
（收文编号/日期）RapidOCR 识别残缺（如"〔2026〕1078号"识别成"切18号"），
qwen 可完整识别；彩色截图直传，无需灰度预处理。
"""

import base64
import os
import time
from pathlib import Path

import requests


OCR_REGION = tuple(float(x) for x in os.getenv("OCR_TOP_LEFT_REGION", "0,0,0.42,0.18").split(","))
OCR_RENDER_SCALE = float(os.getenv("OCR_RENDER_SCALE", "3"))

QWEN_VLM_API_URL = os.getenv("QWEN_VLM_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
QWEN_VLM_API_KEY = os.getenv("QWEN_VLM_API_KEY", "")
QWEN_VLM_MODEL = os.getenv("QWEN_VLM_MODEL", "qwen3.8-max")
QWEN_VLM_TIMEOUT = float(os.getenv("QWEN_VLM_TIMEOUT", "60"))

_PROMPT = (
    "这是公文首页左上角的收文登记章区域截图。请逐字识别图中所有文字"
    "（如收文机关From、收文单位To、收文编号/字号、收文日期等），"
    "按原样逐行输出，不要推测不存在的内容。"
)


def _render_top_left_png(pdf_path: Path) -> bytes:
    """渲染首页左上角区域为彩色 PNG（与旧 RapidOCR 版同区域参数）。"""
    import fitz

    document = fitz.open(str(pdf_path))
    if not document.page_count:
        raise ValueError("PDF没有页面")
    page = document.load_page(0)
    left, top, right, bottom = OCR_REGION
    # clip 直接用页面坐标系（归一化区域 × 页面尺寸），一次渲染出目标区域
    rect = page.rect
    clip = fitz.Rect(rect.width * left, rect.height * top, rect.width * right, rect.height * bottom)
    scale = OCR_RENDER_SCALE
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, clip=clip)
    return pixmap.tobytes("png")


def extract_first_page_top_left(pdf_path: Path) -> dict:
    """用 qwen VLM 识别首页左上角；失败时返回空结果（不影响主流程）。"""
    if not QWEN_VLM_API_KEY:
        return {"text": "", "confidence": 0.0, "error": "QWEN_VLM_API_KEY 未配置"}

    try:
        png = _render_top_left_png(pdf_path)
        b64 = base64.b64encode(png).decode()
        payload = {
            "model": QWEN_VLM_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": _PROMPT},
                ],
            }],
            "max_tokens": 800,
            # 关思考：默认思考 35s+，关闭后 2s 内返回且识别质量不降
            "enable_thinking": False,
        }
        headers = {"Authorization": f"Bearer {QWEN_VLM_API_KEY}"}

        last_err = None
        for attempt in range(2):  # 网关偶发 400/超时，重试一次
            try:
                resp = requests.post(
                    f"{QWEN_VLM_API_URL}/chat/completions",
                    headers=headers, json=payload, timeout=QWEN_VLM_TIMEOUT,
                )
                if resp.status_code == 200:
                    text = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content") or ""
                    return {"text": text.strip(), "confidence": 1.0, "error": None}
                last_err = f"HTTP {resp.status_code}"
            except requests.exceptions.RequestException as exc:
                last_err = f"{type(exc).__name__}: {exc}"
            if attempt == 0:
                time.sleep(2)
        return {"text": "", "confidence": 0.0, "error": f"VLM识别失败: {last_err}"}
    except Exception as exc:
        return {"text": "", "confidence": 0.0, "error": f"区域识别异常: {type(exc).__name__}: {exc}"}
