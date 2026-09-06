# Fantasy Football Manager

A draft room for the Succession Plan that runs on the projection and value over replacement intelligence from [jjti/ff](https://github.com/jjti/ff), the code behind [ffdraft.app](https://www.ffdraft.app/). That project is copied into this repo as is. There is no fork relationship or branch tracking back to it.

## What is here

| Folder | What it does |
| --- | --- |
| `league/` | The draft room. Your league config, the build script, and the styled HTML page. |
| `data/` | The ffdraft.app scrape and aggregate pipeline. Pulls CBS, ESPN and NFL projections plus FantasyPros ADP. |
| `app/` | The original ffdraft.app Next.js app. Kept intact and untouched, useful as a second opinion on VOR. |

## Quick start

```
make league        # builds league/league_data.js from data/processed/Projections-2026.json
make serve         # same, then opens the draft room on http://localhost:8000
```

You can also open `league/index.html` straight from the file system once `league_data.js` exists. The generated file is committed so the page works right after cloning.

## Hosted draft room

`.github/workflows/pages.yaml` publishes the `league/` folder to GitHub Pages on every push to `main` and again after each scheduled data refresh. The page lands at `https://c4c-innovationslab.github.io/fantasy-football-manager/`.

One time setup. In the repo go to Settings, then Pages, and set Source to GitHub Actions. Until that is set the deploy job will fail with a message saying Pages is not enabled.

## How the pieces connect

1. `data/main.py` scrapes the three projection sources and ADP into `data/raw`, then `data/aggregate.py` averages them into `data/processed/Projections-<year>.json`. That file has raw stat lines per player, things like passing yards, receptions and rushing touchdowns.
2. `league/build.py` reads that file, applies the scoring in `league/config.json` to turn stat lines into season points, computes value over replacement using the same method as ffdraft.app, attaches ADP, and writes `league/league_data.js`.
3. `league/index.html` loads `league_data.js` with a script tag and renders the draft board, your plan, and the roster builder.

Every number the draft room shows comes from steps 1 and 2. Nothing is hardcoded in the HTML any more.

## League config

Everything about your league lives in `league/config.json`.

- `teams`, `draft_order`, `my_team` drive the pick clock and your pick numbers. The order is 15 rows of 12 team codes.
- `lineup` and `roster_goal` drive the roster panel and the build view.
- `scoring` is the stat multiplier table. It uses the same field names as the pipeline. Passing touchdowns are set to five and receptions to half a point. Check both against the league host settings before draft day, since they change every projection and the VOR ranking.
- `watch`, `avoid`, `tiers`, `tier_adp_cutoffs` are your lists. Tiers are assigned by ADP cutoff on first load and can be reordered in the browser.
- `plan` is one entry per pick you own with targets in order and the reasoning shown in the recommendation box.

Rebuild after any change with `make league`.

## ADP sources

The board prefers the ADP from your league host when a player is in `league/host_snapshot.csv`. That file is the export from the host draft room. Players not in it fall back to FantasyPros ADP from the pipeline, and players in neither show as undrafted. Hover over an ADP cell to see which source it came from. Set `adp.prefer_host_snapshot` to false in the config to use FantasyPros only.

To refresh the host numbers, replace `host_snapshot.csv` with a new export in the same five columns and rebuild.

## Refreshing projections

`make data` runs the full scrape. It needs Chrome for the Selenium pieces. The scheduled workflow in `.github/workflows/data.yaml` does the same every four hours during draft season and commits the refreshed data and `league_data.js` back to the repo. Trigger it by hand from the Actions tab any time.

The S3 upload and the Next.js deploy from the original project are still present but only run when AWS secrets are set, so nothing will fail without them.

## Value over replacement

VOR is a player's projected points minus the points of the best player at that position who would be left on waivers once every team has filled its starters. The README from the original project explains the reasoning in detail. In this league that means 12 quarterbacks, 36 running backs, 48 receivers and 12 tight ends come off the board before replacement level. Kickers and defenses are always treated as replaceable.

The draft board sorts by ADP and shows VOR next to projected points. The best available panel on the right sorts by VOR, and the recommendation box names the single best value on the board so you can weigh it against the plan target.
