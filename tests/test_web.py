"""Pages, JSON API and security headers."""
from datetime import timedelta


def test_loading_page_before_first_fetch(client):
    response = client.get("/")
    assert response.status_code == 503
    assert b"Fetching the latest prices" in response.data


def test_front_page(seeded, client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for collection in seeded.COLLECTIONS:
        assert collection["name"] in html
    assert "Not in set" in html  # the Golden Auric


def test_unknown_currency_redirects_to_front_page(seeded, client):
    response = client.get("/?currency=NOPE")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_api_prices(seeded, client):
    data = client.get("/api/prices").get_json()
    assert {n["symbol"] for n in data["nfts"]} == {c["symbol"] for c in seeded.COLLECTIONS}
    # Full set = collections with include_in_total (1 + 2 + 3 SOL in the seed data)
    assert data["total_floor"] == 6
    assert [c["symbol"] for c in data["currencies"]] == [c["symbol"] for c in seeded.CURRENCIES]


def test_api_prices_before_first_fetch(client):
    assert client.get("/api/prices").status_code == 503


def test_security_headers(seeded, client):
    headers = client.get("/").headers
    csp = headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp
    assert "frame-ancestors 'none'" in csp
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_static_files_have_version_tags(seeded, client):
    html = client.get("/").get_data(as_text=True)
    assert "/static/css/nft.css?v=" in html
    assert "/static/js/live.js?v=" in html


def test_media_route_blocks_path_traversal(client):
    assert client.get("/media/../app.py").status_code == 404
    assert client.get("/media/%2e%2e/app.py").status_code == 404


def test_readiness(seeded, client):
    assert client.get("/readiness").status_code == 200


def test_api_history(seeded, client):
    tml = seeded
    now = tml.utcnow()
    with tml.app.app_context():
        for minutes, floor in ((60 * 24 * 10, 9), (60 * 24 * 2, 5), (30, 6)):
            tml.db.session.add(tml.FloorHistory(symbol="the_reflection_of_love",
                                                recorded=now - timedelta(minutes=minutes),
                                                floor=floor * 1_000_000_000, listed=1))
        tml.db.session.commit()

    data = client.get("/api/history?days=7").get_json()
    series = data["history"]["the_reflection_of_love"]
    # The 10-day-old row is outside the 7-day window
    assert [value for _, value in series] == [5, 6]
    assert series[0][0].endswith("Z")
