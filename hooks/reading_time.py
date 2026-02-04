import re

def on_page_markdown(markdown, page, config, files):
    # 排除不需要添加统计的页面，例如首页 index.md
    if page.url == "" or page.url == "index.html":
        return markdown

    # 1. 计算字数 (Word Count)
    # 过滤掉 HTML 标签和 Markdown 符号，只统计纯文本
    # 这是一个粗略的估算，对于博客足够了
    text = re.sub(r'<[^>]*>', '', markdown)
    text = re.sub(r'[#*`~\[\]\(\)]', '', text)
    # 简单的字数统计：中文字符数 + 英文单词数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', text))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
    total_count = chinese_chars + english_words

    # 2. 计算预计阅读时间 (Estimated Time)
    # 假设中文阅读速度为 300-500 字/分钟，取 400
    # 英文阅读速度为 200 词/分钟
    # 这里为了简化，统一按 400 字/分钟计算，不足1分钟按1分钟计
    reading_time = round(total_count / 400)
    if reading_time < 1:
        reading_time = 1

    # 3. 构造要插入的 HTML/Markdown
    # 使用 Admonition (警告框) 样式，或者普通的斜体字
    # 这里演示插入一段灰色的元数据文本
    stats_text = f"\n<span style='color:gray; font-size:0.9em;'>📄 本文共 {total_count} 字，预计阅读 {reading_time} 分钟</span>\n\n"

    # 或者如果你喜欢 Material 的 Admonition 风格，可以用这个：
    # stats_text = f'\n!!! info "阅读指南"\n    本文共 {total_count} 字，预计阅读 {reading_time} 分钟\n\n'

    # 4. 插入到文章开头 (如果有 YAML Frontmatter，插在它之后)
    return stats_text + markdown