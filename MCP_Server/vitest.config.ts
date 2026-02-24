import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["packages/**/src/**/*.test.ts", "apps/**/src/**/*.test.ts"],
    exclude: ["**/dist/**", "**/node_modules/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["packages/**/src/**/*.ts", "apps/**/src/**/*.ts"],
      exclude: ["**/*.test.ts", "**/dist/**"],
    },
    testTimeout: 10_000,
    // Faster fake timers for TTL tests
    fakeTimers: {
      shouldAdvanceTime: false,
    },
  },
});
