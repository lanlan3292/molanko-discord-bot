# Molanko Discord Bot

```bash
git clone --depth 1 --branch main https://github.com/lanlan3292/molanko-discord-bot.git
cd molanko-discord-bot
mv cogs/screenshot_web.py cogs/screenshot_web.py.disabled
```

```bash
python -m venv .venv
source .venv/Scripts/activate

python -m pip install -r requirements.txt

npm ci
```

## Configuration

Copy `.env.example` to `discord_bot.env` and fill in your values:

```bash
cp .env.example discord_bot.env
# then edit discord_bot.env
```

* `TOKEN` — your Discord bot token (required)
* `BADGEWORKS_API_URL` — URL of a Badgeworks API server (default `http://localhost:8080`)
* `BADGEWORKS_API_KEY` — API key for that server

Both `BADGEWORKS_*` variables are optional. The bot runs without them; only the
`/badge` command requires a Badgeworks API server.

## Badge command (`/badge`)

Generates a [Devins Badge](https://github.com/intergrav/devins-badges) via the
[Badgeworks API](https://github.com/ArthurSimin/Badgeworks/tree/api) and posts it as a
PNG attachment plus SVG source.

Requires `BADGEWORKS_API_URL` + `BADGEWORKS_API_KEY` to be set and a Badgeworks API
server to be reachable. Deploy your own from the Badgeworks `api` branch:

```bash
git clone -b api https://github.com/ArthurSimin/Badgeworks.git
cd Badgeworks
npm install
# generate a key (printed once):
node scripts/manage-keys.js generate
npm start
```

For a stable key that survives restarts and updates, run the server with the env var
instead of `keys.json`:

```bash
BADGEWORKS_API_KEY=<your-key> node server.js
```

## Usage

```bash
python main.py
```

