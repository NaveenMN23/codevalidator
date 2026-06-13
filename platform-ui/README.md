# Platform UI

The browser-based IDE and administrative dashboard for the Scalable Challenge Platform.

## Tech Stack
- **Framework:** React 18+
- **Build Tool:** Vite
- **Core Technology:** WebContainers (for in-browser code execution)
- **Language:** TypeScript
- **Styling:** CSS Modules

## Key Features
- **File Explorer:** Navigation for challenge source code.
- **Integrated Terminal:** Real-time terminal access via WebContainers.
- **Live Preview:** Immediate feedback for changes made to the challenge code.

## Development

### Setup
```bash
npm install
```

### Run
```bash
npm run dev
```

### Build
```bash
npm run build
```

## Security
This application utilizes WebContainers, which requires specific security headers (`Cross-Origin-Embedder-Policy: require-corp` and `Cross-Origin-Opener-Policy: same-origin`). When deploying, ensure these headers are served by your web server (the provided `nginx.conf` handles this in the Docker build).

