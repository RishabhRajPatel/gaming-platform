import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // Only the app shell (JS/CSS/HTML/icons) is precached. /api and /ws are never
      // listed here and get no runtimeCaching entry below, so the service worker
      // never intercepts or caches live game state, cards, scores, turns, or the
      // WebSocket handshake — every request for those still hits the network fresh.
      includeAssets: ["icon-192.png", "icon-512.png"],
      manifest: {
        name: "Rummy",
        short_name: "Rummy",
        description: "Real-money Deals Rummy — play live 13-card rummy online.",
        display: "standalone",
        orientation: "landscape",
        theme_color: "#0b1f17",
        background_color: "#0b1f17",
        start_url: "/lobby",
        scope: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Precache the built app shell only.
        globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
        // Belt-and-suspenders: even the SPA navigation fallback must never swallow
        // API or WebSocket-upgrade requests.
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
