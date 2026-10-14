# nflsignal-scheduler

A Cloudflare Worker that starts Workflow 3 (market update) on time.

GitHub's scheduled workflows started this one 2–8 hours late during the 2026
season, so the Sunday 12:30 PM ET run usually landed after the 1:00 kickoffs and
the Thursday run after TNF. Cloudflare cron triggers fire on time.

The Worker runs every 15 minutes (Aug–Feb), checks the current Eastern time
against `SLOTS` in `src/index.js`, and dispatches Workflow 3 with the stage set
explicitly. Workflow 3's own cron stays as a backup and skips itself when a
dispatched run started in the previous 8 hours.

| ET | Stage |
|---|---|
| Tue 4:00 PM | update |
| Wed 9:00 AM | opening |
| Thu 2:00 PM | pre_tnf |
| Sat 9:00 PM | update |
| Sun 8:30 AM | lock |
| Sun 12:30 PM | final |
| Mon 6:00 PM | pre_mnf |

## One-time setup

1. Create a GitHub fine-grained personal access token with access to
   `whatsaliju/nfl-betting-automation` only and the permission
   **Actions: Read and write**.
2. Deploy and store the token:

   ```sh
   cd scheduler
   npx wrangler login
   npx wrangler deploy
   npx wrangler secret put GITHUB_TOKEN
   ```

3. Confirm at the next slot with `npx wrangler tail`. It logs
   `Dispatched 3_market_update.yml stage=...`.

To change a time, edit `SLOTS` and run `npx wrangler deploy` again. Keep
times on a :00/:15/:30/:45 boundary.
