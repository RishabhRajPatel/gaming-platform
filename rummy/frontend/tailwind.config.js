/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Height-based breakpoint (Tailwind only ships width-based ones by default) —
      // targets real Android phones in landscape, where width is generous but height
      // is often under ~420px, so the action bar needs to fit without scrolling.
      screens: {
        short: { raw: "(max-height: 480px)" },
      },
      colors: {
        // Premium dark gaming palette
        felt: {
          900: "#0b1f17",
          800: "#0f2a1e",
          700: "#143a29",
        },
        gold: {
          400: "#e8c37a",
          500: "#d4af37",
          600: "#b8912b",
        },
        ink: {
          950: "#0a0c10",
          900: "#0f1218",
          800: "#161b24",
          700: "#1f2733",
        },
      },
      fontFamily: {
        display: ["'Poppins'", "system-ui", "sans-serif"],
        body: ["'Inter'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 6px 20px rgba(0,0,0,0.45)",
        glow: "0 0 24px rgba(212,175,55,0.25)",
      },
    },
  },
  plugins: [],
};
