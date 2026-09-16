import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['**/*.test.{ts,tsx}'],
    // Pin NODE_ENV for the test run. Vitest only defaults it when it is unset,
    // so an ambient NODE_ENV=production (a normal value in a developer shell)
    // makes `react` resolve its production build, which does not export `act`.
    // Every @testing-library/react render then dies with
    // "React.act is not a function" and the whole UI suite looks broken.
    env: {
      NODE_ENV: 'test',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
