# Registering this app in the App Launcher

The launcher reads `launcher.json` at the repo root. It understands **only** these
fields — anything else is ignored and the app won't start:

```json
{
  "name": "Visible app name",
  "description": "One line of what it does.",
  "processes": [
    { "name": "backend", "cmd": "<exact cmd, with {PLACEHOLDER} for the port>" }
  ],
  "ports": [ { "name": "PORT_API", "preferred": 8001 } ],
  "open": "http://localhost:{PORT_API}/"
}
```

## Rules

- `processes` is an **array**, not an object. Use `cmd` (not `command`). Each
  `cmd` runs in order.
- Ports are written with braces: `{PORT_API}`. **Not** `${VAR}` or `%VAR%`. Every
  name in braces must be declared in `ports`.
- Declare each port in `ports`. `preferred` is honored if free; otherwise the
  launcher picks another and substitutes the real value everywhere the placeholder
  appears (`cmd`, `env`, `open`).
- A process running in a subfolder needs `"cwd": "web"` (relative, never absolute).
- Do **not** use `services`, `placeholders`, `dependsOn`, `command`, `url`,
  `port`, or any other field — the launcher ignores them.

## Why this app's `launcher.json` looks the way it does

- **One process.** The FastAPI backend ([app/serve.py](../app/serve.py)) serves both
  the API and the web UI on the same port — there is no separate frontend, so there
  is only a `backend` process and `open` points at its port.
- **`{PORT_API}` preferred 8001.** Matches the port the README documents
  (`--port 8001`); `app.serve` also defaults to 8001.
- **`ITF_CHROMIUM_PATH` in `env`.** On this machine the renderer uses the system
  Google Chrome (Playwright's browser dir is empty). Without it, startup fails with
  *"Executable doesn't exist at ...chrome-headless-shell.exe"*. See the README's
  *Using a Chromium you already have*. If a machine ran `playwright install chromium`,
  this env var can be dropped.

## Prerequisite

`launcher.json` assumes the `.venv` already exists (see README **Setup**). The
launcher does not create it — run the setup steps once before launching.
