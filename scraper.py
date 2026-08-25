"""
Akakçe TP-Link 价格抓取脚本
=============================
使用 Playwright(真实浏览器渲染)抓取 Akakçe 上 TP-Link 各类别产品的最低价信息,
写入 data/latest.json(当前快照)和 data/history.jsonl(历史记录,每行一条)。

用法(本地测试):
    pip install -r requirements.txt
    playwright install chromium
    python scraper.py

在 GitHub Actions 中会被定时(默认每小时)自动调用一次。

⚠️ 重要提示:
Akakçe 有反爬虫检测。本脚本已尽量模拟真实浏览器行为(User-Agent、等待渲染等),
但网站可能随时调整反爬策略或页面结构(class 名称等),届时需要:
  1. 打开浏览器开发者工具(F12),查看 akakce.com 页面实际的产品列表 HTML 结构
  2. 根据实际结构调整下面 extract_products() 函数里的选择器 / 正则

如果长期被拦截,请改用人工触发方式(直接在对话里让 Claude 帮你查询)。
"""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# 1. 要追踪的 TP-Link 产品类别页面
#    key: 类别中文名, value: Akakçe 分类页 URL
# ---------------------------------------------------------------------------
CATEGORIES = {
    "路由器 Router": "https://www.akakce.com/router/tp-link.html",
    "摄像头 Kamera": "https://www.akakce.com/guvenlik-kamerasi/tp-link.html",
    "智能插座 Akıllı Priz": "https://www.akakce.com/akilli-priz/tp-link.html",
    "智能灯泡 Ampul": "https://www.akakce.com/ampul/tp-link.html",
    "交换机 Switch": "https://www.akakce.com/switch/tp-link.html",
    "无线网卡 Kablosuz Ağ Adaptörü": "https://www.akakce.com/kablosuz-ag-adaptoru/tp-link.html",
    "以太网卡 Ethernet Kartı": "https://www.akakce.com/ethernet-karti/tp-link.html",
    "智能家居系统 Akıllı Ev Sistemleri": "https://akakce.com/akilli-ev-sistemleri/tp-link.html",
}

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DEBUG_DIR = Path(__file__).parent / "debug"
DEBUG_DIR.mkdir(exist_ok=True)

PRICE_RE = re.compile(r"([\d.]+,\d{2})\s*TL")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def fetch_category(page, name: str, url: str, debug: bool = False) -> list[dict]:
    """打开一个分类页面并提取产品名称 + 最低价格。"""
    products = []
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        # 等待产品列表渲染(Akakçe 是 SPA 式渲染,需要多等一会)
        await page.wait_for_timeout(2500)

        # 尝试常见的产品条目容器,失败则退回到整页文本正则提取
        html = await page.content()

        if debug:
            # 保存调试用的截图和 HTML 源码,方便人工排查页面实际结构
            safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
            await page.screenshot(
                path=str(DEBUG_DIR / f"{safe_name}.png"), full_page=True
            )
            (DEBUG_DIR / f"{safe_name}.html").write_text(html, encoding="utf-8")
            title = await page.title()
            print(f"  [调试] 页面标题: {title}")
            print(f"  [调试] HTML 长度: {len(html)} 字符")
            print(f"  [调试] 页面中 'TL' 出现次数: {html.count('TL')}")
            print(f"  [调试] 已保存截图/源码到 debug/{safe_name}.png / .html")

        # ---- 方案 A:尝试用结构化选择器(可能需要根据实际页面调整)----
        items = await page.query_selector_all("li.js-list-item, li[data-id], article")
        if items:
            for item in items:
                text = (await item.inner_text()).strip()
                if not text:
                    continue
                m = PRICE_RE.search(text)
                if not m:
                    continue
                # 取第一行非空文本作为产品名
                name_line = next(
                    (l.strip() for l in text.split("\n") if l.strip()), ""
                )
                products.append(
                    {
                        "name": name_line[:150],
                        "price_text": m.group(0),
                    }
                )

        # ---- 方案 B(兜底):整页正则扫描 "产品名 ... 价格 TL" 模式 ----
        if not products:
            # 粗略地把价格和它前面的一小段文本配对
            for m in PRICE_RE.finditer(html):
                start = max(0, m.start() - 120)
                snippet = re.sub(r"<[^>]+>", " ", html[start : m.start()])
                snippet = re.sub(r"\s+", " ", snippet).strip()
                if snippet:
                    products.append(
                        {"name": snippet[-100:], "price_text": m.group(0)}
                    )

        # 去重(按名称+价格)
        seen = set()
        deduped = []
        for p in products:
            key = (p["name"], p["price_text"])
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        products = deduped[:100]  # 每个类别最多保留100条,避免噪音过多

    except Exception as e:
        print(f"[警告] 抓取 {name} 失败: {e}", file=sys.stderr)

    return products


async def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    result = {"timestamp": timestamp, "categories": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="tr-TR",
            viewport={"width": 1366, "height": 900},
        )
        page = await context.new_page()

        first = True
        for name, url in CATEGORIES.items():
            print(f"正在抓取: {name} -> {url}")
            # 只对第一个类别开启调试(截图+保存HTML),避免产生太多调试文件
            products = await fetch_category(page, name, url, debug=first)
            first = False
            print(f"  找到 {len(products)} 条价格信息")
            result["categories"][name] = {
                "url": url,
                "product_count": len(products),
                "products": products,
            }
            await page.wait_for_timeout(1500)  # 类别之间稍作停顿,降低风控概率

        await browser.close()

    # 写入最新快照(供网页展示读取)
    latest_path = DATA_DIR / "latest.json"
    latest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 追加历史记录(每行一个 JSON,便于以后画价格趋势图)
    history_path = DATA_DIR / "history.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"完成,数据已写入 {latest_path}")


if __name__ == "__main__":
    asyncio.run(main())
