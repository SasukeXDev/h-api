# HLS Extractor Flask App

Production-ready Flask app that extracts HLS (`.m3u8`) manifest links from a video page URL and provides an in-browser HLS player.

## Routes

- `/` Home page with URL input form
- `/extract` Extract manifests and stream variants
- `/player?manifest=<m3u8_url>` Play stream with HLS.js
- `/admin` Basic service health info

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

The app binds to `0.0.0.0` and uses `PORT` from environment (default `5000`).

## Production start command

```bash
gunicorn app:app
```

Works for Render, Railway, Docker, and VPS deployments.
