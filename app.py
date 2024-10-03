import os
import time
import json
import logging
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_apscheduler import APScheduler
from jinja2.exceptions import UndefinedError
from flask_migrate import Migrate, upgrade, init
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

jobstores = { 'default': SQLAlchemyJobStore(url='sqlite:///instance/jobs.sqlite')}
scheduler = BackgroundScheduler(jobstores=jobstores)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nft.db"
db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)

if os.getenv("FLASK_ENV") == "development":
    load_dotenv()

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
    volumeAll = db.Column(db.Integer, nullable=False)
    include_in_total = db.Column(db.Boolean, nullable=False, default=True)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class CRYPTO(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sign = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Integer, nullable=False)
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
    for webhook in webhooks:
        requests.post(webhook, json=payload)


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
            },
            {
                "symbol": "ghost_kid_dao",
                "name": "GhostKidDAO",
                "order": 9999,
                "image": "https://img-cdn.magiceden.dev/rs:fill:400:400:0:0/plain/https://creator-hub-prod.s3.us-east-2.amazonaws.com/ghost_kid_dao_pfp_1662325189064.gif",
                "url": "https://magiceden.io/marketplace/ghost_kid_dao",
                "color": 16777215,
                "webhook": [os.getenv("DISCORD_WEBHOOK_GHOST")],
                "include_in_total": False
            }
        ]

        for symbol in symbols:
            url = f"https://api-mainnet.magiceden.dev/v2/collections/{symbol['symbol']}/stats?listingAggMode=true"
            response = requests.get(url, headers={"accept": "application/json"})
            data = response.json()
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
                "name": "Etherium",
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
            response = requests.get(url, headers={"accept": "application/json"})
            data = response.json()
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

@app.route("/", methods=['GET'])
def index():

    currency = request.args.get("currency", default="SOLUSDT")
    nfts = NFT.query.all()


    currency = CRYPTO.query.filter_by(symbol=currency).first()

    # Try to find the requested currency, if not found redirect to front page
    if not currency:
        return redirect(url_for('index'))  # Redirect to the front page

    currencies = CRYPTO.query.all()

    # Calculate total floor price
    total_floor_price = 0
    for nft in nfts:
        # Only include nfts that has True in include_in_total
        if nft.include_in_total:
            total_floor_price += nft.floorPrice
    nftfetched = NFT.query.order_by(NFT.fetched.desc()).first()
    return render_template("nfts.html", currency=currency, currencies=currencies, nfts=nfts, total_floor_price=total_floor_price, nftfetched=nftfetched)

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

scheduler.add_job(fetch_magiceden, 'interval', seconds=20, id="magiceden", replace_existing=True, next_run_time=datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1))
scheduler.add_job(fetch_binance, 'interval', seconds=20, id="binance", replace_existing=True, next_run_time=datetime.now().replace(second=10, microsecond=0) + timedelta(minutes=1))
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