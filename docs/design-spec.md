# Ripple design spec (from the concept art)

Every value below is taken from `design/reference/free-flow.html` and
`design/reference/suez-blocked.html`. Build to these numbers.

## Layout

- Desktop frame: map area 1440 × 810, side panel 400 wide on the right
  (total 1840 × 810). The map scales to fill the window; the panel stays 400.
- Below 900 px wide, the panel becomes a bottom sheet over the map.
- Map projection: equirectangular, cropped to the area in view. Coastlines and
  borders come from Natural Earth (1:50m), not hand-drawn shapes.

## Colors

### Map and panel

| Role | Hex |
|---|---|
| Ocean (page ground) | #132423 |
| Land | #1F3936, stroke #2C4C47 at 1 px |
| Highlighted land (China, India, shock country) | #28524B |
| Panel background | #0E1A19, left border #27443F at 1 px |
| Primary text | #F1F5F2 |
| Body text in panel | #D5DFDC |
| Secondary text | #B9C7C3 |
| Section headings in panel | #8FA6A1 |
| Light label pill | #E9EEEA with text #132423 |

### Tier colors (nodes and the routes carrying that tier's output)

| Tier | Hex |
|---|---|
| 1 Rocks and mining | #C79A6B |
| 2 Base materials | #E8662F |
| 3 Components | #A98BE8 |
| 4 Assembly (and finished devices in transit) | #46C6D8 |
| 5 Shipping nodes (ports, canals, crossings) | #E9EEEA (dots drawn #F1F5F2) |
| 6 Sales | #7CCB9A |
| 7 Support and repair (and returns) | #F08CC0 |

### Reserved (never used for tiers)

| Meaning | Fill | Rim | Text |
|---|---|---|---|
| Gold coin: revenue | #F2B92B | #9A6A06 | #6B4704 |
| Blue coin: spend | #5AA0E6 | #1F5E9E | #0E2F52 |
| Red coin: lost sales, and all disruptions | #D6453D | #8E1F19 | #FFFFFF |
| Grey coin: delayed sales | #8A9694 | #4E5958 | #1D2524 |

Disruption zone: circle fill rgba(214,69,61,0.22), 2 px dashed #D6453D border.

## Type

- Interface font: **Archivo** (Google Fonts, variable width 62–125, weight 400–800).
- Arcade font: **Pixelify Sans** 500/700, only for coins, the year tag, and
  coin counters.
- Small label pill: 12 px, weight 700, width 85%, letter-spacing 0.04em,
  uppercase, padding 4 × 9, radius 7.
- Big label pill: 19 px, weight 800, width 80%, letter-spacing 0.05em,
  uppercase, padding 8 × 16, radius 12.
- Year tag: Pixelify Sans 46 px bold, bottom-left (24, 712); the slash is
  #46C6D8. Subtitle under it: Archivo 13 px, weight 600, #B9C7C3.
- Panel title "Ripple": 30 px, weight 800, width 90%.
- Panel section headings: 12 px, weight 700, letter-spacing 0.06em, uppercase.

## Node symbols

| Kind | Symbol | Size |
|---|---|---|
| Assembly factory | Hexagon, tier-4 fill, 2 px ocean outline, small factory glyph inside | 26 |
| Major supplier | Filled triangle, tier color | 24 |
| Smaller supplier | Outlined triangle, 2 px tier color | 16 |
| Port, canal, crossing | White dot with 3 px ocean border | 14 |
| Apple Store | Filled green square, radius 3 | 18 |
| Other retailer | Outlined green square, 3 px border | 18 |
| Phone carrier | Green dot with two signal arcs | 24 |
| Apple Park HQ | Text card "APPLE PARK / CUPERTINO", 2 px #E9EEEA border, radius 10 | 112 wide |

Every node has both a shape and a color, so color is never the only cue.

## Routes

| Route | Style |
|---|---|
| Sea | 7 px tier-colored line, round caps, smoothed, with a 2 px ocean-colored tick overlay (dash 3, gap 15) |
| Air | Dotted arc, dash 2 gap 7, round caps; 1.6 px normally, 3 px when expedited |
| Road | Solid tier-colored line with a thin ocean-colored center stripe |
| Rail | Tier-colored line with short perpendicular crossties |
| Detour | 5 px, dash 14 gap 9 |
| Blocked or unused | Grey #7E8C89 at 35% opacity |
| Money in (revenue) | Gold #F2B92B, 2.5 px |
| Money out (spend) | Blue #5AA0E6, 3 px |
| Inferred link | Dashed version of its normal style |

## Coins and ships

- Coin: 24 px circle (20 in legends), 2 px rim, inset shadow 0 -3 px in the
  rim color, "$" in Pixelify Sans bold at half the coin size.
- Lost coin: red, with a dark crack line, rotated and fading as it falls off the route.
- Delayed coins: grey, stacked with a 7 px vertical offset.
- 1 coin = a fixed dollar amount, shown in the panel legend.
- Ship: 30 × 16 original icon, white hull, two tier-4 containers. Blocked ship
  is rotated across the canal; queued ships bunch up before the blockage.

## Motion

- One orchestrated moment: when a disruption drops, the shock zone appears,
  then routes beyond it grey out, then coins change state.
- Ships and coins travel along their routes continuously at a slow pace.
- With `prefers-reduced-motion`, nothing travels; items sit at fixed positions.

## Side panel

Free flow: title + sample tag, status line, quota bar (20 blocks, gold when
filled), money key (2 columns), map key (2 columns), tier color key
(4 columns), full-width "Drop a disruption" button (#E9EEEA, 48 px tall).

Disruption: title + sample tag, then four sections in this order:
What's wrong, What's affected (bars in red, dashed for low confidence, with
the score), What can be shifted (checkboxes, accent #46C6D8), Will we meet
quota? (dashed gold quota line, grey no-action line, green with-plan line, red
shaded gap, and one sentence with the recovery estimate).
