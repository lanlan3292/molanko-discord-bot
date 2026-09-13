# Molanko Discord Bot

Molanko Discord Bot is a Discord.py-based bot that includes a few non-essential features.

[简体中文](./README.zh-CN.md)

## Use

### 1. Clone the repository

```bash
git clone --depth 1 --single-branch --branch main https://github.com/lanlan3292/molanko-discord-bot.git
cd molanko-discord-bot
mv cogs/screenshot_web.py cogs/screenshot_web.py.disabled
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt

npm ci
# If you run into problems, you can try npm install instead.
# If the problem persists, please report it.
```

### 3. Configuration (required)

Copy `.env.example` to `discord_bot.env` and fill in your Discord bot token:

```bash
cp .env.example discord_bot.env
# then edit discord_bot.env
```

* `TOKEN` — your Discord bot token

### 4. Badge command (`/badge`)

**Important:** Badgeworks is **not** a Molanko ecosystem project and is not controlled by lanlan3292. It may have issues that are outside the control of this project.

If you do not need the badge command, you can disable the cog:

```bash
mv cogs/badge.py cogs/badge.py.disabled
```

The `/badge` command generates a [Devins Badge](https://github.com/intergrav/devins-badges) locally and posts it as a PNG attachment together with the SVG source. Badges are rendered by the vendored [Badgeworks](https://github.com/ArthurSimin/Badgeworks) core (`badgeworks/`, no external server or API key required).

It renders through Node.js (`scripts/badge.mjs`), so it needs the Node dependencies installed (done by `npm ci` in step 2). No additional configuration is needed.

Start with the two required text fields, then type in `icon` to search every bundled preset/Simple Icon. Examples:

```text
/badge top_text:"Available on" bottom_text:"GitHub" icon:github
/badge top_text:"Built with" bottom_text:"Python" icon:python style:compact
/badge top_text:"Plain" bottom_text:"Text badge" logo_position:None
/badge top_text:"Powered by" bottom_text:"Font Awesome" fontawesome_icon:"fa-brands fa-discord"
/badge top_text:"From" bottom_text:"theSVG" thesvg_slug:docker
/badge top_text:"Created with" bottom_text:"My Logo" image:<upload a PNG/SVG>
```

`icon` uses the local bundled icon list. Supplying `fontawesome_icon`, `thesvg_slug`, or an `image` attachment automatically selects that source, so `icon_mode` is optional. Upload an image (PNG/JPG/SVG) via the `image` parameter to use it as the badge logo. If `icon_mode` is supplied, it must match the single source-specific field; conflicting source fields are rejected. Choose `logo_position:None` for no icon.

### 5. Start the bot

```bash
python main.py
```
