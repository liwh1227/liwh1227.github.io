"""Add a compact reading estimate to articles without changing their titles."""

import math
import re
from html.parser import HTMLParser


class _ReadableText(HTMLParser):
    """Collect rendered prose while excluding block code and executable content."""

    _excluded_tags = {"pre", "script", "style"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.excluded_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._excluded_tags:
            self.excluded_depth += 1

    def handle_endtag(self, tag):
        if tag in self._excluded_tags:
            self.excluded_depth = max(0, self.excluded_depth - 1)

    def handle_data(self, data):
        if not self.excluded_depth:
            self.parts.append(data)


def on_page_content(html, page, config, files):
    # Profile and navigation pages are not articles.
    if not page.file.src_uri.startswith("posts/"):
        return html

    # HTML parsing preserves escaped comparisons such as <100µs. Regex-based
    # tag removal on Markdown can otherwise swallow prose up to a later >.
    parser = _ReadableText()
    parser.feed(html)
    parser.close()
    text = " ".join(parser.parts)
    text = re.sub(r"https?://\S+", "", text)
    total_count = len(re.findall(r"[\u4e00-\u9fff]", text)) + len(
        re.findall(r"\b[a-zA-Z]+\b", text)
    )
    reading_time = max(1, math.ceil(total_count / 400))
    stats = (
        '<p class="reading-meta" aria-label="阅读信息">'
        f"约 {total_count:,} 字 · {reading_time} 分钟阅读</p>"
    )

    # Insert after the rendered heading, so Markdown title detection is intact.
    heading = re.search(r"<h1\b[^>]*>.*?</h1>", html, flags=re.DOTALL)
    if heading:
        return html[: heading.end()] + "\n" + stats + html[heading.end() :]

    # Material renders the page title above content when Markdown has no H1.
    return stats + "\n" + html
