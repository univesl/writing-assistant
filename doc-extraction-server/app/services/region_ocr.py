"""第一页重点区域 OCR。依赖可选，缺失时安全降级。"""

import os
from pathlib import Path


OCR_REGION = tuple(float(x) for x in os.getenv("OCR_TOP_LEFT_REGION", "0,0,0.42,0.18").split(","))


def extract_first_page_top_left(pdf_path: Path) -> dict:
    """渲染并识别第一页左上角，失败时返回空结果。"""
    try:
        import fitz
        import numpy as np
        from PIL import Image, ImageEnhance, ImageOps
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        return {"text": "", "confidence": 0.0, "error": f"OCR依赖未安装: {exc.name}"}

    try:
        document = fitz.open(str(pdf_path))
        if not document.page_count:
            return {"text": "", "confidence": 0.0, "error": "PDF没有页面"}
        page = document.load_page(0)
        scale = float(os.getenv("OCR_RENDER_SCALE", "3"))
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        left, top, right, bottom = OCR_REGION
        crop = image.crop((int(image.width * left), int(image.height * top), int(image.width * right), int(image.height * bottom)))
        crop = ImageEnhance.Contrast(ImageOps.grayscale(crop)).enhance(1.8)
        crop = crop.resize((crop.width * 2, crop.height * 2))
        result, _ = RapidOCR()(np.asarray(crop))
        lines = result or []
        text = "\n".join(str(item[1]).strip() for item in lines if len(item) > 1 and str(item[1]).strip())
        scores = [float(item[2]) for item in lines if len(item) > 2]
        return {"text": text, "confidence": sum(scores) / len(scores) if scores else 0.0, "error": None}
    except Exception as exc:
        return {"text": "", "confidence": 0.0, "error": f"OCR识别失败: {type(exc).__name__}"}
