# Thumbnail Bot

Standalone Telegram bot (Pyrofork) that generates anime thumbnail cards from
AniList data, restricted to an owner + admin list.

## Template behavior

- **Title**: auto-wraps to up to 2 lines and shrinks to fit.
- **Season line**: optional "SEASON X" text under the title (you type it in
  during the flow, or type `skip`). AniList has no reliable "season number"
  field, so this is manual input — same pattern as your other bots'
  undetected-metadata prompts.
- **Background panel**:
  - **With** a season → full blurred/darkened panel (matches the
    Skeleton Knight / Mushoku Tensei style).
  - **Without** a season → lighter background + a rounded gray "chip" sized
    to hug the title+synopsis block (matches the Smoking Behind the
    Supermarket style).
- **Watermark**: bottom-left tag box. Defaults to `@Ongoing_english_dub`,
  overridable via `/watermark <text>` (persisted in MongoDB, global to the
  bot). `/watermark reset` restores the default.

## Commands

| Command | Who | What |
|---|---|---|
| `/thumb <anime name>` | admin/owner | Start the thumbnail flow |
| `/cancel` | anyone | Abort current flow |
| `/watermark [text\|reset]` | admin/owner | View/set/reset the watermark |
| `/addadmin <user_id>` | owner only | Grant admin access |
| `/removeadmin <user_id>` | owner only | Revoke admin access |
| `/admins` | admin/owner | List current owner + admins |

The whole bot (including `/thumb`) is locked to the owner and approved
admins — anyone else gets "This bot is restricted to admins and the owner."

## Flow

1. `/thumb <anime name>` — searches AniList.
2. Pick the correct match from the buttons.
3. Send season text (e.g. `Season 2`) or `skip`.
4. Choose artwork source:
   - **Auto-fetch** — uses AniList's cover image (background + poster) and
     banner image (circle inset). No uploads needed.
   - **Provide 3 images** — send background, poster, and circle-inset images
     one at a time.
5. Bot composites the final 1280x720 PNG and sends it back.

## Setup (Codespaces or local)

```bash
pip install -r requirements.txt
cp .env.sample .env
# fill in API_ID, API_HASH, BOT_TOKEN (my.telegram.org / @BotFather)
# set OWNER_ID to your own Telegram user ID
# set MONGO_URI (Atlas free tier works fine)
python bot.py
```

The owner ID is set via `.env` — no command needed for the owner. Add
further admins after startup with `/addadmin <user_id>`.

## Deploying (Render free tier)

`Dockerfile` is included, same pattern as your Auto-Rename-Bot. Set the env
vars from `.env.sample` in Render's dashboard.

## Customizing the layout

Positioning/sizing constants (panel widths, circle diameter, font sizes,
colors, chip radius, dot-grid spacing) live at the top of `thumbnail_gen.py`.

Fonts: Poppins (Bold / SemiBold / ExtraBold) in `fonts/`.

## Not included yet (flagged, not built)

- **Manual edit Mini App** (drag layers, crop handles, text editing) — this
  is a separate web-app build (canvas UI + hosting + Telegram WebApp
  handshake) on top of this bot. Say the word when you're ready and I'll
  scope that out separately.
- Multi-instance-safe session state — flow state is in-memory per user
  and resets on restart/`/cancel`. Fine for a single bot instance.
