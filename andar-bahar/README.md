# Andar Bahar — Mobile App (Android APK)

A polished Andar Bahar card game built with React + Vite + TypeScript and wrapped as a
native Android app with **Capacitor**. Plays **offline** with provably-fair local shuffles
(virtual chips), or **online / real-money** when you point it at a backend server.

## Modes
- **Offline (no server URL):** local play, virtual chips, deterministic provably-fair
  shuffle (client seed + nonce). Great for demo/testing.
- **Online (server URL set in ⚙ Settings):** each bet is sent to your FastAPI backend,
  which shuffles, decides the winner, and settles your real wallet. See the backend at
  `rummy/backend/app/andar_bahar/` and endpoint `POST /api/v1/andar-bahar/bet`.

## Build the APK

### Easiest: GitHub Actions (no local Android setup)
Push this repo to GitHub and run the **“Andar Bahar APK”** workflow
(`.github/workflows/andar-bahar-apk.yml`) — from the Actions tab, or it runs on push to
`main`. Download `app-debug.apk` from the run’s **Artifacts**. Install it on any Android
phone (enable “install from unknown sources”).

### Local build (needs Android SDK + JDK 17/21)
```bash
cd andar-bahar
npm install
npm run build          # builds the web bundle into dist/
npx cap sync android   # copies the bundle into the native project
cd android
./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
```
Open in Android Studio instead with: `npx cap open android`.

## Configure the server
In the app, tap ⚙ and enter your backend base URL (e.g. `https://api.yourdomain.com`).
Leave it empty to stay offline. “Save & test” pings `/api/v1/health`.

## Project layout
```
andar-bahar/
├── src/game/         # pure game engine (deck, rng, andarBahar rules) — unit-checked
├── src/services/     # config (Preferences) + server API client
├── src/screens/      # Settings
├── src/components/   # CardView
├── src/App.tsx       # game screen + bet/deal animation
├── capacitor.config.ts
└── android/          # generated native project (build with Gradle)
```

## App identity
`appId: com.swayatra.andarbahar`, `appName: Andar Bahar`. Change these in
`capacitor.config.ts` (and re-run `npx cap sync`) before publishing.
