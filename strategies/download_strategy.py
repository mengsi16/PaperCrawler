# strategies/download_strategy.py
import httpx
import aiofiles
import os
from abc import ABC, abstractmethod


class DownloadStrategy(ABC):
    """
    下载策略的抽象基类 (Abstract Base Class)。
    所有具体的下载策略（如arXiv, CORE, AAAI, CVF）都应继承此类，
    并实现 download 方法。
    """

    def __init__(self, session: httpx.AsyncClient, save_dir: str):
        """
        初始化策略。

        Args:
            session (httpx.AsyncClient): 用于发出网络请求的客户端实例。
            save_dir (str): PDF文件的保存目录。
        """
        self.session = session
        self.save_directory = save_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    @abstractmethod
    async def download(self, normalized_title: str, filepath: str) -> bool:
        """
        尝试使用本策略下载论文。

        Args:
            normalized_title (str): 标准化后的论文标题。
            filepath (str): 预期的PDF文件保存路径。

        Returns:
            bool: 如果下载成功则返回 True，否则返回 False。
        """
        pass

    async def _download_pdf_from_url(self, pdf_url: str, filepath: str) -> bool:
        """
        一个通用的辅助函数，用于从给定的URL异步下载PDF文件。
        所有子类都可以复用这个函数。
        """
        try:
            print(f"      [Downloader] Attempting to download from: {pdf_url}")
            async with self.session.stream('GET', pdf_url, headers=self.headers, follow_redirects=True) as response:
                response.raise_for_status()

                content_type = response.headers.get('content-type', '').lower()
                if 'application/pdf' not in content_type:
                    print(f"      [Downloader] ❌ Failed: URL did not point to a PDF. Content-Type: {content_type}")
                    return False

                async with aiofiles.open(filepath, 'wb') as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
                print(f"      [Downloader] ✅ Successfully saved to: {filepath}")
                return True
        except Exception as e:
            print(f"      [Downloader] ❌ Download failed from {pdf_url}: {repr(e)}")
            if os.path.exists(filepath):
                os.remove(filepath)
            return False