from app.services.crawler import CrawlResult, merge_crawl_parse, parse_page


def test_parse_page_extracts_meta_and_colors():
    html = """
    <html><head><title>Acme Co</title>
    <meta name="keywords" content="seo, marketing, ai">
    <style>body{color:#112233}</style></head>
    <body><h1>Hello</h1><button class="cta">Get started</button>
    <a href="https://twitter.com/acme">x</a></body></html>
    """
    p = parse_page("https://acme.test", html)
    assert "seo" in p["keyword_seeds"]
    assert p["colors"]["primary"].startswith("#")
    assert p["cta_candidates"]


def test_merge_crawl_dedupes_keywords():
    c = CrawlResult(url="https://x.com")
    c.html_pages["https://x.com"] = "<html><body><h1>One</h1><h1>One</h1></body></html>"
    m = merge_crawl_parse(c)
    assert m["aggregate"]["headings"].count("One") == 1
