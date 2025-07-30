# Paper Crawler

## 项目概述

Paper Crawler 是一个学术论文下载工具，支持从多个来源（如 arXiv、CORE、AAAI、NeurIPS、CVF、ACM、IEEE）自动下载 PDF 文件。它使用策略模式来处理不同平台的下载逻辑，支持 httpx 和 Selenium 两种方式。

## 项目结构

- **chromedriver.exe** 和 **undetected_chromedriver.exe**: Selenium 驱动程序，用于浏览器自动化。
- **downloaded_papers/**: 下载的 PDF 文件存储目录。
- **LICENSE**: 项目许可证文件。
- **main.py**: 项目入口点，演示如何使用 PaperCrawler 下载论文。
- **paper_crawler.py**: 核心爬虫类，管理下载过程和策略调度。
- **requirements.txt**: 项目依赖列表。
- **strategies/**:
  - **__init__.py**: 包初始化文件。
  - **download_strategy.py**: 下载策略的抽象基类。
  - **implementations.py**: 基于 httpx 的具体下载实现（arXiv、CORE、AAAI、NeurIPS、CVF）。
  - **selenium_implementations.py**: 基于 Selenium 的下载实现（ACM、IEEE）。

## 核心代码介绍

### main.py
这是项目的主入口，实例化 `PaperCrawler` 并下载指定论文。示例：
```python
crawler = PaperCrawler(save_dir="downloaded_papers")
crawler.setup_driver()  # 初始化 Selenium 驱动
crawler.download_paper(title="论文标题", conference="会议名称")
crawler.teardown_driver()  # 关闭驱动
```

### paper_crawler.py
核心类 `PaperCrawler`：
- 初始化保存目录和 CORE API 密钥。
- `setup_driver()`: 配置反检测的 Selenium 驱动。
- `download_paper()`: 根据会议映射选择下载策略，尝试多种来源。
- 支持的会议映射：S&P/Oakland -> IEEE, CCS/WWW -> ACM, AAAI/NeurIPS/CVPR/ICCV -> 特定下载器。

### strategies 目录
- **download_strategy.py**: 定义抽象基类 `DownloadStrategy`，子类实现 `download()` 方法。
- **implementations.py**: httpx 实现的下载器，使用 API 或网页抓取下载 PDF。
- **selenium_implementations.py**: Selenium 实现的下载器，处理需要浏览器交互的平台，如 ACM 和 IEEE。

## 如何部署和使用

### 环境要求
- Python 3.8+
- Chrome 浏览器版本指定为117

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置
- 在 `paper_crawler.py` 中替换 `CORE_API_KEY = "Your CORE KEY"` 为你的 CORE API 密钥（从 [CORE](https://core.ac.uk/) 获取）。
- 确保 `chromedriver.exe` 和 `undetected_chromedriver.exe` 在项目根目录。

### 运行
1. 编辑 `main.py` 中的 `papers_to_download` 列表，添加论文标题和会议（可选）。
2. 运行：
   ```bash
   python main.py
   ```
3. Selenium 会打开浏览器，可能需要手动处理登录或 CAPTCHA。

### 注意事项
- 对于 ACM 和 IEEE，可能需要账号访问。
- 下载过程异步，支持延迟以避免 IP 封禁。
- 如果下载失败，会尝试后备策略（如 arXiv、CORE）。

## 许可证
Apache License (详见 LICENSE 文件)。 
