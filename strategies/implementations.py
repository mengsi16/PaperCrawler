# strategies/implementations.py (Corrected and Refined)
import httpx
import xml.etree.ElementTree as ET
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

# 导入我们之前定义的抽象基类
from strategies.download_strategy import DownloadStrategy


# --- 保留的下载器 ---

class ArxivDownloader(DownloadStrategy):
    """从arXiv下载论文的策略。"""

    def __init__(self, session: httpx.AsyncClient, save_dir: str):
        super().__init__(session, save_dir)
        self.api_url = "https://export.arxiv.org/api/query?"

    async def download(self, normalized_title: str, filepath: str) -> bool:
        print("   -> [Strategy: arXiv] Trying to find and download...")
        try:
            params = {"search_query": f'ti:"{normalized_title}"', "start": 0, "max_results": 1}
            response = await self.session.get(self.api_url, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            entry = root.find('atom:entry', namespace)
            if entry:
                pdf_link_element = entry.find("atom:link[@title='pdf']", namespace)
                if pdf_link_element is not None and pdf_link_element.get('href'):
                    pdf_url = pdf_link_element.get('href')
                    return await self._download_pdf_from_url(pdf_url, filepath)
            print("   -> [Strategy: arXiv] 🟡 Paper not found.")
            return False
        except Exception as e:
            print(f"   -> [Strategy: arXiv] ❌ An error occurred: {e}")
            return False


class CoreDownloader(DownloadStrategy):
    """
    从CORE下载论文的策略。
    [修正] 已更新为使用POST请求和JSON负载，以提高稳定性。
    """

    def __init__(self, session: httpx.AsyncClient, save_dir: str, api_key: str):
        super().__init__(session, save_dir)
        self.api_url = "https://api.core.ac.uk/v3/search/works"
        self.api_key = api_key
        if self.api_key: self.headers["Authorization"] = f"Bearer {self.api_key}"

    async def download(self, normalized_title: str, filepath: str) -> bool:
        if not self.api_key: return False
        print("   -> [Strategy: CORE] Trying to find and download...")
        try:
            # 使用POST请求发送JSON数据，避免URL编码问题
            data = {"q": f'title:("{normalized_title}")'}
            response = await self.session.post(self.api_url, json=data, headers=self.headers)
            response.raise_for_status()
            results = response.json()
            if results.get("results"):
                download_url = results["results"][0].get("downloadUrl")
                if download_url: return await self._download_pdf_from_url(download_url, filepath)
            print("   -> [Strategy: CORE] 🟡 Paper not found or no download link.")
            return False
        except Exception as e:
            print(f"   -> [Strategy: CORE] ❌ An error occurred: {e}")
            return False


class AaaiOjsDownloader(DownloadStrategy):
    """从 ojs.aaai.org 下载AAAI会议论文的策略。"""

    def __init__(self, session: httpx.AsyncClient, save_dir: str):
        super().__init__(session, save_dir)
        self.search_url = "https://ojs.aaai.org/index.php/AAAI/search/search"

    async def download(self, normalized_title: str, filepath: str) -> bool:
        print("   -> [Strategy: AAAI OJS] Trying to find and download...")
        try:
            # 使用未标准化的标题进行搜索，以获得更好的匹配效果
            search_response = await self.session.get(self.search_url, params={'query': normalized_title})
            search_response.raise_for_status()
            soup = BeautifulSoup(search_response.text, 'html.parser')
            article_link = soup.select_one('h3.title a, h4.title a')
            if not article_link or not article_link.get('href'):
                print("   -> [Strategy: AAAI OJS] 🟡 Paper not found.")
                return False
            article_page_url = article_link.get('href')
            article_response = await self.session.get(article_page_url)
            article_response.raise_for_status()
            article_soup = BeautifulSoup(article_response.text, 'html.parser')
            pdf_link = article_soup.select_one('a.obj_galley_link.pdf')
            if not pdf_link or not pdf_link.get('href'):
                print(f"   -> [Strategy: AAAI OJS] 🟡 Found article page but no PDF link: {article_page_url}")
                return False
            pdf_url = pdf_link.get('href').replace('/view/', '/download/')
            return await self._download_pdf_from_url(pdf_url, filepath)
        except Exception as e:
            print(f"   -> [Strategy: AAAI OJS] ❌ An error occurred: {e}")
            return False


class NeuripsDownloader(DownloadStrategy):
    """
    从 proceedings.neurips.cc 下载 NeurIPS 论文的策略。
    [修正] 改进了链接查找逻辑，避免跳转到admin登录页。
    """

    def __init__(self, session: httpx.AsyncClient, save_dir: str):
        super().__init__(session, save_dir)
        self.base_url = "https://proceedings.neurips.cc"
        self.search_url = f"{self.base_url}/papers/search"

    async def download(self, normalized_title: str, filepath: str) -> bool:
        print(f"   -> [Strategy: NeurIPS Search] Trying to find and download...")
        try:
            params = {'q': normalized_title}
            search_response = await self.session.get(self.search_url, params=params)
            search_response.raise_for_status()
            soup = BeautifulSoup(search_response.text, 'html.parser')

            # 查找所有论文链接，并与标题进行匹配
            paper_links = soup.select('div.container-fluid ul li a')
            found_link = None
            for link in paper_links:
                # 进行不区分大小写和空格的模糊匹配
                if normalized_title.lower().replace(" ", "") in link.get_text(strip=True).lower().replace(" ", ""):
                    found_link = link
                    break

            if not found_link or not found_link.get('href'):
                print("   -> [Strategy: NeurIPS Search] 🟡 Paper not found in search results.")
                return False

            abstract_url = urljoin(self.base_url, found_link.get('href'))

            # 从摘要页面链接构建PDF链接
            pdf_url = abstract_url.replace("Abstract.html", "Paper.pdf").replace("/hash/", "/file/")
            print(f"   -> [Strategy: NeurIPS Search] ✅ Found potential PDF link: {pdf_url}")
            return await self._download_pdf_from_url(pdf_url, filepath)

        except Exception as e:
            print(f"   -> [Strategy: NeurIPS Search] ❌ An error occurred: {e}")
            return False


# 注意：ACM和IEEE的httpx版本已被移除，因为它们不可靠。
# 请使用下面新文件中的Selenium版本。
class CvfDownloader(DownloadStrategy):
    """从 CVF (openaccess.thecvf.com) 下载论文，例如 CVPR, ICCV。"""

    def __init__(self, session: httpx.AsyncClient, save_dir: str):
        super().__init__(session, save_dir)
        self.base_url = "https://openaccess.thecvf.com"
        # CVF的搜索功能有时不稳定，直接访问会议页面可能更好
        # self.search_url = f"{self.base_url}/search_result"
        # 此处保留原有逻辑，但可以考虑后续优化为直接爬取会议页面

    async def download(self, normalized_title: str, filepath: str) -> bool:
        print("   -> [Strategy: CVF Open Access] Trying to find and download...")
        try:
            # 1. 在CVF网站上搜索
            params = {"q": normalized_title}
            search_response = await self.session.get(f"{self.base_url}/search_result", params=params)
            search_response.raise_for_status()
            soup = BeautifulSoup(search_response.text, 'html.parser')

            # 2. 查找第一个搜索结果
            result_link = soup.select_one('div.content div dl dt a')
            if not result_link or not result_link.get('href'):
                print("   -> [Strategy: CVF Open Access] 🟡 Paper not found in search results.")
                return False

            # 3. 从摘要页面链接构建PDF链接
            abstract_url = urljoin(self.base_url, result_link.get('href'))

            # 访问摘要页以找到PDF链接
            abstract_page_resp = await self.session.get(abstract_url)
            abstract_page_resp.raise_for_status()
            abstract_soup = BeautifulSoup(abstract_page_resp.text, 'html.parser')

            # 寻找包含 "pdf" 文本的链接
            pdf_link = abstract_soup.find('a', href=re.compile(r'\.pdf$'))
            if not pdf_link:
                print(f"   -> [Strategy: CVF Open Access] 🟡 Found abstract page but no PDF link: {abstract_url}")
                return False

            pdf_url = urljoin(abstract_url, pdf_link['href'])
            print(f"   -> [Strategy: CVF Open Access] ✅ Found PDF link: {pdf_url}")
            return await self._download_pdf_from_url(pdf_url, filepath)
        except Exception as e:
            print(f"   -> [Strategy: CVF Open Access] ❌ An error occurred: {e}")
            return False
