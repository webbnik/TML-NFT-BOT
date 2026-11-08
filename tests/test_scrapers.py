"""Magic Eden/Binance scrapers, price history, Discord alerts and media URLs."""
from datetime import datetime, timedelta

import pytest
import requests

SOL = 1_000_000_000


def stats(floor, listed=10):
    return {"floorPrice": floor, "listedCount": listed, "avgPrice24hr": floor, "volumeAll": 1000.0}


def fake_magiceden(monkeypatch, tml, responses):
    """Make get_json return responses[symbol] for Magic Eden stats URLs."""
    def get_json(url):
        for symbol, response in responses.items():
            if f"/collections/{symbol}/stats" in url:
                return response
        return None
    monkeypatch.setattr(tml, "get_json", get_json)


@pytest.mark.parametrize("bad_response", [None, "<html>oops</html>", {"msg": "rate limited"}, {"floorPrice": None}])
def test_magiceden_bad_responses_are_skipped(tml, monkeypatch, bad_response):
    fake_magiceden(monkeypatch, tml, {c["symbol"]: bad_response for c in tml.COLLECTIONS})
    tml.fetch_magiceden()  # must not raise
    with tml.app.app_context():
        assert tml.NFT.query.count() == 0


def test_get_json_handles_errors(tml, monkeypatch):
    def timeout(*args, **kwargs):
        raise requests.Timeout("timed out")
    monkeypatch.setattr(tml.requests, "get", timeout)
    assert tml.get_json("https://example.invalid") is None


def test_magiceden_stores_prices_history_and_alerts(tml, monkeypatch):
    sent = []
    monkeypatch.setattr(tml.requests, "post", lambda url, json, timeout: sent.append((url, json)))
    monkeypatch.setenv("DISCORD_ALL", "https://discord.test/all")
    symbol = "the_reflection_of_love"

    clock = [datetime(2026, 1, 1, 12, 0, 0)]
    monkeypatch.setattr(tml, "utcnow", lambda: clock[0])

    # First fetch: stored, no alert (nothing to compare with)
    fake_magiceden(monkeypatch, tml, {symbol: stats(20 * SOL)})
    tml.fetch_magiceden()
    # Same price 1 minute later: no new history row
    clock[0] += timedelta(minutes=1)
    tml.fetch_magiceden()
    # Floor drops: alert + history row
    clock[0] += timedelta(minutes=1)
    fake_magiceden(monkeypatch, tml, {symbol: stats(18 * SOL)})
    tml.fetch_magiceden()
    # Unchanged but 5 minutes later: regular history sample
    clock[0] += timedelta(minutes=5)
    tml.fetch_magiceden()

    with tml.app.app_context():
        assert tml.NFT.query.filter_by(symbol=symbol).one().floorPrice == 18 * SOL
        rows = tml.FloorHistory.query.filter_by(symbol=symbol).order_by(tml.FloorHistory.recorded).all()
        assert [r.floor for r in rows] == [20 * SOL, 18 * SOL, 18 * SOL]

    assert len(sent) == 1
    url, payload = sent[0]
    assert url == "https://discord.test/all"
    assert "decreased from 20.0 SOL to 18.0 SOL" in payload["embeds"][0]["description"]


def test_magiceden_ignores_buggy_tiny_floor(tml, monkeypatch):
    fake_magiceden(monkeypatch, tml, {"the_reflection_of_love": stats(5)})
    tml.fetch_magiceden()
    with tml.app.app_context():
        assert tml.NFT.query.count() == 0


def test_discord_alert_uses_floor_nft_artwork(seeded, monkeypatch):
    tml = seeded
    sent = []
    monkeypatch.setattr(tml.requests, "post", lambda url, json, timeout: sent.append(json))
    with tml.app.app_context():
        tml.db.session.add(tml.MEDIA(symbol="the_reflection_of_love", mint="MINT123",
                                     token_name="The Reflection of Love #1", image_file="abc.webp"))
        tml.db.session.commit()
        nft = tml.NFT.query.filter_by(symbol="the_reflection_of_love").one()
        tml.discord_webhook(nft, nft.floorPrice + SOL, 5, ["https://discord.test/hook", None])

    embed = sent[0]["embeds"][0]
    assert embed["thumbnail"]["url"] == f"{tml.PUBLIC_URL}/media/abc.webp"
    assert any("item-details/MINT123" in field["value"] for field in embed["fields"])


def test_binance_stores_rates_and_rate_history(tml, monkeypatch):
    monkeypatch.setattr(tml, "get_json", lambda url: {"price": "100.5"})
    tml.fetch_binance()
    tml.fetch_binance()  # within 5 minutes: no second history row
    with tml.app.app_context():
        assert tml.CRYPTO.query.count() == len(tml.CURRENCIES)
        assert tml.RateHistory.query.count() == len(tml.CURRENCIES)


def test_binance_bad_response_is_skipped(tml, monkeypatch):
    monkeypatch.setattr(tml, "get_json", lambda url: {"code": -1121, "msg": "Invalid symbol."})
    tml.fetch_binance()
    with tml.app.app_context():
        assert tml.CRYPTO.query.count() == 0


@pytest.mark.parametrize("url, expected", [
    ("https://bafyabc.ipfs.nftstorage.link/6020.png?ext=png", "/bafyabc/6020.png"),
    ("ipfs://bafyabc/1.mp4", "/bafyabc/1.mp4"),
    ("https://ipfs.io/ipfs/bafyabc/x/2.png", "/bafyabc/x/2.png"),
    ("https://pbs.twimg.com/media/a.jpg", None),
    ("http://127.0.0.1:8000/admin", None),
    ("http://169.254.169.254/latest/meta-data", None),
    ("https://evil.example/ipfs/bafyabc/../../x", None),
    ("", None),
    (None, None),
])
def test_media_downloads_only_from_ipfs_gateway(tml, url, expected):
    result = tml.ipfs_to_gateway(url)
    if expected is None:
        assert result is None
    else:
        assert result == tml.IPFS_GATEWAY + expected
