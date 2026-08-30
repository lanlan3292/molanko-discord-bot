# Molanko Discord Bot

[简体中文](./README.zh-CN.md)

---

## 1. Clone the repository

```bash
git clone --depth 1 --branch main https://github.com/lanlan3292/molanko-discord-bot.git
cd molanko-discord-bot
mv cogs/screenshot_web.py cogs/screenshot_web.py.disabled
```

## 2. Install dependencies

```bash
python -m venv .venv
source .venv/Scripts/activate

python -m pip install -r requirements.txt

npm ci
# If you run into problems, you can try npm install instead.
# If the problem persists, please report it.
```

## 3. Configuration (required)

Copy `.env.example` to `discord_bot.env` and fill in your Discord bot token:

```bash
cp .env.example discord_bot.env
# then edit discord_bot.env
```

* `TOKEN` — your Discord bot token

## 4. Configure Badgeworks (optional)

**Important:** Badgeworks is **not** a Molanko ecosystem project and is not controlled by lanlan3292. It may have issues that are outside the control of this project.

If you do not need Badgeworks, you can disable the cog and skip to step 5:

```bash
mv cogs/badge.py cogs/badge.py.disabled
```

If you do use Badgeworks, configure the following variables:

* `BADGEWORKS_API_URL` — URL of the Badgeworks API server (default `http://localhost:8080`)
* `BADGEWORKS_API_KEY` — API key for the server

Only the `/badge` command requires a Badgeworks API server.

### Badge command (`/badge`)

Generates a [Devins Badge](https://github.com/intergrav/devins-badges) via the [Badgeworks API](https://github.com/ArthurSimin/Badgeworks/tree/api) and posts it as a PNG attachment together with the SVG source.

The command requires `BADGEWORKS_API_URL` and `BADGEWORKS_API_KEY` to be set, and the bot must be able to reach a Badgeworks API server. You can deploy your own server from the Badgeworks `api` branch:

```bash
git clone -b api https://github.com/ArthurSimin/Badgeworks.git
cd Badgeworks
npm install
# Generate a key (printed once):
node scripts/manage-keys.js generate
npm start
```

For a stable key that survives restarts and updates, run the server with the environment variable instead of relying on `keys.json`:

```bash
BADGEWORKS_API_KEY=<your-key> node server.js
```

## 5. Start the bot

```bash
python main.py
```
