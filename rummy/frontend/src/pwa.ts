import { registerSW } from "virtual:pwa-register";

// A stale installed app/tab is the #1 cause of "I fixed it but you still see the old
// bug" — the service worker updates itself in the background, but a tab that's
// already open (or an installed APK that's just resumed, never fully closed) keeps
// running the JS it already loaded. Reload automatically the moment a new version
// is ready instead of waiting for the user to manually close and reopen.
export function initPWAUpdates(): void {
  registerSW({
    immediate: true,
    onNeedRefresh() {
      window.location.reload();
    },
  });
}
