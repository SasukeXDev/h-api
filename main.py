from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

from extractor import (
    extract_m3u8_from_page,
    download_m3u8,
    extract_streams_from_m3u8
)

app = FastAPI(title="Video Manifest Extractor API")


class PageRequest(BaseModel):
    url: str


@app.post("/extract")
async def extract_video_links(data: PageRequest):
    manifests = await extract_m3u8_from_page(data.url)

    if not manifests:
        raise HTTPException(status_code=404, detail="No manifest found")

    m3u8_url = manifests[0]
    m3u8_file = download_m3u8(m3u8_url)
    streams = extract_streams_from_m3u8(m3u8_file)

    return {
        "page_url": data.url,
        "manifest_url": m3u8_url,
        "streams": streams,
        "total_streams": len(streams)
    }
