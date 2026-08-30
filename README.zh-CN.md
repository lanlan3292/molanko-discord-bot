# Molanko Discord Bot

[English](./README.md)

1. 拉取仓库

```bash
git clone --depth 1 --branch main https://github.com/lanlan3292/molanko-discord-bot.git
cd molanko-discord-bot
mv cogs/screenshot_web.py cogs/screenshot_web.py.disabled
```

2. 安装库

```bash
python -m venv .venv
source .venv/Scripts/activate

python -m pip install -r requirements.txt

npm ci
# 如果存在一些问题你可以尝试npm install 如果仍然存在一些问题请反馈
```

## 配置

将 `.env.example` 复制为 `discord_bot.env` 并填写你的值：

```bash
cp .env.example discord_bot.env
# 然后编辑 discord_bot.env
```

* `TOKEN` — 你的 Discord 机器人令牌（必需）
* `BADGEWORKS_API_URL` — Badgeworks API 服务器的 URL（默认 `http://localhost:8080`）
* `BADGEWORKS_API_KEY` — 该服务器的 API 密钥

这两个 `BADGEWORKS_*` 变量都是可选的。机器人没有它们也能运行；只有 `/badge` 命令需要 Badgeworks API 服务器。

## Badge 命令（`/badge`）

通过 [Badgeworks API](https://github.com/ArthurSimin/Badgeworks/tree/api) 生成 [Devins Badge](https://github.com/intergrav/devins-badges)，并以 PNG 附件和 SVG 源码形式发布。

需要设置 `BADGEWORKS_API_URL` 和 `BADGEWORKS_API_KEY`，并且能够访问 Badgeworks API 服务器。从 Badgeworks 的 `api` 分支部署你自己的服务器：

```bash
git clone -b api https://github.com/ArthurSimin/Badgeworks.git
cd Badgeworks
npm install
# 生成一个密钥（仅打印一次）：
node scripts/manage-keys.js generate
npm start
```

如需在重启和更新后保留稳定的密钥，请使用环境变量运行服务器，而不是使用 `keys.json`：

```bash
BADGEWORKS_API_KEY=<你的密钥> node server.js
```

## 使用方法

```bash
python main.py
```
