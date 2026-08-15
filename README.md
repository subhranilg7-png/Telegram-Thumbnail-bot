# Telegram Thumbnail Bot + Mini App Editor

Updated renderer for the selected Ongoing English Dub anime design.

## Design rules
- 1280x720 master output; renderer supports 2x rendering for high-quality PDF export.
- Four images: main background, top horizontal image, small card 1, small card 2.
- AniList supplies title, subtitle/romaji title, synopsis, rating, season + year, and genres.
- The `FRIDAY` label is removed.
- Branding is `@Ongoing_english_dub` by default.
- Accent colour is automatically extracted from the main background image and applied to borders, pills, decorations, rating, season badge, panel accents and branding.
- Right information card is a dark semi-transparent/frosted-style panel.
- PNG, PDF and editable-ish PPTX exports are available from the Mini App.

## Artwork flow
`/thumb <anime>` → AniList match → choose Auto-fetch or provide 4 images manually.

Auto-fetch uses AniList banner/cover assets and sensible fallbacks. Manual mode asks for exactly four images.

## Environment
Required: `API_ID`, `API_HASH`, `BOT_TOKEN`, `OWNER_ID`, `MONGO_URI`.
Mini App: `WEBAPP_URL`, optionally `WEBAPP_HOST` and `WEBAPP_PORT`.
