import os
import time
import zipfile
import requests
import subprocess
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

MINERU_API_TOKEN = os.getenv("MINERU_API_TOKEN", "")

class MinerUService:
    def __init__(self, api_token: str = MINERU_API_TOKEN):
        self.api_token = api_token
        self.base_url = "https://mineru.net/api/v4"

    def parse_pdf_to_markdown(self, pdf_path: str) -> Optional[str]:
        """解析PDF文件为Markdown内容

        Args:
            pdf_path: PDF文件路径

        Returns:
            Markdown内容字符串，失败返回None
        """
        try:
            file_name = os.path.basename(pdf_path)

            upload_info = self._get_upload_urls([file_name])
            if not upload_info:
                print(f"[MinerU] 获取上传URL失败: {file_name}")
                return None

            batch_id = upload_info["batch_id"]
            upload_urls = upload_info["file_urls"]

            upload_success = self._upload_file(pdf_path, upload_urls[0])
            if not upload_success:
                print(f"[MinerU] 上传失败: {file_name}")
                return None

            result = self._wait_for_completion(batch_id)
            if not result:
                print(f"[MinerU] 解析失败或超时: {file_name}")
                return None

            markdown_content = self._extract_markdown(result)
            if markdown_content:
                print(f"[MinerU] 解析成功: {file_name}")
            return markdown_content

        except Exception as e:
            print(f"[MinerU] 解析异常: {e}")
            return None

    def _get_upload_urls(self, file_names: list) -> Optional[dict]:
        url = f"{self.base_url}/file-urls/batch"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }

        files_data = []
        for file_name in file_names:
            files_data.append({
                "name": file_name,
                "data_id": file_name.split('.')[0]
            })

        data = {"files": files_data, "model_version": "vlm"}

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return {
                        "batch_id": result["data"]["batch_id"],
                        "file_urls": result["data"]["file_urls"]
                    }
                else:
                    print(f"[MinerU] 获取URL失败: {result.get('msg', '未知错误')}")
            return None
        except Exception as e:
            print(f"[MinerU] 获取URL异常: {e}")
            return None

    def _upload_file(self, file_path: str, upload_url: str) -> bool:
        try:
            with open(file_path, 'rb') as f:
                response = requests.put(upload_url, data=f, timeout=120)
                return response.status_code == 200
        except Exception as e:
            print(f"[MinerU] 上传异常: {e}")
            return False

    def _wait_for_completion(self, batch_id: str, check_interval: int = 10, timeout: int = 600) -> Optional[dict]:
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self._get_batch_status(batch_id)
            if status is None:
                return None

            extract_result = status.get("extract_result", [])
            if not extract_result:
                time.sleep(check_interval)
                continue

            states = [item.get("state", "") for item in extract_result]
            overall_state = states[0] if states else ""
            print(f"[MinerU] 当前状态: {overall_state}")

            if overall_state in ["done", "completed"]:
                return status
            elif overall_state == "failed":
                return None
            else:
                time.sleep(check_interval)

        return None

    def _get_batch_status(self, batch_id: str) -> Optional[dict]:
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        headers = {"Authorization": f"Bearer {self.api_token}"}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    return result["data"]
            return None
        except Exception as e:
            print(f"[MinerU] 获取状态异常: {e}")
            return None

    def _extract_markdown(self, result: dict) -> Optional[str]:
        extract_result = result.get("extract_result", [])
        if not extract_result:
            return None

        for item in extract_result:
            zip_url = item.get("full_zip_url")
            if zip_url:
                import tempfile
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = Path(temp_dir) / "result.zip"

                    if self._download_with_retry(zip_url, zip_path):
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)

                            md_files = list(Path(temp_dir).glob("*.md"))
                            if md_files:
                                with open(md_files[0], 'r', encoding='utf-8') as f:
                                    return f.read()

                            nested_md = list(Path(temp_dir).rglob("*.md"))
                            if nested_md:
                                with open(nested_md[0], 'r', encoding='utf-8') as f:
                                    return f.read()
                        except Exception as e:
                            print(f"[MinerU] 解压异常: {e}")

        return None

    def _download_with_retry(self, url: str, output_path: Path, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=180)
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return True
            except Exception as e:
                if "cdn-mineru.openxlab.org.cn" in url:
                    try:
                        response = requests.get(url, timeout=180, verify=False)
                        if response.status_code == 200:
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            return True
                    except Exception:
                        pass
                    try:
                        curl_cmd = [
                            "curl.exe", "-k", "-L", "--silent", "--show-error",
                            "--connect-timeout", "30", "--max-time", "180",
                            "-o", str(output_path), url
                        ]
                        curl_result = subprocess.run(curl_cmd, check=False, capture_output=True, text=True)
                        if curl_result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                            return True
                    except Exception:
                        pass

            if attempt < max_retries - 1:
                time.sleep(5)

        return False


mineru_service = MinerUService()
