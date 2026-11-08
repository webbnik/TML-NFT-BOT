import io
import os
import re
import time
import hashlib
import logging
import requests
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from jinja2.exceptions import UndefinedError
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from apscheduler.schedulers.background import BackgroundScheduler
from PIL import Image

# Jobs are re-added on every start, so they don't need a persistent job store
scheduler = BackgroundScheduler()

# Timeout (seconds) for calls to Magic Eden and Binance
REQUEST_TIMEOUT = 10

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nft.db"
db = SQLAlchemy()
db.init_app(app)

if os.getenv("FLASK_ENV") == "development":
    load_dotenv()


_asset_versions = {}


@app.template_global()
def asset(filename):
    """URL of a static file with a version tag based on its content, e.g.
    /static/css/nft.css?v=3f9a1c2b7d. Browsers and Cloudflare cache static
    files for hours, so a changed file must get a new URL to be picked up."""
    version = _asset_versions.get(filename)
    if version is None:
        with open(os.path.join(app.static_folder, filename), "rb") as file:
            version = hashlib.sha256(file.read()).hexdigest()[:10]
        if not app.debug:
            _asset_versions[filename] = version
    return url_for("static", filename=filename, v=version)

class NFT(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    color = db.Column(db.Integer, nullable=False)
    floorPrice = db.Column(db.Integer, nullable=False)
    listedCount = db.Column(db.Integer, nullable=False)
    avgPrice24hr = db.Column(db.Integer, nullable=False)
    volumeAll = db.Column(db.Integer, nullable=True)
    include_in_total = db.Column(db.Boolean, nullable=False, default=True)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class CRYPTO(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sign = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class MEDIA(db.Model):
    """Artwork of the cheapest listed NFT (the "floor NFT") of a collection,
    downloaded to the instance folder and served from /media/."""
    symbol = db.Column(db.String(100), primary_key=True)
    mint = db.Column(db.String(100), nullable=False)
    token_name = db.Column(db.String(200), nullable=False)
    image_file = db.Column(db.String(200), nullable=True)
    video_file = db.Column(db.String(200), nullable=True)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

def discord_webhook(nft, current_floorprice, listedcount, webhooks):
    upordown = "increased" if nft.floorPrice < current_floorprice else "decreased"
    upordowngraphic = "https://nft.hardy.se/static/img/increase.png" if upordown == "increased" else "https://nft.hardy.se/static/img/decrease.png"
    payload = {
        "username": "NFT",
        "avatar_url": "https://i.imgur.com/4M34hi2.png",
        "embeds": [
            {
                "title": f"{nft.name}",
                "url": f"{nft.url}",
                "description": f"Has {upordown} from {nft.floorPrice / 1000000000} SOL to {current_floorprice / 1000000000} SOL",
                "color": nft.color,
                "author": {
                "name": "nft.hardy.se",
                "url": "https://nft.hardy.se/"
                },
                "fields": [
                    {
                        "name": "Old floor Price",
                        "value": f"{nft.floorPrice / 1000000000} SOL",
                        "inline": True
                    },
                    {
                        "name": "New floor Price",
                        "value": f"{current_floorprice / 1000000000} SOL",
                        "inline": True
                    },
                    {
                        "name": "Listed",
                        "value": f"{listedcount}",
                        "inline": True
                    },
                ],
                "thumbnail": {
                    "url": f"{nft.image}"
                },
                "footer": {
                    "text": f"Floor price has {upordown}",
                    "icon_url": f"{upordowngraphic}"
                }
            }
        ]
    }
    # Skip unset webhooks (e.g. when running locally without a .env)
    for webhook in filter(None, webhooks):
        try:
            requests.post(webhook, json=payload, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            print(f"Discord webhook failed: {e}")


def get_json(url):
    """Fetch JSON from an API. Returns None (and logs why) if the call fails
    or the response is not valid JSON, e.g. during a Magic Eden outage."""
    try:
        response = requests.get(url, headers={"accept": "application/json"}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f"Request to {url} failed: {e}")
        return None


def fetch_magiceden():
    with app.app_context():
        symbols = [
            {
                "symbol": "tomorrowland_winter",
                "name": "A letter from the Universe (Winter)",
                "order": 1,
                "image": "https://pbs.twimg.com/media/FZar7ZcUsAAw0wa.jpg",
                "url": "https://magiceden.io/marketplace/tomorrowland_winter",
                "color": 7608595,
                "webhook": [os.getenv("DISCORD_WEBHOOK_LETTER"), os.getenv("DISCORD_ALL")],
                "include_in_total": True
            },
            {
                "symbol": "the_reflection_of_love",
                "name": "The reflection of Love",
                "order": 2,
                "image": "https://moon.ly/uploads/nft/e8141974-650f-4c59-80b0-3bb9397ae049.gif",
                "url": "https://magiceden.io/marketplace/the_reflection_of_love",
                "color": 1274905,
                "webhook": [os.getenv("DISCORD_WEBHOOK_REFLECTION"), os.getenv("DISCORD_ALL")],
                "include_in_total": True
            },
            {
                "symbol": "tomorrowland_love_unity",
                "name": "The Symbol of Love and Unity",
                "order": 3,
                "image": "https://img-cdn.magiceden.dev/rs:fill:400:400:0:0/plain/https://bafybeidzsht5g3rtb2crlgildg3hrbt5mtuiw6eiakxj5ckhftvrqyjvbm.ipfs.nftstorage.link/",
                "url": "https://magiceden.io/marketplace/tomorrowland_love_unity",
                "color": 1643380,
                "webhook": [os.getenv("DISCORD_WEBHOOK_SYMBOL"), os.getenv("DISCORD_ALL")],
                "include_in_total": True
            },
            {
                "symbol": "the_golden_auric",
                "name": "The Golden Auric",
                "order": 0,
                "image": "https://img-cdn.magiceden.dev/rs:fill:400:400:0:0/plain/https://creator-hub-prod.s3.us-east-2.amazonaws.com/the_golden_auric_pfp_1682607788127.png",
                "url": "https://magiceden.io/marketplace/the_golden_auric",
                "color": 16777215,
                "webhook": [os.getenv("DISCORD_WEBHOOK_AURIC"), os.getenv("DISCORD_ALL")],
                "include_in_total": False
            }
        ]

        for symbol in symbols:
            url = f"https://api-mainnet.magiceden.dev/v2/collections/{symbol['symbol']}/stats?listingAggMode=true"
            data = get_json(url)
            # Skip this collection on API errors or unexpected responses
            if not isinstance(data, dict) or not isinstance(data.get("floorPrice"), (int, float)):
                print(f"Fetching ME at {datetime.now()} - Unexpected response, skipping - {symbol['symbol']}: {data}")
                time.sleep(1)
                continue
            data["symbol"] = data.get("symbol", symbol["symbol"])
            nft = NFT.query.filter_by(symbol=data["symbol"]).first()
            print(f"Fetching ME at {datetime.now()} - Floorprice: {data.get('floorPrice')} ({data.get('floorPrice') / 1000000000}) - {symbol['symbol']}")
            # Bug in MagicEden giving floorPrices below 999, so we ignore those
            if data.get("floorPrice") < 999:
                print("Floorprice below 999, ignoring")
            else:
                # Add data to database if it doesn't exist
                if not nft:
                    nft = NFT(
                        symbol=data.get("symbol"),
                        name=symbol.get("name"),
                        order=symbol.get("order"),
                        image=symbol.get("image"),
                        url=symbol.get("url"),
                        color=symbol.get("color"),
                        floorPrice=data.get("floorPrice"),
                        listedCount=data.get("listedCount"),
                        avgPrice24hr=data.get("avgPrice24hr", 0),
                        volumeAll=data.get("volumeAll"),
                        include_in_total=symbol.get("include_in_total"),
                        fetched=datetime.utcnow()
                    )
                    db.session.add(nft)
                    db.session.commit()

                # If NFT exists
                else:
                    # Send message to Discord if there is a change in floor price
                    if nft.floorPrice != data["floorPrice"]:
                        discord_webhook(nft, data["floorPrice"], data["listedCount"], symbol["webhook"])

                    # Update the NFT in the database
                    nft_attributes = {
                        "name": symbol.get("name"),
                        "order": symbol.get("order"),
                        "image": symbol.get("image"),
                        "url": symbol.get("url"),
                        "color": symbol.get("color"),
                        "floorPrice": data.get("floorPrice"),
                        "listedCount": data.get("listedCount"),
                        "avgPrice24hr": data.get("avgPrice24hr", 0),
                        "volumeAll": data.get("volumeAll"),
                        "include_in_total": symbol.get("include_in_total"),
                        "fetched": datetime.utcnow()
                    }
                    for attr, value in nft_attributes.items():
                        setattr(nft, attr, value)
                    db.session.commit()
                # Avoid hitting the rate limit of 2 qps
                time.sleep(1)


def fetch_binance():
    with app.app_context():
        currencies = [
            {
                "symbol": "SOLUSDT",
                "name": "USDT",
                "sign": "$"
            },
            {
                "symbol": "SOLEUR",
                "name": "Euro",
                "sign": "€"
            },
            {  "symbol": "SOLETH",
                "name": "Ethereum",
                "sign": "Ξ"
            },
            {
                "symbol": "SOLBTC",
                "name": "Bitcoin",
                "sign": "₿"
            }
        ]
        for currency in currencies:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={currency['symbol']}"
            data = get_json(url)
            if not isinstance(data, dict) or "price" not in data:
                print(f"Fetching Binance at {datetime.now()} - Unexpected response, skipping - {currency['symbol']}: {data}")
                continue
            crypto = CRYPTO.query.filter_by(symbol=currency["symbol"]).first()
            # Add data to database if it doesn't exist
            if not crypto:
                crypto = CRYPTO(
                    symbol=currency["symbol"],
                    price=data["price"],
                    name=currency["name"],
                    sign=currency["sign"],
                    fetched=datetime.utcnow()
                )
                db.session.add(crypto)
                db.session.commit()

            # If currency exists
            else:
                # Update the currency in the database
                crypto_attributes = {
                    "price": data.get("price"),
                    "name": currency.get("name"),
                    "sign": currency.get("sign"),
                    "fetched": datetime.utcnow()
                }
                for attr, value in crypto_attributes.items():
                    setattr(crypto, attr, value)
                db.session.commit()


# ---------- Floor NFT artwork ----------
# NFT files live on IPFS. The free gateways baked into the NFT metadata
# (nftstorage.link, dweb.link) shut down in 2026, so files are fetched through
# a gateway that still works and stored locally, so visitors never depend on IPFS.
IPFS_GATEWAY = os.getenv("IPFS_GATEWAY", "https://ipfs.filebase.io/ipfs").rstrip("/")
# The original PNGs are ~5 MB, so posters are resized to this size (pixels)
POSTER_SIZE = 800
MEDIA_DIR = os.path.join(app.instance_path, "media")
MEDIA_TIMEOUT = 120                      # the CDN can be slow on first fetch
MAX_MEDIA_BYTES = 30 * 1024 * 1024
MEDIA_EXTENSIONS = {"image/webp": ".webp", "image/png": ".png", "image/jpeg": ".jpg",
                    "image/gif": ".gif", "video/mp4": ".mp4", "video/webm": ".webm"}
IPFS_SUBDOMAIN = re.compile(r"^https?://([a-z0-9]+)\.ipfs\.[^/]+/?(.*)$", re.IGNORECASE)
IPFS_PATH = re.compile(r"^(?:ipfs://|https?://[^/]+/ipfs/)(?:ipfs/)?([A-Za-z0-9]+)/?(.*)$")


def ipfs_to_gateway(url):
    """Rewrite any IPFS URL to IPFS_GATEWAY. Other URLs are returned unchanged."""
    if not url:
        return None
    url = url.split("?")[0]
    match = IPFS_SUBDOMAIN.match(url) or IPFS_PATH.match(url)
    if not match:
        return url
    cid, path = match.groups()
    return f"{IPFS_GATEWAY}/{cid}/{path}".rstrip("/")


def download_media(url, kind, headers=None):
    """Download a video (or other media) into MEDIA_DIR. Files are named after a hash
    of the URL, so the same artwork is only downloaded once.
    Returns the file name, or None if the download failed."""
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    for existing in os.listdir(MEDIA_DIR):
        if existing.startswith(key + "."):
            return existing

    part = os.path.join(MEDIA_DIR, f"{key}.part")
    try:
        with requests.get(url, headers=headers, stream=True, timeout=MEDIA_TIMEOUT) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            extension = MEDIA_EXTENSIONS.get(content_type)
            if not extension or not content_type.startswith(kind):
                print(f"Media {url} has unexpected type {content_type!r}, skipping")
                return None
            size = 0
            with open(part, "wb") as file:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    size += len(chunk)
                    if size > MAX_MEDIA_BYTES:
                        raise ValueError("file too large")
                    file.write(chunk)
        filename = key + extension
        os.replace(part, os.path.join(MEDIA_DIR, filename))
        return filename
    except (requests.RequestException, ValueError, OSError) as e:
        print(f"Media download {url} failed: {e}")
        if os.path.exists(part):
            os.remove(part)
        return None


def download_poster(url):
    """Download an image and store a resized WebP copy in MEDIA_DIR.
    Returns the file name, or None if it failed."""
    filename = hashlib.sha256(url.encode()).hexdigest()[:24] + ".webp"
    path = os.path.join(MEDIA_DIR, filename)
    if os.path.exists(path):
        return filename
    try:
        with requests.get(url, stream=True, timeout=MEDIA_TIMEOUT) as response:
            response.raise_for_status()
            data = io.BytesIO()
            for chunk in response.iter_content(chunk_size=256 * 1024):
                data.write(chunk)
                if data.tell() > MAX_MEDIA_BYTES:
                    raise ValueError("file too large")
        data.seek(0)
        with Image.open(data) as image:
            image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            image.thumbnail((POSTER_SIZE, POSTER_SIZE), Image.Resampling.LANCZOS)
            image.save(path + ".part", "WEBP", quality=82, method=6)
        os.replace(path + ".part", path)
        return filename
    except (requests.RequestException, ValueError, OSError) as e:
        print(f"Poster download {url} failed: {e}")
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        return None


def media_exists(filename):
    return not filename or os.path.exists(os.path.join(MEDIA_DIR, filename))


def fetch_media():
    """Store the artwork (poster + animation) of each collection's floor NFT."""
    with app.app_context():
        os.makedirs(MEDIA_DIR, exist_ok=True)
        for nft in NFT.query.all():
            url = f"https://api-mainnet.magiceden.dev/v2/collections/{nft.symbol}/listings?limit=1"
            listings = get_json(url)
            time.sleep(1)  # Magic Eden rate limit
            if not isinstance(listings, list) or not listings:
                continue
            listing = listings[0]
            token = listing.get("token") or {}
            mint = token.get("mintAddress") or listing.get("tokenMint")
            if not mint:
                continue

            image_url = ipfs_to_gateway(token.get("image") or (listing.get("extra") or {}).get("img"))
            video_url = ipfs_to_gateway(token.get("animationUrl"))
            if not image_url and not video_url:
                continue  # no artwork in the metadata (e.g. A Letter from the Universe)

            # Skip if the floor NFT is unchanged and all its files are in place
            media = db.session.get(MEDIA, nft.symbol)
            if (media and media.mint == mint
                    and media_exists(media.image_file) and (media.image_file or not image_url)
                    and media_exists(media.video_file) and (media.video_file or not video_url)):
                continue

            image_file = download_poster(image_url) if image_url else None
            video_file = download_media(video_url, "video/") if video_url else None
            if not image_file and not video_file:
                continue

            if not media:
                media = MEDIA(symbol=nft.symbol)
                db.session.add(media)
            media.mint = mint
            media.token_name = token.get("name") or nft.name
            media.image_file = image_file
            media.video_file = video_file
            media.fetched = datetime.utcnow()
            db.session.commit()
            print(f"Floor NFT media for {nft.symbol}: {media.token_name} ({image_file}, {video_file})")

        # Remove files no longer used by any floor NFT
        in_use = {f for m in MEDIA.query.all() for f in (m.image_file, m.video_file) if f}
        for filename in os.listdir(MEDIA_DIR):
            if filename not in in_use and not filename.endswith(".part"):
                os.remove(os.path.join(MEDIA_DIR, filename))


LAMPORTS_PER_SOL = 1_000_000_000
DEFAULT_CURRENCY = "SOLUSDT"


def iso_utc(dt):
    """Stored datetimes are naive UTC; mark them as UTC for the browser."""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def get_state():
    """Current prices as plain data, shared by the page and the JSON API.
    Returns None until both scrapers have stored data."""
    nfts = NFT.query.filter(NFT.order != 9999).order_by(NFT.order).all()
    currencies = CRYPTO.query.order_by(CRYPTO.id).all()
    if not nfts or not currencies:
        return None

    media = {m.symbol: m for m in MEDIA.query.all()}

    def media_url(filename):
        return url_for("media_file", filename=filename) if filename else None

    def floor_nft(symbol):
        m = media.get(symbol)
        if not m:
            return None
        return {
            "name": m.token_name,
            "url": f"https://magiceden.io/item-details/{m.mint}",
            "image": media_url(m.image_file),
            "video": media_url(m.video_file),
        }

    return {
        "updated": iso_utc(max(nft.fetched for nft in nfts)),
        "total_floor": sum(nft.floorPrice for nft in nfts if nft.include_in_total) / LAMPORTS_PER_SOL,
        "currencies": [
            {
                "symbol": c.symbol,
                "name": c.name,
                "sign": c.sign,
                "price": float(c.price),
                "fetched": iso_utc(c.fetched),
            }
            for c in currencies
        ],
        "nfts": [
            {
                "symbol": n.symbol,
                "name": n.name,
                "order": n.order,
                "image": n.image,
                "url": n.url,
                "floor": n.floorPrice / LAMPORTS_PER_SOL,
                "avg24h": (n.avgPrice24hr or 0) / LAMPORTS_PER_SOL,
                "listed": n.listedCount,
                "volume_all": (n.volumeAll or 0) / LAMPORTS_PER_SOL,
                "include_in_total": n.include_in_total,
                "fetched": iso_utc(n.fetched),
                "floor_nft": floor_nft(n.symbol),
            }
            for n in nfts
        ],
    }


@app.route("/", methods=['GET'])
def index():
    state = get_state()
    # No data yet (e.g. right after a deploy): show the loading page
    if not state:
        return render_template('error.html'), 503

    symbols = [c["symbol"] for c in state["currencies"]]
    requested_currency = request.args.get("currency", default=DEFAULT_CURRENCY)
    # Unknown currency requested: go back to the front page (default currency)
    if requested_currency not in symbols:
        if "currency" in request.args:
            return redirect(url_for('index'))
        requested_currency = symbols[0]

    currency = next(c for c in state["currencies"] if c["symbol"] == requested_currency)
    return render_template("nfts.html", state=state, currency=currency)


@app.route("/api/prices", methods=['GET'])
def api_prices():
    """Latest prices as JSON; the front page polls this to update live."""
    state = get_state()
    if not state:
        return jsonify({"error": "No data fetched yet"}), 503
    response = jsonify(state)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/media/<path:filename>", methods=['GET'])
def media_file(filename):
    """Floor NFT artwork. File names are content hashes, so they never change."""
    response = send_from_directory(MEDIA_DIR, filename, max_age=31536000)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.errorhandler(UndefinedError)
def handle_undefined_error(e):
    # Logic to handle the error and display a custom error page
    return render_template('error.html', error_message=str(e)), 500

@app.route('/readiness')
def k8sreadiness():
  # Check if the database contains any nfts and crypto
    nft_exists = NFT.query.first() is not None
    crypto_exists = CRYPTO.query.first() is not None

    if nft_exists and crypto_exists:
        return "<h1><center>Readiness check completed</center><h1>", 200
    else:
        return "<h1><center>Readiness check failed</center><h1>", 500

# Create any missing tables on startup (replaces the old "flask db" migration steps)
with app.app_context():
    db.create_all()

scheduler.add_job(fetch_magiceden, 'interval', seconds=40, id="magiceden", replace_existing=True, next_run_time=datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1))
scheduler.add_job(fetch_binance, 'interval', seconds=40, id="binance", replace_existing=True, next_run_time=datetime.now().replace(second=10, microsecond=0) + timedelta(minutes=1))
scheduler.add_job(fetch_media, 'interval', minutes=5, id="media", replace_existing=True, next_run_time=datetime.now().replace(second=25, microsecond=0) + timedelta(minutes=1))
scheduler.start()

# Run as gunicorn
if __name__ != '__main__':
    # Use gunicorn's logger to replace flask's default logger
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

# Run as standalone flask
if __name__ == "__main__":

    with app.app_context():
        app.run()

    app.run(host="0.0.0.0", port=8457, debug=True)
