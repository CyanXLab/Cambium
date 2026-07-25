---
name: web-search
description: 当用户需要搜索互联网、获取最新信息、查询不确定的事实、或需要外部数据时使用此技能。触发词：搜索、查一下、最新、最近、现在、上网找。
---

调用 web_search 工具（由 open-webSearch MCP 提供）进行网络搜索。工具参数：query（搜索关键词）、limit（结果数，默认5）。返回结果包含标题和摘要。如果搜索结果不够，可以再用 fetchWebContent 工具获取页面全文。
