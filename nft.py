from flask import Flask, render_template, request
import time
import requests
import json
from dotenv import load_dotenv
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///nft.db"

db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


class NFT(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(300), nullable=False)
    color = db.Column(db.Integer, nullable=False)
    webhook = db.Column(db.String(300), nullable=True)
    floorPrice = db.Column(db.Integer, nullable=False)
    listedCount = db.Column(db.Integer, nullable=False)
    avgPrice24hr = db.Column(db.Integer, nullable=False)
    volumeAll = db.Column(db.Integer, nullable=False)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Symbol: {self.symbol}, Floor Price: {self.floorPrice}, Listed Count: {self.listedCount}, Average Price 24hr: {self.avgPrice24hr}, Volume All: {self.volumeAll}"

class CRYPTO(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sign = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    fetched = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Symbol: {self.symbol}, Price: {self.price}"

@scheduler.task('interval', id='magiceden', seconds=25, misfire_grace_time=900)
def fetch_magiceden():
    with app.app_context():
    # with scheduler.app.app_context():
        symbols = [
                {
                    "symbol": "tomorrowland_winter",
                    "name": "A letter from the Universe (Winter)",
                    "order": 1,
                    "image": "https://pbs.twimg.com/media/FZar7ZcUsAAw0wa.jpg",
                    "url": "https://magiceden.io/marketplace/tomorrowland_winter",
                    "color": 7608595,
                    "webhook": os.getenv("DISCORD_WEBHOOK_LETTER")
                },
                {
                    "symbol": "the_reflection_of_love",
                    "name": "The reflection of Love",
                    "order": 2,
                    "image": "https://moon.ly/uploads/nft/e8141974-650f-4c59-80b0-3bb9397ae049.gif",
                    "url": "https://magiceden.io/marketplace/the_reflection_of_love",
                    "color": 1274905,
                    "webhook": os.getenv("DISCORD_WEBHOOK_REFLECTION")
                },
                {
                    "symbol": "tomorrowland_love_unity",
                    "name": "The Symbol of Love and Unity",
                    "order": 3,
                    "image": "https://img-cdn.magiceden.dev/rs:fill:400:400:0:0/plain/https://bafybeidzsht5g3rtb2crlgildg3hrbt5mtuiw6eiakxj5ckhftvrqyjvbm.ipfs.nftstorage.link/",
                    "url": "https://magiceden.io/marketplace/tomorrowland_love_unity",
                    "color": 1643380,
                    "webhook": os.getenv("DISCORD_WEBHOOK_SYMBOL")
                },
                {
                    "symbol": "the_golden_auric",
                    "name": "The Golden Auric",
                    "order": 0,
                    "image": "https://img-cdn.magiceden.dev/rs:fill:400:400:0:0/plain/https://creator-hub-prod.s3.us-east-2.amazonaws.com/the_golden_auric_pfp_1682607788127.png",
                    "url": "https://magiceden.io/marketplace/the_golden_auric",
                    "color": 16777215,
                    "webhook": os.getenv("DISCORD_WEBHOOK_AURIC")
                }
            ]

        discord = os.getenv("DISCORD_WEBHOOK")
        for symbol_info in symbols:
            symbol = symbol_info["symbol"]
            url = f"https://api-mainnet.magiceden.dev/v2/collections/{symbol}/stats"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            # Add data to database
            data = response.json()
            # Add data to database, if symbol already exists, update the data
            nft = NFT.query.filter_by(symbol=data["symbol"]).first()
            if nft:
                # If floor price has increased, send message to Discord
                upordown = "unchanged"
                if nft.floorPrice < data["floorPrice"]:
                    upordown = "increased"
                # If floor price has decreased, send message to Discord
                elif nft.floorPrice > data["floorPrice"]:
                    upordown = "decreased"
                payload = {
                    "username": "NFT",
                    "avatar_url": "https://i.imgur.com/4M34hi2.png",
                    "embeds": [
                        {
                            "title": "Floor Price Update",
                            "description": f"{symbol_info['name']} has {upordown} from {data['floorPrice'] / 1000000000} SOL to {data['floorPrice'] / 1000000000} SOL",
                            "color": symbol_info["color"],
                            "fields": [
                                {
                                    "name": "New floor Price",
                                    "value": f"{data['floorPrice'] / 1000000000} SOL",
                                    "inline": True
                                },
                                {
                                    "name": "Old floor Price",
                                    "value": f"{nft.floorPrice / 1000000000} SOL",
                                    "inline": True
                                }
                            ],
                            "thumbnail": {
                                "url": f"{symbol_info['image']}"
                            },
                            "footer": {
                                "text": f"Floor price has {upordown}",
                                "icon_url": "https://example.com/up_icon.png"
                            }
                        }
                    ]
                }
                # Send message to Discord if there is a change in floor price
                if nft.floorPrice != data["floorPrice"]:
                    requests.post(discord, json=payload)
                nft.name = symbol_info["name"]
                nft.order = symbol_info["order"]
                nft.image = symbol_info["image"]
                nft.url = symbol_info["url"]
                nft.color = symbol_info["color"]
                nft.webhook = symbol_info["webhook"]
                nft.floorPrice = data["floorPrice"]
                nft.listedCount = data["listedCount"]
                try:
                    nft.avgPrice24hr = data["avgPrice24hr"]
                except:
                    nft.avgPrice24hr = 0
                nft.volumeAll = data["volumeAll"]
                nft.fetched = datetime.utcnow()
                db.session.commit()
            else:
                try:
                    avgPrice24hr = data["avgPrice24hr"]
                except:
                    data["avgPrice24hr"] = 0
                nft = NFT(
                    symbol=data["symbol"],
                    name=symbol_info["name"],
                    order=symbol_info["order"],
                    image=symbol_info["image"],
                    url=symbol_info["url"],
                    color=symbol_info["color"],
                    webhook=symbol_info["webhook"],
                    floorPrice=data["floorPrice"],
                    listedCount=data["listedCount"],
                    avgPrice24hr=data["avgPrice24hr"],
                    volumeAll=data["volumeAll"],
                    fetched=datetime.utcnow()
                )
                db.session.add(nft)
                db.session.commit()
            time.sleep(1)

@scheduler.task('interval', id='binance', seconds=20, misfire_grace_time=900)
def fetchbinance():
    with app.app_context():
        # symbols = ["SOLUSDT", "SOLEUR"]
        symbols = [
        {
            "symbol": "SOLUSDT",
            "name": "USDT",
            "sign": "$"        },
        {
            "symbol": "SOLEUR",
            "name": "Euro",
            "sign": "€"
        }
    ]
        for symbol_info in symbols:
            symbol = symbol_info["symbol"]
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            data = response.json()
            crypto = CRYPTO.query.filter_by(symbol=symbol_info["symbol"]).first()
            # Add data to database, if symbol already exists, update the data
            if crypto:
                crypto.price = data["price"]
                crypto.name = symbol_info["name"]
                crypto.sign = symbol_info["sign"]
                crypto.fetched = datetime.utcnow()
                db.session.commit()
            else:
                crypto = CRYPTO(symbol=symbol_info["symbol"], price=data["price"], name=symbol_info["name"], sign=symbol_info["sign"], fetched=datetime.utcnow())
                db.session.add(crypto)
                db.session.commit()


@app.route("/", methods=['GET'])
def index():
    currency = request.args.get("currency", default="SOLUSDT")
    nfts = NFT.query.all()
    currency = CRYPTO.query.filter_by(symbol=currency).first()
    currencies = CRYPTO.query.all()
    # eur = CRYPTO.query.filter_by(symbol="SOLEUR").first()
    # Sum total floor price
    total_floor_price = 0
    for nft in nfts:
        if nft.order != 0:
            total_floor_price += nft.floorPrice
    nftfetched = NFT.query.order_by(NFT.fetched.desc()).first()
    return render_template("nfts.html", currency=currency, currencies=currencies, nfts=nfts, total_floor_price=total_floor_price, nftfetched=nftfetched)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8457, debug=True)