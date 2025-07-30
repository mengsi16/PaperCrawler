# paper_crawler.py (Stealth & Reordered)
import asyncio
import os
import re
import httpx

# --- Selenium Imports ---
import undetected_chromedriver as webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# --- httpx-based Downloaders ---
from strategies.implementations import (
    ArxivDownloader,
    CoreDownloader,
    AaaiOjsDownloader,
    NeuripsDownloader,
    CvfDownloader
)

# --- Selenium-based Downloaders ---
from strategies.selenium_implementations import (
    AcmDlSeleniumDownloader,
    IeeeSeleniumDownloader
)

CORE_API_KEY = "Your CORE KEY"  # 请替换为你的API Key

# 会议到来源的映射
CONFERENCE_TO_SOURCE_MAP = {
    # IEEE
    's&p': 'ieee',
    'oakland': 'ieee',
    # ACM
    'ccs': 'acm',
    'www': 'acm',
    # Specific Downloaders
    'aaai': 'aaai',
    'neurips': 'neurips',
    'cvpr': 'cvpr',
    'iccv': 'iccv',
}

class PaperCrawler:
    def __init__(self, save_dir: str, core_api_key: str = CORE_API_KEY, request_delay: int = 2):
        self.save_directory = os.path.abspath(save_dir)
        self.core_api_key = core_api_key
        self.request_delay = request_delay
        self.timeout_config = httpx.Timeout(20.0, read=60.0)
        os.makedirs(self.save_directory, exist_ok=True)
        self.driver = None

    def setup_driver(self):
        """
        [核心升级] 初始化并配置带有反检测功能的 Selenium WebDriver。
        """
        if self.driver is None:
            print("🔧 Setting up Stealth Selenium WebDriver...")
            chrome_options = Options()
            # --- 其他常规配置 ---
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # --- PDF下载设置 ---
            # 使用undetected_chromedriver支持的方式设置首选项
            download_path = os.path.abspath(self.save_directory)
            chrome_options.add_argument(f"--download.default_directory={download_path}")
            chrome_options.add_argument("--download.prompt_for_download=false")
            chrome_options.add_argument("--plugins.always_open_pdf_externally=true")
            
            try:
                # 使用undetected_chromedriver来更好地处理SSL和反检测
                self.driver = webdriver.Chrome(service=Service('./undetected_chromedriver.exe'),options=chrome_options,driver_executable_path="./chromedriver.exe")
                
                # 初始化后立即设置下载行为
                self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': download_path
                })
                
                print(
                    "✅ Stealth Selenium WebDriver is ready. Please complete any necessary logins in the browser window.")
            except Exception as e:
                print(f"❌ Failed to set up Selenium WebDriver: {e}")
                self.driver = None

    def teardown_driver(self):
        """
        [公开方法] 关闭Selenium WebDriver。
        """
        if self.driver:
            print("👋 Shutting down Selenium WebDriver.")
            self.driver.quit()
            self.driver = None

    def _normalize_title(self, title: str) -> str:
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\s-]', ' ', title.lower())).strip()

    def _sanitize_filename(self, title: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "_", title.strip())[:150] + ".pdf"

    async def _process_single_paper(self, title: str, conference: str | None = None) -> str | None:
        if not title.strip(): return None
        original_title = title.strip()
        normalized_title = self._normalize_title(original_title)
        filepath = os.path.join(self.save_directory, self._sanitize_filename(original_title))
        print(filepath)
        if os.path.exists(filepath):
            print(f"🟢 File already exists, skipping: {filepath}")
            return filepath

        print(f"\n🚀 Starting download for: '{original_title}' (Conference: {conference or 'Unspecified'})")

        # --- 更健壮的策略调度逻辑 ---
        async with httpx.AsyncClient(timeout=self.timeout_config, follow_redirects=True) as session:
            
            # 1. 构建所有可用的策略实例
            httpx_strategies = {
                'aaai': AaaiOjsDownloader(session, self.save_directory),
                'neurips': NeuripsDownloader(session, self.save_directory),
                'cvpr': CvfDownloader(session, self.save_directory),
                'iccv': CvfDownloader(session, self.save_directory),
                'arxiv': ArxivDownloader(session, self.save_directory),
                'core': CoreDownloader(session, self.save_directory, self.core_api_key),
            }
            selenium_strategies = {}
            if self.driver:
                selenium_strategies['acm'] = AcmDlSeleniumDownloader(self.driver, self.save_directory)
                selenium_strategies['ieee'] = IeeeSeleniumDownloader(self.driver, self.save_directory)
            else:
                 print("   [Warning] Selenium driver not available, skipping platform-specific strategies (ACM, IEEE).")

            # 2. 定义包含所有通用后备策略的有序列表
            all_fallback_strategies = []
            all_fallback_strategies.extend([httpx_strategies['core']])
            if 'acm' in selenium_strategies: all_fallback_strategies.append(selenium_strategies['acm'])
            if 'ieee' in selenium_strategies: all_fallback_strategies.append(selenium_strategies['ieee'])
            all_fallback_strategies.extend([httpx_strategies['arxiv']])
            
            # 3. 根据 conference 构建最终的策略队列
            strategy_queue = []
            primary_strategy = None
            if conference:
                conf_key = conference.lower()
                source = CONFERENCE_TO_SOURCE_MAP.get(conf_key)
                print(f"   [Info] Conference '{conference}' mapped to source: {source or 'Generic'}")
                
                # 确定主要策略
                if source == 'ieee' and 'ieee' in selenium_strategies:
                    primary_strategy = selenium_strategies['ieee']
                elif source == 'acm' and 'acm' in selenium_strategies:
                    primary_strategy = selenium_strategies['acm']
                elif source in httpx_strategies:
                    primary_strategy = httpx_strategies[source]
                
                # 将主要策略放在首位
                if primary_strategy:
                    strategy_queue.append(primary_strategy)

                # 添加所有不重复的后备策略
                for fallback in all_fallback_strategies:
                    if fallback is not primary_strategy:
                        strategy_queue.append(fallback)
            else:
                # 如果没有指定会议，则使用完整的后备策略列表
                print("   [Info] No conference specified. Trying all major platforms.")
                strategy_queue = all_fallback_strategies

            # 4. 按顺序执行策略队列
            for strategy in strategy_queue:
                print(f"   -> Trying strategy: {strategy.__class__.__name__}")
                try:
                    success = False
                    # 判断策略是同步还是异步
                    if asyncio.iscoroutinefunction(strategy.download):
                        # 异步策略
                        await asyncio.sleep(self.request_delay)
                        if await strategy.download(normalized_title, filepath):
                             success = True
                    else:
                        # 同步策略 (Selenium)
                        if strategy.download(original_title, filepath):
                            success = True
                    
                    if success:
                        print(f"✅ [SUCCESS] Downloaded via strategy: {strategy.__class__.__name__}.")
                        return filepath
                except Exception as e:
                    print(f"   [Error] Strategy {strategy.__class__.__name__} failed with error: {e}")
            
        print(f"❌ [FAILURE] All strategies failed for: '{original_title}'")
        return None

    def download_paper(self, title: str, conference: str | None = None) -> str | None:
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            return asyncio.run(self._process_single_paper(title, conference))
        except Exception as e:
            print(f"An unexpected error occurred in the event loop for '{title}': {e}")
            return None
