"""Latest Fantasy Footballers episode summary and YouTube captions when published."""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

EPISODES_URL = "https://www.thefantasyfootballers.com/episodes/"
USER_AGENT = "Mozilla/5.0 (compatible; fantasy-draft-tool-espn-mcp)"
TRANSCRIPT_LIMIT = 12_000

_EPISODE_HREF = re.compile(
    r'href="(https://www\.thefantasyfootballers\.com/episodes/[^"#]+/)"'
)
_YOUTUBE_ID = re.compile(r"img\.youtube\.com/vi/([A-Za-z0-9_-]{6,})")
_TIMEDTEXT = re.compile(r"https://www\.youtube\.com/api/timedtext[^\"'\s<]+")
_CAPTION_TEXT = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)


def _meta(page: str, prop: str) -> str | None:
    match = re.search(rf'property="{re.escape(prop)}" content="([^"]*)"', page)
    if not match:
        return None
    return html.unescape(match.group(1))


def latest_episode_url(index_html: str) -> str | None:
    match = _EPISODE_HREF.search(index_html)
    return match.group(1) if match else None


def youtube_id_from_html(page: str) -> str | None:
    match = _YOUTUBE_ID.search(page)
    return match.group(1) if match else None


def parse_episode_page(page: str, url: str) -> dict[str, Any]:
    return {
        "title": _meta(page, "og:title"),
        "summary": _meta(page, "og:description"),
        "published": _meta(page, "article:published_time"),
        "url": _meta(page, "og:url") or url,
        "youtube_id": youtube_id_from_html(page),
    }


def caption_url_from_watch_html(page: str) -> str | None:
    match = _TIMEDTEXT.search(page)
    if not match:
        return None
    return html.unescape(match.group(0).replace("\\u0026", "&").replace("\\/", "/"))


def captions_to_text(xml: str) -> str:
    parts = [html.unescape(re.sub(r"<[^>]+>", "", chunk)) for chunk in _CAPTION_TEXT.findall(xml)]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


async def _get_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    return response.text


async def latest_episode() -> dict[str, Any]:
    """Fetch the newest episode page and captions when YouTube exposes them."""
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        index_html = await _get_text(client, EPISODES_URL)
        episode_url = latest_episode_url(index_html)
        if not episode_url:
            return {"error": "No episode link found on the Footballers episodes page."}
        page = await _get_text(client, episode_url)
        episode = parse_episode_page(page, episode_url)
        transcript, note = await _transcript(client, episode.get("youtube_id"))
        episode["transcript"] = transcript
        episode["transcript_note"] = note
        if transcript and len(transcript) > TRANSCRIPT_LIMIT:
            episode["transcript"] = transcript[:TRANSCRIPT_LIMIT]
            episode["transcript_truncated"] = True
        return episode


async def _transcript(client: httpx.AsyncClient, video_id: str | None) -> tuple[str | None, str]:
    if not video_id:
        return None, "Episode page has a summary only; no YouTube video id was published."
    try:
        watch = await _get_text(client, f"https://www.youtube.com/watch?v={video_id}")
    except httpx.HTTPError:
        return None, "Episode page has a summary only; YouTube captions were not available."
    caption_url = caption_url_from_watch_html(watch)
    if not caption_url:
        return None, "Episode page has a summary only; YouTube captions were not available."
    try:
        xml = await _get_text(client, caption_url)
    except httpx.HTTPError:
        return None, "Episode page has a summary only; YouTube captions were not available."
    text = captions_to_text(xml)
    if not text:
        return None, "Episode page has a summary only; YouTube captions were empty."
    return text, "YouTube captions for the episode video."
