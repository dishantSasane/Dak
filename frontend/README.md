# Dak frontend

React 18, TypeScript and Vite. From this directory:

```sh
npm ci
npm run dev
npm run build
npx playwright install chromium
npm run test:browser
```

Vite listens at http://127.0.0.1:5173 and proxies `/api` to the FastAPI server at http://127.0.0.1:8000. Direct navigation uses SPA fallback. A deployed host must serve `index.html` for application routes and proxy `/api` to the backend.

All screens use real API requests. Browser regression tests intercept synthetic responses to verify responsive rendering, accessibility, citations, submission payloads and review actions without model quota. These fixtures are test-only and never populate the application. System preference selects light/dark themes.
