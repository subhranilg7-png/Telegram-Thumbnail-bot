# Telegram Thumbnail Bot + Mini App Editor

This version keeps the existing AniList/manual 3-image workflow and adds a Telegram Mini App editor. The visual target is the supplied Canva/PDF examples: full-bleed artwork, adaptive dark translucent left treatment, overlapping circle inset, white ring, watermark, dots and bottom-right title.

## Features
- `/thumb <anime name>`: AniList search and selection.
- Optional season text.
- Auto-fetch artwork from AniList or provide 3 images manually.
- Generates a 1280x720 PNG.
- `✏️ Edit thumbnail` opens a Telegram Mini App.
- Mini App controls: title/synopsis/season, circle zoom/position/size, background/poster zoom, overlay/panel opacity, title/synopsis vertical positions.
- Export PNG, PDF, PPTX from the Mini App.
- PPTX uses separate editable image/text/shape layers where practical; PDF is a high-quality export, not a fully native Canva document.
- Owner/admin access and MongoDB persistence are retained.

## Important: Telegram Mini App URL
Set `WEBAPP_URL` to the **public HTTPS URL** of this service. On Render, if the service is `https://my-thumbnail-bot.onrender.com`, set `WEBAPP_URL=https://my-thumbnail-bot.onrender.com`.

Telegram will not open an ordinary `http://localhost` Mini App in production. For local testing use an HTTPS tunnel such as Cloudflare Tunnel/ngrok, then set `WEBAPP_URL` to that HTTPS URL.

## Environment
See `.env.sample`. Required: `API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`, `MONGO_URI`. For the editor: `WEBAPP_URL`, optionally `WEBAPP_HOST=0.0.0.0`, `WEBAPP_PORT=8080`.

## Run
```bash
pip install -r requirements.txt
cp .env.sample .env
python bot.py
```

## Architecture
```
AniList / 3 uploads
        ↓
   project state
        ↓
   Pillow renderer
        ↓
      PNG
        ↓
 Telegram Mini App
        ↓
 project state changes
        ↓
 PNG / PDF / PPTX
```

The editor does not paint directly onto a PNG. It changes layout state and re-renders, so undo/reset and future exporters remain possible.
