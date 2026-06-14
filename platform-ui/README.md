# Platform UI (CodeForge IDE)

The high-fidelity, browser-native IDE for the Scalable Challenge Platform.

## Tech Stack
- **Framework:** React 18+
- **Build Tool:** Vite
- **Core Engine:** WebContainers (WASM Node.js)
- **Styling:** Tailwind CSS + Split.js

## Key Features
*   **WASM-Native IDE:** Runs real Node.js and SQLite (`sql.js`) environments directly in the browser.
*   **Viewport-Locked Layout:** Professional "clean" IDE experience with resizable panels.
*   **Background Preparation:** Dependencies (`npm install`) trigger automatically on boot to minimize wait time.
*   **Resilient Hot-Patching:** Automatically migrates legacy challenge code to browser-compatible WASM logic on-the-fly.
*   **Continuous Save:** Auto-saves user work to the backend every 2 seconds.

## Development

### Setup & Requirements
This application requires specific security headers to enable SharedArrayBuffer (needed for WebContainers):
- `Cross-Origin-Embedder-Policy: require-corp`
- `Cross-Origin-Opener-Policy: same-origin`

These are pre-configured in the `vite.config.ts` for local development and `nginx.conf` for Docker.

### Run Locally
```bash
npm install
npm run dev
```

### Build for Production
```bash
docker compose up --build ui
```

## Troubleshooting
- **Dependencies Not Loading:** Check the terminal for background installation logs. Ensure your network allows access to the npm registry.
- **Scrollbar Issues:** The IDE is designed to fit the viewport. If you see global scrollbars, ensure the parent container hasn't been modified with `min-h-screen`.
- **WASM Bindings:** If you encounter `better-sqlite3` errors, click the **"Reset to Boilerplate"** button in the header to apply the latest WASM hot-patch.
