import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.swayatra.andarbahar",
  appName: "Andar Bahar",
  webDir: "dist",
  android: {
    // Allow cleartext so a self-hosted http:// dev backend works during testing.
    // For production use https and set this to false.
    allowMixedContent: true,
  },
};

export default config;
