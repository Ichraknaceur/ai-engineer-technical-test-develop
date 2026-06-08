import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL is injected at build/run time via VITE_API_URL.
// In Docker Compose it points to the backend service; locally it falls
// back to http://localhost:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
  },
});
