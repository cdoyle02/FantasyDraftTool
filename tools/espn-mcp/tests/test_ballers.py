from espn_mcp.ballers import (
    caption_url_from_watch_html,
    captions_to_text,
    latest_episode_url,
    parse_episode_page,
)

INDEX = """
<a href="https://www.thefantasyfootballers.com/episodes/">Archive</a>
<a href="https://www.thefantasyfootballers.com/episodes/week-5-waivers-tyreek-talk-hole-in-one/">Latest</a>
<a href="https://www.thefantasyfootballers.com/episodes/older-show/">Older</a>
"""

PAGE = """
<meta property="og:title" content="Week 5 Waivers + Tyreek Talk" />
<meta property="og:description" content="Waiver wire for Week 5." />
<meta property="article:published_time" content="2026-10-06T19:26:25+00:00" />
<meta property="og:url" content="https://www.thefantasyfootballers.com/episodes/week-5/" />
<img src="https://img.youtube.com/vi/Y9-NBj7W-rI/maxresdefault.jpg" />
"""

WATCH = r"""
"captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=Y9-NBj7W-rI\u0026lang=en"}]
"""


def test_latest_episode_url_skips_the_archive_index() -> None:
    assert (
        latest_episode_url(INDEX)
        == "https://www.thefantasyfootballers.com/episodes/week-5-waivers-tyreek-talk-hole-in-one/"
    )


def test_parse_episode_page_reads_summary_and_video_id() -> None:
    episode = parse_episode_page(PAGE, "https://example.test/fallback")
    assert episode["title"] == "Week 5 Waivers + Tyreek Talk"
    assert episode["summary"] == "Waiver wire for Week 5."
    assert episode["published"] == "2026-10-06T19:26:25+00:00"
    assert episode["youtube_id"] == "Y9-NBj7W-rI"


def test_caption_url_and_text() -> None:
    url = caption_url_from_watch_html(WATCH)
    assert url == "https://www.youtube.com/api/timedtext?v=Y9-NBj7W-rI&lang=en"
    text = captions_to_text("<text start='0'>Lamar &amp; friends</text><text>start</text>")
    assert text == "Lamar & friends start"
