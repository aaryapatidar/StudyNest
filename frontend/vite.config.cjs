const { defineConfig, loadEnv } = require('vite');
const react = require('@vitejs/plugin-react');

module.exports = defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
            target: (env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '').replace(/\/api$/, '') || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  };
});