"""
Test RSS ingestion from sources.json.
Fetches a handful of breaking-tier sources and prints what comes back.
Run: python3 scripts/test_feeds.py
"""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.source_registry import load_sources, get_sources_for_tier
from src.ingestion.fetcher import RSSFetcher


async def main():
    sources = load_sources()
    print(f"Loaded {len(sources)} sources from config/sources.json\n")

    # Test 3 breaking-tier sources
    breaking = get_sources_for_tier("breaking")[:3]
    fetcher = RSSFetcher()

    for source in breaking:
        print(f"Fetching: {source.name} ({source.rss_url})")
        articles = await fetcher.fetch_source(source, max_articles=5)
        print(f"  Got {len(articles)} articles")
        for a in articles[:2]:
            print(f"  [{a.source_type}] {a.title[:80]}")
            print(f"    {a.url}")
            print(f"    content length: {len(a.content)} chars | categories: {[c.value for c in a.categories]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
