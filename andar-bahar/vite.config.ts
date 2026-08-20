import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" is REQUIRED so assets load over file:// inside the Android APK.
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { port: 5174 },
});
