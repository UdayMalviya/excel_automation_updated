# Browser Automation Platform

Production-ready browser automation platform with:

- FastAPI backend
- Playwright automation
- React + Vite frontend
- Visible browser session via Xvfb + x11vnc + noVNC
- Docker Compose development workflow with hot reload

## Project structure

```text
.
├── backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── start.sh
│   └── src
│       ├── api
│       │   ├── app.py
│       │   └── main.py
│       ├── core
│       │   └── config.py
│       ├── schemas
│       │   └── task.py
│       ├── services
│       │   └── playwright_service.py
│       └── utils
│           └── logger.py
├── docker-compose.yml
└── frontend
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── src
    │   ├── App.jsx
    │   ├── components
    │   │   ├── ControlPanel.jsx
    │   │   ├── LogsPanel.jsx
    │   │   └── VNCViewer.jsx
    │   ├── main.jsx
    │   ├── pages
    │   │   └── Dashboard.jsx
    │   ├── services
    │   │   └── api.js
    │   └── styles.css
    ├── tailwind.config.js
    └── vite.config.js
```

## Run

```bash
docker compose up --build
```

## Local test runner

You can test the automation flow locally without the frontend by running:

```bash
cd backend
python test_local_automation.py
```

This uses the same backend Playwright service and prompts for:

- URL
- username
- password
- transaction type
- CAPTCHA after the browser is opened

## Endpoints

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- noVNC: `http://localhost:6080/vnc.html?autoconnect=true&resize=remote`
- Raw VNC: `localhost:5900`

## What happens

1. Open the frontend dashboard.
2. Enter a URL or keep the default.
3. Click `Run Automation`.
4. Watch the browser session live in the embedded noVNC iframe.
5. Review the structured response and execution logs in the UI.

## Production notes

The codebase includes extension hooks for:

- reverse proxying with Nginx or Traefik
- auth middleware / API gateway integration
- queue-backed task execution
- horizontal scaling by moving browser workers behind a queue
