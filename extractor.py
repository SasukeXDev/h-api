import asyncio
import re
import requests
import os
from playwright.async_api import async_playwright

M3U8_REGEX = r"https?://.*?\.m3u8.*"

async def extract_m3u8_from_page(url):
    found = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        page.on(
            "request",
            lambda r: found.append(r.url)
            if re.search(M3U8_REGEX, r.url)
            else None
        )

        await page.goto(url, timeout=60000)
        await asyncio.sleep(3)

        # Try clicking play
        try:
            await page.click("video", timeout=8000)
        except:
            pass

        await asyncio.sleep(8)
        await browser.close()

    return list(set(found))


def download_m3u8(m3u8_url):
    os.makedirs("manifests", exist_ok=True)
    filename = "manifests/stream.m3u8"

    r = requests.get(m3u8_url, timeout=20)
    r.raise_for_status()

    with open(filename, "w", encoding="utf-8") as f:
        f.write(r.text)

    return filename


def extract_streams_from_m3u8(path):
    streams = []

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                streams.append(line)

    return streams
