# Telegram Anime Thumbnail Bot — Ongoing English Dub design

This version uses the selected 1280x720 anime-info design.

## Artwork slots
1. Main/background artwork — full canvas, also used to extract the accent colour.
2. Top horizontal artwork.
3. Small card artwork 1.
4. Small card artwork 2.

Auto mode uses AniList banner/cover artwork when additional sources are unavailable. Manual mode accepts four Telegram photo uploads.

## AniList fields
The renderer receives title, Romaji subtitle, synopsis, average score, genres, season and season year from AniList. AniList scores are converted from `0–100` to `0–10` (e.g. `86` -> `8.6/10`). Season/year is rendered as `SPRING 2019`, etc.

## Dynamic colour
The accent colour is automatically extracted from image 1. It controls the borders, pills, season badge, dividers, decorative accents and branding highlights.

## Fixed design rules
- 1280x720 output.
- No `FRIDAY` label.
- `@Ongoing_english_dub` branding.
- Semi-transparent dark right information panel.
- Top horizontal rounded image.
- Two rounded image cards.
- Synopsis and rating on the left.
- Season/year above the right panel.
- No duplicate bottom-right title.

## Exports
PNG, PDF and PPTX are supported. PNG/PDF/PPTX use the same final rendered composition for visual fidelity. The Telegram Mini App remains the editable control surface for text, image crops and layout settings.
