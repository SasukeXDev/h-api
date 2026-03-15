import os
import re
from typing import List, Dict, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request

REQUEST_TIMEOUT = 12
M3U8_QUOTED_REGEX = re.compile(r"['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", re.IGNORECASE)
M3U8_DIRECT_REGEX = re.compile(r"https?://[^\s'\"<>]+\.m3u8[^\s'\"<>]*", re.IGNORECASE)

app = Flask(__name__)


class ExtractionError(Exception):
    """Raised when manifest extraction cannot proceed."""


def is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def fetch_text(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def discover_m3u8_urls(page_html: str, page_url: str) -> List[str]:
    found = set()

    for candidate in M3U8_DIRECT_REGEX.findall(page_html):
        found.add(candidate.strip())

    for match in M3U8_QUOTED_REGEX.findall(page_html):
        found.add(urljoin(page_url, match.strip()))

    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all(src=True):
        src = tag.get("src", "").strip()
        if ".m3u8" in src.lower():
            found.add(urljoin(page_url, src))

    return sorted(found)


def parse_master_playlist(playlist_text: str, playlist_url: str) -> Tuple[bool, List[Dict[str, str]]]:
    lines = [line.strip() for line in playlist_text.splitlines() if line.strip()]
    is_master = any(line.startswith("#EXT-X-STREAM-INF") for line in lines)

    if not is_master:
        return False, [{"quality": "Auto", "url": playlist_url}]

    streams = []
    for idx, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue

        attrs = line.split(":", 1)[1] if ":" in line else ""
        resolution_match = re.search(r"RESOLUTION=(\d+)x(\d+)", attrs)
        bandwidth_match = re.search(r"BANDWIDTH=(\d+)", attrs)

        quality = "Unknown"
        if resolution_match:
            quality = f"{resolution_match.group(2)}p"
        elif bandwidth_match:
            kbps = int(bandwidth_match.group(1)) // 1000
            quality = f"{kbps} kbps"

        stream_url = None
        for next_line in lines[idx + 1 :]:
            if next_line.startswith("#"):
                continue
            stream_url = urljoin(playlist_url, next_line)
            break

        if stream_url:
            streams.append({"quality": quality, "url": stream_url})

    deduped = []
    seen = set()
    for stream in streams:
        if stream["url"] in seen:
            continue
        seen.add(stream["url"])
        deduped.append(stream)

    return True, deduped


def extract_video_data(video_page_url: str) -> Dict[str, object]:
    if not is_valid_http_url(video_page_url):
        raise ExtractionError("Please enter a valid http(s) URL.")

    try:
        page_html = fetch_text(video_page_url)
    except requests.Timeout as exc:
        raise ExtractionError("Request timed out while fetching the target page.") from exc
    except requests.RequestException as exc:
        raise ExtractionError(f"Unable to fetch target page: {exc}") from exc

    manifests = discover_m3u8_urls(page_html, video_page_url)
    if not manifests:
        raise ExtractionError("No .m3u8 manifest links were found on the page.")

    selected_manifest = manifests[0]

    try:
        manifest_text = fetch_text(selected_manifest)
    except requests.Timeout as exc:
        raise ExtractionError("Request timed out while fetching the manifest.") from exc
    except requests.RequestException as exc:
        raise ExtractionError(f"Unable to fetch manifest: {exc}") from exc

    is_master, streams = parse_master_playlist(manifest_text, selected_manifest)
    if not streams:
        streams = [{"quality": "Auto", "url": selected_manifest}]

    return {
        "page_url": video_page_url,
        "found_manifests": manifests,
        "master_playlist": selected_manifest if is_master else None,
        "selected_manifest": selected_manifest,
        "streams": streams,
    }


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/extract")
def extract():
    video_url = (request.form.get("video_url") or "").strip()

    try:
        data = extract_video_data(video_url)
        return render_template("result.html", data=data, error=None)
    except ExtractionError as exc:
        return render_template("result.html", data=None, error=str(exc)), 400
    except Exception:
        return render_template(
            "result.html",
            data=None,
            error="Unexpected server error while processing the URL.",
        ), 500


@app.get("/player")
def player():
    manifest_url = (request.args.get("manifest") or "").strip()

    if not is_valid_http_url(manifest_url):
        return render_template("player.html", error="Invalid or missing manifest URL.", player_data=None), 400

    try:
        manifest_text = fetch_text(manifest_url)
        _, streams = parse_master_playlist(manifest_text, manifest_url)
    except requests.RequestException as exc:
        return render_template("player.html", error=f"Failed to load manifest: {exc}", player_data=None), 400
    except Exception:
        return render_template("player.html", error="Failed to initialize player.", player_data=None), 500

    player_data = {
        "manifest": manifest_url,
        "streams": streams,
    }
    return render_template("player.html", error=None, player_data=player_data)


@app.get("/admin")
def admin():
    return {
        "status": "ok",
        "service": "hls-extractor",
        "environment_port": os.getenv("PORT", "5000"),
    }


@app.errorhandler(404)
def not_found(_err):
    return render_template("result.html", data=None, error="Page not found."), 404


@app.errorhandler(500)
def internal_error(_err):
    return render_template("result.html", data=None, error="Internal server error."), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
