"""Backups, status alerts and history with exchange rates."""
import gzip
import os
import sqlite3
from datetime import datetime, timedelta


def test_backup_creates_compressed_copy_and_keeps_newest(tml, tmp_path, monkeypatch):
    backups = tmp_path / "backups"
    monkeypatch.setattr(tml, "BACKUP_DIR", str(backups))
    monkeypatch.setattr(tml, "BACKUP_KEEP", 3)
    monkeypatch.setattr(tml, "utcnow", lambda: datetime(2026, 11, 9, 3, 30))

    source = tmp_path / "source.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE floor_history (floor INTEGER)")
        db.execute("INSERT INTO floor_history VALUES (42)")

    # Older backups: only the newest 3 (including today's) are kept
    backups.mkdir()
    for day in range(1, 6):
        (backups / f"nft-2026-11-0{day}.db.gz").write_bytes(b"old")

    target = tml.backup_database(source=str(source))

    assert os.path.basename(target) == "nft-2026-11-09.db.gz"
    restored = tmp_path / "restored.db"
    restored.write_bytes(gzip.decompress(open(target, "rb").read()))
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT floor FROM floor_history").fetchone() == (42,)
    assert sorted(os.listdir(backups)) == ["nft-2026-11-04.db.gz", "nft-2026-11-05.db.gz", "nft-2026-11-09.db.gz"]


def test_backup_skips_in_memory_database(tml):
    assert tml.backup_database() is None


def test_stale_prices_alert_once_and_on_recovery(seeded, monkeypatch):
    tml = seeded
    sent = []
    monkeypatch.setattr(tml.requests, "post", lambda url, json, timeout: sent.append(json["embeds"][0]["description"]))
    monkeypatch.setenv("DISCORD_WEBHOOK_STATUS", "https://discord.test/status")
    monkeypatch.setattr(tml, "_stale_alerts", {})

    clock = [tml.utcnow() + timedelta(minutes=30)]
    monkeypatch.setattr(tml, "utcnow", lambda: clock[0])

    tml.check_freshness()   # both sources 30 minutes old -> two alerts
    tml.check_freshness()   # still stale -> no repeat
    assert len(sent) == 2 and all("have not updated" in m for m in sent)

    with tml.app.app_context():
        for row in tml.NFT.query.all() + tml.CRYPTO.query.all():
            row.fetched = clock[0]
        tml.db.session.commit()
    tml.check_freshness()   # fresh again -> two recovery messages
    assert len(sent) == 4 and all("updating again" in m for m in sent[2:])


def test_api_history_with_rates(seeded, client):
    tml = seeded
    now = tml.utcnow()
    with tml.app.app_context():
        tml.db.session.add(tml.RateHistory(symbol="SOLUSDT", recorded=now - timedelta(hours=1), price=90.0))
        tml.db.session.commit()
    data = client.get("/api/history?days=7&rates=1").get_json()
    assert data["rates"]["SOLUSDT"][0][1] == 90.0
    assert "rates" not in client.get("/api/history?days=7").get_json()


def test_history_page(seeded, client):
    response = client.get("/history")
    assert response.status_code == 200
    assert "Price history" in response.get_data(as_text=True)
    assert "Strict-Transport-Security" in response.headers
