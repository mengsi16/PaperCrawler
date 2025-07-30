from paper_crawler import PaperCrawler


def main():
    """主执行函数，用于启动论文下载过程。"""

    SAVE_DIRECTORY = "downloaded_papers"
    crawler = PaperCrawler(save_dir=SAVE_DIRECTORY)

    # 演示如何通过会议名称自动选择下载策略
    papers_to_download = [
        {
            "title": "ET-BERT: A Contextualized Datagram Representation with Pre-training Transformers for Encrypted Traffic Classification",
            "conference": "WWW",
        },
        # # 2. CCS 会议 -> 映射到 'acm' -> 优先使用 AcmDlSeleniumDownloader
        # {
        #     "title": "Accurate and Efficient Recurring Vulnerability Detection for IoT Firmware",
        #     "conference": "CCS",
        # },
        # # 3. AAAI 会议 -> 映射到 'aaai' -> 使用特定的 AaaiOjsDownloader
        # {
        #     "title": "Zero-Shot Complex Question-Answering on Long Scientific Documents",
        #     "conference": "AAAI"
        # },
        # # 4. 未指定会议 -> 触发“全家桶”模式 (ACM -> IEEE -> Arxiv -> CORE)
        # {
        #     "title": "LRM: Large Reconstruction Model for Single Image to 3D",
        #     "conference": "ICLR",  # ICLR下载器已移除，将测试备选方案
        # },
        {
            "title": "TrafficFormer An Efficient Pre-trained Model for Traffic Data",
            "conference": "S&P",
        },
        # {
        #     "title": "ET-BERT: A Contextualized Datagram Representation with Pre-training Transformers for Encrypted Traffic Classification",
        #     "conference": None,  # 无特定会议
        # }
    ]

    print("=============================================")
    print("  Academic Paper Downloader (Conference Map) ")
    print("=============================================")

    # 1. 在所有任务开始前，手动启动浏览器
    crawler.setup_driver()

    # 2. 循环处理每一篇论文
    for paper in papers_to_download:
        crawler.download_paper(
            title=paper["title"],
            conference=paper.get("conference")
        )

    # 3. 所有任务结束后，手动关闭浏览器
    crawler.teardown_driver()

    print("\n================= All Done =================")


if __name__ == "__main__":
    main()
