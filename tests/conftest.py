import os
import sys

import pytest

# Configure the app before it is imported: in-memory database, no background jobs
os.environ["TML_DISABLE_SCHEDULER"] = "1"
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402


@pytest.fixture
def tml(tmp_path, monkeypatch):
    """The app module with an empty database and no real waiting."""
    monkeypatch.setattr(app_module, "MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(app_module.time, "sleep", lambda seconds: None)
    for name in ("DISCORD_ALL", "DISCORD_WEBHOOK_LETTER", "DISCORD_WEBHOOK_REFLECTION",
                 "DISCORD_WEBHOOK_SYMBOL", "DISCORD_WEBHOOK_AURIC"):
        monkeypatch.delenv(name, raising=False)
    with app_module.app.app_context():
        app_module.db.drop_all()
        app_module.db.create_all()
    return app_module


@pytest.fixture
def client(tml):
    return tml.app.test_client()


@pytest.fixture
def seeded(tml):
    """Database with all collections and exchange rates."""
    with tml.app.app_context():
        for i, c in enumerate(tml.COLLECTIONS):
            tml.db.session.add(tml.NFT(
                symbol=c["symbol"], name=c["name"], order=c["order"], image=c["image"], url=c["url"],
                color=c["color"], floorPrice=(i + 1) * 1_000_000_000, listedCount=10 + i,
                avgPrice24hr=(i + 1) * 1_000_000_000, volumeAll=1000, include_in_total=c["include_in_total"],
            ))
        for c, price in zip(tml.CURRENCIES, (100.0, 90.0, 0.03, 0.001)):
            tml.db.session.add(tml.CRYPTO(symbol=c["symbol"], name=c["name"], sign=c["sign"], price=price))
        tml.db.session.commit()
    return tml
