# Teen Patti (3 Patti)

The platform's third game — 4-player Teen Patti (3-card poker).

## Pieces
- **Playable game** — `web/teen-patti.html`: a full, self-contained 4-player game
  (you vs 3 bots) with the exact ranking, blind/seen play, chaal, raise, side show,
  show, 15s turn timer, and the 30s-wait → 3s-countdown table start. Landscape UI.
  Open it in any browser. `web/teen-patti-simple.html` is a lighter earlier variant.
  `web/index.html` is the same game as `teen-patti.html`, packaged as the Capacitor
  app's entry point — build an Android APK from it via the steps below.
- **Engine + API** — `rummy/backend/app/teen_patti/`: pure-Python deck, deal, hand
  evaluation and comparison, a one-shot wallet-settled bet endpoint
  (`POST /api/v1/teen-patti/play-hand`), and a real-time server-authoritative
  WebSocket table (`/ws/teen-patti/{table_id}`) — same shuffle/hand-eval logic reused
  by both. Unit- and integration-tested in `rummy/backend/tests/test_teen_patti.py`
  and `test_teen_patti_ws.py`. The bots-only browser game above doesn't call this API
  yet — it's still fully offline/client-side.

## Build the APK

### Easiest: GitHub Actions (no local Android setup)
Push this repo to GitHub and run the **"Teen Patti APK"** workflow
(`.github/workflows/teen-patti-apk.yml`) — from the Actions tab, or it runs on push to
`main`. Download `app-debug.apk` from the run's **Artifacts**. Install it on any
Android phone (enable "install from unknown sources").

### Local build (needs Android SDK + JDK 17/21)
```bash
cd teen-patti
npm install
npx cap sync android   # copies web/ (index.html) into the native project
cd android
./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
```
Open in Android Studio instead with: `npx cap open android`.

There's no bundler here — `web/index.html` is a dependency-free single file, so
`cap sync` copies it straight into the native project, no build step in between.

## Hand ranking (highest first)
1. **Trail / Trio** — AAA … 222
2. **Pure Sequence** — same suit consecutive: A-K-Q > **A-2-3** > K-Q-J > … > 4-3-2
3. **Sequence** — consecutive, mixed suits
4. **Color** — same suit, not consecutive
5. **Pair**
6. **High Card**

## Table rules
Boot ₹10 each into the pot. Play **blind** (bet = stake) or **See** your cards and play
**chaal** (2× stake). **Raise** doubles the stake. **Side Show** compares with the
previous seen player. When two remain, **Show** decides the winner; best hand takes the
pot. Turn timer 15s → auto-pack. Empty seats are filled by bots so the table is always
4-handed.

## Multiplayer (next step)
For real online multiplayer, drive this engine from a WebSocket server exactly like the
Deals Rummy table (`rummy/backend/app/websocket/`): the server owns shuffle, turns,
timers, bets, side-show/show and pot; clients only render server state.
