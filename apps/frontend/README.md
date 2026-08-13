# ARK NEXUS X — Frontend

React + TypeScript + Vite UI for the ARK NEXUS X desktop shell.

## Panels

The UI provides 12 panels covering the core subsystems: dashboard, macro studio, agent framework, vision pipeline, scheduler, scripting (NexusScript), decision engine, device integration, marketplace, model runtime, self-improvement, and configuration.

## Development

```bash
npm ci
npm run dev       # Vite dev server with HMR
npm run build     # tsc -b && vite build
npm run lint      # oxlint
npm run preview   # preview the production build
```

## IPC

The frontend talks to the Tauri/Rust shell over typed commands and events. During frontend-only development it runs against a mock IPC layer so panels can be built and verified without the native shell.
