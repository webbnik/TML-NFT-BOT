# TML-NFT-BOT
Just a small bot to fetch NFT floor prices for the [Tomorrowland Medallion](https://nft.tomorrowland.com/forge).

Floor prices are fetched from the Magic Eden API and SOL exchange rates from Binance every 40 seconds, and presented on [nft.hardy.se](https://nft.hardy.se/):
- Live prices that update without reloading the page
- The current floor NFT of each collection, with its animation
- A 7-day floor trend per collection, and a [price history page](https://nft.hardy.se/history) with charts (7 days to all time, in SOL or any currency)
- Prices in USDT, EUR, ETH or BTC, a holdings calculator, and light/dark themes

The bot also sends any floor updates to a Discord server: https://discord.gg/WGYaCcApvQ
<img width="509" alt="Screenshot 2023-06-15 at 05 35 49" src="https://github.com/webbnik/TML-NFT-BOT/assets/9825063/b219de7e-f279-4d55-a2b8-9ecaa6716d41">

For any support or feedback, please open an Issue or contact me on Discord ^

## Price history
Floor prices are stored whenever they change (and at least every 5 minutes), and SOL exchange rates every 5 minutes. History is kept indefinitely in the `floor_history` and `rate_history` tables of `instance/nft.db`.

`GET /api/history?days=30` returns the floor history per collection (up to 200 points per collection, max 3650 days). Add `&rates=1` for the SOL exchange rates over the same period, and `&points=1000` for more detail.

## Backups and monitoring
- The database is backed up every night at 03:30 UTC (and shortly after each start) as `nft-YYYY-MM-DD.db.gz`; the newest 30 are kept. In production they are in the `tml-nft-backups` Docker volume (`/var/lib/docker/volumes/tml-nft-backups/_data` on the server). Sync that folder somewhere else to keep copies off the server.
- To restore: stop the container, `gunzip` a backup to `nft.db` in the `tml-nft-data` volume, and start it again.
- If floor prices or exchange rates stop updating for 15 minutes, a message is posted to the `DISCORD_WEBHOOK_STATUS` channel (and again when they recover).

## Running locally
```bash
python -m venv venv
venv/bin/pip install -r requirements-dev.txt     # Windows: venv\Scripts\pip
venv/bin/python app.py                           # http://localhost:8457
```
Or with Docker: `docker compose up --build` (http://localhost:8459).

Without a `.env` file no Discord alerts are sent. Copy `.env_example` to `.env` and set `FLASK_ENV=development` to use webhooks locally.

Run the tests with `python -m pytest`. They also run on every deploy (a failing test stops the deploy), and on pull requests using GitHub's runners.

### Settings (environment variables)
| Variable | Default | Purpose |
|---|---|---|
| `DISCORD_*` | – | Discord webhook URLs, see `.env_example` |
| `PUBLIC_URL` | `https://nft.hardy.se` | Public address, used for images in Discord alerts |
| `IPFS_GATEWAY` | `https://ipfs.filebase.io/ipfs` | Gateway used to download NFT artwork |
| `DATABASE_URL` | `sqlite:///nft.db` | Database (relative paths are inside `instance/`) |
| `DISCORD_WEBHOOK_STATUS` | – | Where to post alerts when prices stop updating |
| `STALE_ALERT_MINUTES` | `15` | How long without updates before alerting |
| `BACKUP_DIR` / `BACKUP_KEEP` | `instance/backups` / `30` | Where nightly backups go and how many to keep |

## Deployment
Pushing to `master` runs the tests, builds the Docker image and deploys it on the server. The database and downloaded artwork are stored in the `tml-nft-data` Docker volume, so they survive deploys.

## Credits & licenses
- **Font:** [Space Grotesk](https://github.com/floriankarsten/space-grotesk), self-hosted in `static/fonts/` under the SIL Open Font License 1.1 (see `static/fonts/OFL.txt`).
- **Icons:** simple line icons drawn for this project (`templates/icons.svg`). No third-party icon set or front-end library is used.
- **NFT artwork:** belongs to its respective owners (Tomorrowland). It is not stored in this repository; the app downloads the current floor NFT's artwork from IPFS at runtime and caches it in the `instance/` folder.
