import asyncio
from backend.app.services.web_tools.url_reader import extract_urls_from_text, fetch_multiple_urls

async def test():
    urls = extract_urls_from_text("Tolong jelaskan repo ini: https://github.com/baidu/Unlimited-OCR")
    print("Found URLs:", urls)
    content = await fetch_multiple_urls(urls)
    print("Content preview:")
    print(content[:500] if content else "NO CONTENT")

if __name__ == "__main__":
    asyncio.run(test())
