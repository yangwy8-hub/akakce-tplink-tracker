# Akakçe TP-Link 价格追踪器

每小时自动抓取 Akakçe.com 上 TP-Link 全部类别(路由器、摄像头、智能插座、
灯泡、交换机、无线网卡、以太网卡、智能家居系统)的价格,并生成一个可访问的
网页面板。

## 部署步骤(全程免费,约 10 分钟)

### 1. 创建 GitHub 仓库
1. 打开 https://github.com/new
2. 仓库名随意,例如 `akakce-tplink-tracker`
3. 设为 Public(GitHub Pages 免费版需要公开仓库)
4. 创建完成

### 2. 上传本项目的所有文件
把这个文件夹里的所有文件(包括隐藏的 `.github` 文件夹)上传到你刚创建的仓库,
保持目录结构不变:

```
你的仓库/
├── .github/workflows/scrape.yml
├── data/latest.json
├── scraper.py
├── requirements.txt
├── index.html
└── README.md
```

最简单的方式:在仓库页面点击 "Add file" → "Upload files",把文件夹内容拖进去。
（`.github` 文件夹需要单独拖入，GitHub 网页上传支持保留文件夹结构）

### 3. 开启 GitHub Pages
1. 进入仓库的 Settings → Pages
2. Source 选择 "Deploy from a branch"
3. Branch 选择 `main`,文件夹选择 `/ (root)`
4. 保存后,几分钟内会得到一个网址,形如:
   `https://你的用户名.github.io/akakce-tplink-tracker/`
   **这就是你要的、可以定时更新的网址。**

### 4. 手动触发一次抓取(验证是否正常工作)
1. 进入仓库的 Actions 标签
2. 左侧选择 "定时抓取 Akakçe TP-Link 价格"
3. 点击右侧 "Run workflow" 手动跑一次
4. 等待 1-3 分钟,跑完后刷新第 3 步得到的网址,应该能看到价格数据

之后它会**每小时自动运行一次**（cron 表达式 `5 * * * *`，即每小时第5分钟），
无需你再手动操作。

## 如果抓取失败 / 数据为空

Akakçe 有反爬虫机制，如果某类别显示"本次未抓取到数据"：

1. 打开 Actions 里对应那次运行的日志，看具体报错
2. 用浏览器打开对应的 Akakçe 分类页，按 F12 打开开发者工具，查看产品列表实际
   使用的 HTML class 名称
3. 打开 `scraper.py`，找到 `extract_products` 里的这一行，把选择器换成你在
   开发者工具里看到的实际 class：
   ```python
   items = await page.query_selector_all("li.js-list-item, li[data-id], article")
   ```
4. 提交修改，重新手动触发一次 Actions 测试

如果长期被彻底封锁抓不到任何数据，建议改用付费抓取 API（如 ScraperAPI /
Bright Data / ScrapingBee），或退回人工触发方式（直接在对话里问 Claude 要
最新价格，Claude 用搜索引擎获取，不受此反爬限制）。

## 文件说明

| 文件 | 作用 |
|---|---|
| `scraper.py` | 核心抓取脚本 |
| `.github/workflows/scrape.yml` | 定时任务配置(每小时自动运行) |
| `data/latest.json` | 最新一次抓取结果(网页读取这个文件) |
| `data/history.jsonl` | 历史记录,每行一条 JSON,可用来后续做价格趋势图 |
| `index.html` | 展示页面(部署为 GitHub Pages 后即可访问) |
