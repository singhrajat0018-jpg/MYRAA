import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["tests/**/*.test.ts", "tests/**/*.spec.ts"],
    exclude: ["tests/**/*.py", "node_modules", "dist"],
    testTimeout: 15000,
    hookTimeout: 10000,
    reporters: ["verbose"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["server_voice.ts", "server_conversations.ts", "server_memory.ts"],
    },
  },
});
