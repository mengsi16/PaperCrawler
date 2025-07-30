# strategies/selenium_implementations.py (XPath Precision)
import os
import time
from abc import ABC, abstractmethod
# from selenium import webdriver
import undetected_chromedriver as webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import re, difflib


class SeleniumDownloadStrategy(ABC):
    """
    使用 Selenium 进行下载的策略抽象基类。
    """

    def __init__(self, driver: webdriver.Chrome, save_dir: str):
        self.driver = driver
        self.save_directory = save_dir
        self.wait = WebDriverWait(self.driver, 25)  # 增加等待时间以应对慢速网络

        # 设置页面加载策略，忽略SSL错误
        self.driver.set_page_load_timeout(30)
        # 添加忽略SSL错误的参数
        self.driver.execute_cdp_cmd('Security.setIgnoreCertificateErrors', {'ignore': True})

    @abstractmethod
    def download(self, original_title: str, filepath: str) -> bool:
        """
        尝试使用本策略下载论文。
        """
        pass

    def _wait_for_download_and_rename(self, filepath: str, timeout: int = 120) -> bool:
        """
        一个更健壮的函数，用于等待文件下载完成并重命名。
        """
        initial_files = set(os.listdir(self.save_directory))
        end_time = time.time() + timeout
        print("      [Selenium] Waiting for download to start and complete...")
        while time.time() < end_time:
            # 检查是否有临时下载文件
            is_downloading = any(
                f.endswith('.crdownload') or f.endswith('.tmp') for f in os.listdir(self.save_directory))

            if not is_downloading:
                current_files = set(os.listdir(self.save_directory))
                new_files = current_files - initial_files
                if new_files:
                    downloaded_filename = new_files.pop()
                    # 确保文件已完全写入磁盘
                    time.sleep(2)
                    try:
                        os.rename(os.path.join(self.save_directory, downloaded_filename), filepath)
                        print(f"      [Selenium] ✅ Download complete and renamed to: {os.path.basename(filepath)}")
                        return True
                    except OSError as e:
                        print(f"      [Selenium] ❌ Error renaming file: {e}")
                        return False
            time.sleep(1)
        print("      [Selenium] 🟡 Timed out waiting for download to complete.")
        return False

class AcmDlSeleniumDownloader(SeleniumDownloadStrategy):
    """
    [XPath 精确版] 通过 Selenium 从 ACM Digital Library 下载论文。
    """

    def download(self, original_title: str, filepath: str) -> bool:
        print("   -> [Strategy: ACM DL] Trying to find and download...")

        # 1. 访问主页（带重试机制）
        try:
            print(f"      [Selenium-ACM] 正在访问 ACM Digital Library 主页...")
            self.driver.get("https://dl.acm.org/")
            # 等待页面加载完成
            self.driver.implicitly_wait(5)
            try:
                checkbox_selector = 'input[type="checkbox"]'
                checkbox = self.wait.until(EC.presence_of_element_located(By.CSS_SELECTOR, checkbox_selector))
                if checkbox:
                    print("      [Selenium-ACM] ✅ 找到隐私政策复选框，点击同意。")
                    checkbox.click()
                else:
                    print("      [Selenium-ACM] ❌ 未找到隐私政策复选框，可能已被移除。")
            except Exception as e:
                print("      [Selenium-ACM] 🟡 由人工操作。")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("      [Selenium-ACM] ✅ ACM DL 主页加载完成。")
            # 2. 查找元素和下载
            # 优先检测搜索框，处理Cloudflare验证
            # 查找搜索框
            try:
                search_input = None
                search_selectors = [
                    (By.CSS_SELECTOR, 'input[placeholder="Search"]'),
                    (By.CSS_SELECTOR, 'input[type="search"]'),
                    (By.XPATH, '//input[@placeholder="Search"]')
                ]
                for selector_type, selector in search_selectors:
                    try:
                        search_input = self.wait.until(EC.presence_of_element_located((selector_type, selector)))
                        if search_input:
                            print(f"      [ACM] ✅ 找到搜索框: {selector}")
                            break
                    except:
                        continue
                if not search_input:
                    print(
                        "      [Selenium-ACM] 🟡 Search input not found, likely a CAPTCHA. Waiting 10s for manual intervention.")
                    self.driver.implicitly_wait(10)
                    self.driver.refresh()
                    try:
                        for selector_type, selector in search_selectors:
                            try:
                                search_input = self.wait.until(
                                    EC.presence_of_element_located((selector_type, selector)))
                                if search_input:
                                    print(f"      [ACM] ✅ 找到搜索框: {selector}")
                                    break
                            except:
                                continue
                    except TimeoutException:
                        print("      [Selenium-ACM] ❌ Still no search input after waiting. Aborting.")
                        return False

                search_input.clear()
                original_title = f'"{original_title}"'
                search_input.send_keys(original_title)
                # 提交搜索
                try:
                    search_input.send_keys(Keys.RETURN)
                    print("      [ACM] ✅ 已提交搜索请求")
                except:
                    try:
                        # 尝试查找并点击搜索按钮
                        search_button = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                        search_button.click()
                        print("      [ACM] ✅ 已点击搜索按钮")
                    except:
                        print("      [ACM] ❌ 搜索提交失败")
                        return False
                # 等待搜索结果加载
                self.driver.implicitly_wait(5)

                # 检查是否有搜索结果
                no_results = False
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.no-results")))
                    no_results = True
                except:
                    pass
                if no_results:
                    print("      [ACM] ⚠️ 精确搜索没有结果，尝试普通搜索...")
                    # 返回主页重新搜索
                    self.driver.get("https://dl.acm.org/")
                    self.driver.implicitly_wait(3)

                    # 重新查找搜索框
                    for selector_type, selector in search_selectors:
                        try:
                            search_input = self.wait.until(EC.presence_of_element_located((selector_type, selector)))
                            if search_input:
                                break
                        except:
                            continue

                    if search_input:
                        search_input.clear()
                        search_input.send_keys(original_title)  # 不加引号进行普通搜索
                        search_input.send_keys(Keys.RETURN)
                        self.driver.implicitly_wait(3)
                    else:
                        print("      [ACM] ❌ 无法找到搜索框进行普通搜索")
                        return False
                # 查找搜索结果
                result_selectors = [
                    (By.CSS_SELECTOR, ".issue-item__title a"),
                    (By.CSS_SELECTOR, ".issue-item a"),
                    (By.XPATH, "//div[contains(@class, 'issue-item')]//a")
                ]
                result_found = False
                result_link = None
                for selector_type, selector in result_selectors:
                    try:
                        result_link = self.wait.until(EC.presence_of_element_located((selector_type, selector)))
                        if result_link:
                            result_found = True
                            break
                    except:
                        continue
                if not result_found or not result_link:
                    print("      [ACM] ❌ 未找到搜索结果")
                    return False
                # 等待并点击第一个结果中的PDF链接
                # 使用更通用的选择器，不依赖于li的位置，只依赖于aria-label属性
                pdf_button = None
                pdf_selectors = [
                    (By.CSS_SELECTOR, "a[aria-label='PDF']"),
                    (By.CSS_SELECTOR, "a[aria-label='View PDF']"),
                    (By.CSS_SELECTOR, "a.btn.red[href*='pdf']"),
                    (By.XPATH, "//a[contains(text(), 'PDF')]")
                ]
                for selector_type, selector in pdf_selectors:
                    try:
                        pdf_button = self.wait.until(EC.element_to_be_clickable((selector_type, selector)))
                        if pdf_button:
                            print(f"      [ACM] ✅ 找到PDF下载链接: {selector}")
                            break
                    except:
                        continue
                if not pdf_button:
                    print("      [ACM] ❌ 未找到PDF下载链接，可能需要付费访问")
                    return False
                pdf_viewer_url = pdf_button.get_attribute('href')
                if not pdf_viewer_url:
                    print("      [ACM] ❌ 无法获取PDF链接")
                    return False
                self.driver.get(pdf_viewer_url)
                # --- 核心修正: 处理浏览器内置的PDF阅读器 ---
                # 3. 等待浏览器加载完PDF阅读器
                # 我们等待URL包含 '/doi/pdf/' 来确认已进入阅读器页面
                self.wait.until(EC.url_contains("/doi/pdf/"))
                print("      [Selenium-ACM] ✅ PDF viewer page loaded.")
                # 4. 获取当前页面的URL，这就是PDF的直接链接
                final_pdf_url = self.driver.current_url
                # 5. 使用高级JS方法强制浏览器下载PDF
                print("      [Selenium-ACM] 使用增强的JavaScript方法下载PDF...")
                try:
                    # 使用强化版的JavaScript注入，阻止浏览器的默认行为
                    print("      [Selenium-ACM] 使用强化版JavaScript注入...")
                    script = f"""
                        // 创建隐藏的iframe来处理下载
                        var iframe = document.createElement('iframe');
                        iframe.style.display = 'none';
                        document.body.appendChild(iframe);
                        // 在iframe内创建Blob对象
                        var xhr = new XMLHttpRequest();
                        xhr.open('GET', '{final_pdf_url}', true);
                        xhr.responseType = 'blob';
                        xhr.onload = function() {{
                            if (xhr.status === 200) {{
                                // 创建Blob URL
                                var blob = xhr.response;
                                var blobUrl = URL.createObjectURL(blob);

                                // 在iframe中创建下载链接
                                var link = iframe.contentDocument.createElement('a');
                                link.href = blobUrl;
                                link.download = '{os.path.basename(filepath)}';
                                iframe.contentDocument.body.appendChild(link);
                                link.click();

                                // 清理资源
                                setTimeout(function() {{
                                    URL.revokeObjectURL(blobUrl);
                                    document.body.removeChild(iframe);
                                }}, 5000);
                            }}
                        }};
                        xhr.send();
                    """
                    self.driver.execute_script(script)
                    # 等待文件下载完成
                    if self._wait_for_download_and_rename(filepath, timeout=120):
                        return True
                except Exception as e2:
                    print(f"      [Selenium-ACM] ❌ 备用下载方法也失败: {e2}")
                    return False

            except (TimeoutException, NoSuchElementException) as e:
                # 捕获所有查找失败的情况
                print(
                    f"   -> [Strategy: ACM DL (Selector)] 🟡 Could not find required elements. It might be behind a 'Get Access' wall or page structure changed. Error: {e}")
                return False
            except Exception as e:
                print(f"   -> [Strategy: ACM DL (Selector)] ❌ An unexpected error occurred: {e}")
                return False
        except Exception as e:
            print(f"   -> [Strategy: ACM DL (Selector)] ❌ An error occurred while trying to access ACM DL: {e}")
            return False


class IeeeSeleniumDownloader(SeleniumDownloadStrategy):
    """
    [XPath 精确版] 通过 Selenium 从 IEEE Xplore 下载论文。
    """

    def download(self, original_title: str, filepath: str) -> bool:
        print("   -> [Strategy: IEEE Xplore (Selector)] Trying to find and download...")
        try:
            self.driver.get("https://ieeexplore.ieee.org")

            # 使用更健壮的selector，并等待元素可被点击
            """#LayoutWrapper > div > div > div.ng2-app > div > xpl-root > header > xpl-header > div > div.bg-hero-img > div.search-bar-container > xpl-search-bar-migr > div > form > div.search-field > div > div.global-search-bar > xpl-typeahead-migr > div > input"""
            # 查找搜索框 - 使用常见的选择器
            search_selectors = [
                (By.CSS_SELECTOR, 'div.global-search-bar input'),
                (By.CSS_SELECTOR, 'input[type="search"]'),
                (By.XPATH, '//div[contains(@class, "search-bar")]//input')
            ]
            search_box = None
            for selector_type, selector in search_selectors:
                try:
                    search_box = self.wait.until(EC.presence_of_element_located((selector_type, selector)))
                    if search_box:
                        print(f"      [IEEE] ✅ 找到搜索框: {selector}")
                        break
                except:
                    continue
            if not search_box:
                print("      [IEEE] ❌ 无法找到搜索框，尝试刷新页面")
                self.driver.refresh()
                self.driver.implicitly_wait(5)
                # 再次尝试查找
                for selector_type, selector in search_selectors:
                    try:
                        search_box = self.wait.until(EC.presence_of_element_located((selector_type, selector)))
                        if search_box:
                            print(f"      [IEEE] ✅ 刷新后找到搜索框: {selector}")
                            break
                    except:
                        continue
            if not search_box:
                print("      [IEEE] ❌ 多次尝试后仍无法找到搜索框，可能是页面结构变化")
                return False

            try:
                search_box.clear()
                search_box.send_keys(original_title)
                self.driver.implicitly_wait(1)
                print("      [IEEE] ✅ 已输入搜索内容")
            except Exception as e:
                print(f"      [IEEE] ❌ 无法输入搜索内容: {e}")
                return False

            # 查找搜索按钮
            search_button = None
            button_selectors = [
                (By.CSS_SELECTOR, 'div.search-icon button'),
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, '//div[contains(@class, "search-icon")]//button'),
                (By.XPATH, '//button[contains(text(), "Search")]')
            ]
            for selector_type, selector in button_selectors:
                try:
                    search_button = self.wait.until(EC.element_to_be_clickable((selector_type, selector)))
                    if search_button:
                        print(f"      [IEEE] ✅ 找到搜索按钮: {selector}")
                        break
                except:
                    continue
            if search_button:
                try:
                    search_button.click()
                    print("      [IEEE] ✅ 已点击搜索按钮")
                except Exception as e:
                    print(f"      [IEEE] ⚠️ 无法点击搜索按钮: {e}")
                    # 备用方案：使用回车键
                    try:
                        search_box.send_keys(Keys.RETURN)
                        print("      [IEEE] ✅ 使用回车键提交搜索")
                    except:
                        print("      [IEEE] ❌ 搜索提交失败")
                        return False
            else:
                # 如果找不到按钮，使用回车键
                try:
                    search_box.send_keys(Keys.RETURN)
                    print("      [IEEE] ✅ 使用回车键提交搜索")
                except:
                    print("      [IEEE] ❌ 无法提交搜索")
                    return False

            self.driver.implicitly_wait(5)  # 等待搜索结果加载
            print("      [IEEE] 等待搜索结果加载完成...")
            # 通用 XPath，用于定位第一个结果中的PDF链接
            # 查找PDF下载链接
            pdf_button = None
            pdf_selectors = [
                (By.XPATH, '(//xpl-results-item//a[contains(@href, "stamp.jsp")])[1]'),
                (By.CSS_SELECTOR, 'a[href*="stamp.jsp"]'),
                (By.CSS_SELECTOR, '.pdf-btn-container a')
            ]
            for selector_type, selector in pdf_selectors:
                try:
                    pdf_button = self.wait.until(EC.element_to_be_clickable((selector_type, selector)))
                    if pdf_button:
                        print(f"      [IEEE] ✅ 找到PDF下载链接: {selector}")
                        break
                except:
                    continue
            print("      [Selenium-IEEE] ✅ Found PDF button via generic XPath, clicking to download...")

            if not pdf_button:
                print("      [IEEE] ❌ 未找到PDF下载链接，可能没有搜索结果或需要付费访问")
                return False
            # 获取PDF链接但先不点击
            # 获取PDF链接
            pdf_viewer_url = pdf_button.get_attribute('href')
            if not pdf_viewer_url:
                print("      [IEEE] ❌ PDF链接获取失败")
                return False

            print(f"      [IEEE] 获取到PDF链接: {pdf_viewer_url}")

            # 访问PDF链接
            self.driver.get(pdf_viewer_url)

            # 等待PDF页面加载完成
            self.driver.implicitly_wait(3)

            # 检查当前页面是否真的是PDF预览页面或者是错误页面
            page_title = self.driver.title.lower()
            page_source_snippet = self.driver.page_source[:500].lower()

            # 检查是否遇到了登录页面或错误页面
            if any(keyword in page_title for keyword in ['login', 'sign in', 'access denied', 'error']):
                print(f"      [IEEE] ❌ 检测到登录或错误页面，页面标题: {self.driver.title}")
                return False

            if any(keyword in page_source_snippet for keyword in
                   ['login', 'sign in', 'access denied', 'subscription required']):
                print("      [IEEE] ❌ 检测到访问限制页面")
                return False

            # 尝试使用键盘快捷键下载PDF
            print("      [IEEE] 尝试使用键盘快捷键下载PDF...")
            success = self._try_keyboard_download(filepath)
            if success:
                return True

            # 最后尝试右键菜单下载
            success = self._try_context_menu_download(filepath)
            if success:
                return True

            print("      [IEEE] ❌ 所有下载方法都失败")
            return False

        except TimeoutException:
            print(
                "   -> [Strategy: IEEE Xplore (Selector)] 🟡 Timed out waiting for elements. Check for CAPTCHA or login.")
            return False
        except Exception as e:
            print(f"   -> [Strategy: IEEE Xplore (Selector)] ❌ An error occurred: {e}")
            return False

    def _try_keyboard_download(self, filepath: str) -> bool:
        """尝试使用键盘快捷键下载PDF"""
        print("      [IEEE] 尝试键盘快捷键下载方法...")

        try:
            # 确保页面获得焦点
            self.driver.execute_script("window.focus();")

            # 等待页面完全加载
            self.driver.implicitly_wait(3)

            # 方法1: 使用ActionChains发送Ctrl+S
            actions = ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys('s').key_up(Keys.CONTROL).perform()
            print("      [IEEE] 已发送Ctrl+S快捷键")

            # 等待下载对话框出现并处理
            self.driver.implicitly_wait(2)

            # 尝试发送Enter键确认下载（如果有保存对话框）
            actions.send_keys(Keys.RETURN).perform()
            print("      [IEEE] 已发送Enter键确认")

            # 等待下载完成
            if self._wait_for_download_and_rename(filepath, timeout=60):
                return True

            # 方法2: 如果Ctrl+S不行，尝试使用JavaScript触发下载
            print("      [IEEE] 尝试JavaScript触发保存...")
            self.driver.execute_script("""
                // 尝试触发浏览器的保存功能
                if (window.print) {
                    // 有些情况下print对话框也能触发保存
                    setTimeout(function() {
                        window.print();
                    }, 1000);
                }

                // 尝试创建键盘事件
                var event = new KeyboardEvent('keydown', {
                    key: 's',
                    ctrlKey: true,
                    bubbles: true
                });
                document.dispatchEvent(event);
            """)

            self.driver.implicitly_wait(3)
            if self._wait_for_download_and_rename(filepath, timeout=60):
                return True

        except Exception as e:
            print(f"      [IEEE] 键盘下载方法失败: {e}")

        return False

    def _try_context_menu_download(self, filepath: str) -> bool:
        """尝试使用右键菜单下载"""
        print("      [IEEE] 尝试右键菜单下载方法...")

        try:
            # 在页面中央右键点击
            actions = ActionChains(self.driver)

            # 获取页面中心位置
            body = self.driver.find_element(By.TAG_NAME, "body")
            actions.move_to_element(body).context_click().perform()
            print("      [IEEE] 已右键点击页面")

            self.driver.implicitly_wait(1)

            # 尝试发送按键选择"另存为"选项
            # 在大多数浏览器中，"另存为"通常是右键菜单的第一个或第二个选项
            actions.send_keys('a').perform()  # 通常'a'键对应"另存为"

            self.driver.implicitly_wait(2)

            # 发送Enter确认
            actions.send_keys(Keys.RETURN).perform()

            # 等待下载完成
            if self._wait_for_download_and_rename(filepath, timeout=60):
                return True

        except Exception as e:
            print(f"      [IEEE] 右键菜单下载失败: {e}")

        return False
