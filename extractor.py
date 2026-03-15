import asyncio
import os
import re
from urllib.parse import urljoin

import requests
from playwright.async_api import async_playwright

M3U8_REGEX = re.compile(r"https?://[^\s\"'<>]+\.m3u8(?:[^\s\"'<>]*)?", re.IGNORECASE)


def _normalize_m3u8_url(candidate):
    """Strip common trailing punctuation captured from HTML/script content."""
    return candidate.rstrip("'\"),;]")

async def extract_m3u8_from_page(url):
    found = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        page.on(
            "request",
            lambda r: found.add(r.url)
            if M3U8_REGEX.search(r.url)
            else None
        )
        page.on(
            "response",
            lambda r: found.add(r.url)
            if M3U8_REGEX.search(r.url)
            else None
        )

        await page.goto(url, timeout=60000, wait_until="networkidle")
        await asyncio.sleep(3)

        # Try clicking play
        try:
            await page.click("video", timeout=8000)
        except:
            pass

        await asyncio.sleep(8)

        # Some players inject the manifest URL into page scripts or inline data.
        content = await page.content()
        found.update(_normalize_m3u8_url(item) for item in M3U8_REGEX.findall(content))

        await browser.close()

    return sorted(found)


def download_m3u8(m3u8_url):
    os.makedirs("manifests", exist_ok=True)
    filename = "manifests/stream.m3u8"

    r = requests.get(
        m3u8_url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*",
        },
    )
    r.raise_for_status()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(r.text)

    return filename


def extract_streams_from_m3u8(path, manifest_url):
    streams = []
    seen = set()

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                absolute_url = urljoin(manifest_url, line)
                if absolute_url not in seen:
                    seen.add(absolute_url)
                    streams.append(absolute_url)

    return streams
