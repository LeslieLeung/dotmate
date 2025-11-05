# Dotmate Frontend Setup Guide

This guide explains how to set up and use the Dotmate configuration frontend.

## Overview

The Dotmate frontend consists of two parts:
1. **Backend API** (FastAPI) - Provides REST endpoints for config management and preview generation
2. **Frontend UI** (React + TypeScript) - Visual interface for editing configuration

## Quick Start

### 1. Install Backend Dependencies

```bash
# Install FastAPI and uvicorn
uv sync
```

### 2. Start the Backend API

```bash
# Start the API server
python backend/api.py
```

The API will be available at `http://localhost:8000`

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 4. Start the Frontend Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Using the Frontend

1. Open `http://localhost:5173` in your browser
2. Configure your API key
3. Add devices and schedules
4. Use the preview functionality to test your views
5. Save the configuration

## Backend API Endpoints

- `GET /api/config` - Get current configuration
- `POST /api/config` - Save configuration
- `GET /api/views` - Get available view types with schemas
- `POST /api/preview` - Generate preview image

## Features

### Configuration Management
- Visual editor for devices and schedules
- Dynamic forms based on view type
- Validation before saving

### Live Preview
- Server-side rendering using the same code as production
- Immediate feedback on configuration changes
- Support for all view types

### View Types

All view types from the main application are supported:

- **work**: Work countdown timer
- **text**: Custom text messages
- **code_status**: WakaTime coding statistics
- **image**: Binary image display
- **title_image**: Generated text-based images
- **umami_stats**: Umami analytics
- **github_contributions**: GitHub contribution heatmap

## Architecture

```
┌─────────────────┐
│  React Frontend │  (http://localhost:5173)
│  (Vite + TS)    │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  FastAPI Backend│  (http://localhost:8000)
│                 │
└────────┬────────┘
         │
         ├─── Reads/Writes config.yaml
         └─── Uses DemoClient for previews
```

## Development

### Adding New View Types

New view types are automatically detected by the frontend. Just:

1. Create the view class in `dotmate/view/`
2. Register it in `ViewFactory`
3. Restart the backend API
4. The frontend will automatically show the new type

### Customizing the Frontend

The frontend is built with:
- **React 18** + TypeScript
- **shadcn/ui** components
- **Tailwind CSS** for styling

See `frontend/README.md` for detailed frontend documentation.

## Troubleshooting

### Port Already in Use

If port 8000 is already in use:
```bash
# Kill the process using port 8000
lsof -ti:8000 | xargs kill -9

# Or change the port in backend/api.py
uvicorn.run(app, host="0.0.0.0", port=8001)
```

### CORS Issues

If you see CORS errors, check the `allow_origins` in `backend/api.py`:
```python
allow_origins=["http://localhost:5173", "http://localhost:3000"]
```

### Preview Not Working

1. Check that all required parameters are filled
2. Verify external service credentials (WakaTime, Umami, GitHub)
3. Check backend logs for detailed error messages

## Production Deployment

### Backend

```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.api:app
```

### Frontend

```bash
cd frontend
npm run build

# Serve the dist/ folder with any static file server
# For example, with Python:
cd dist
python -m http.server 8080
```

Or use a proper web server like nginx or deploy to:
- Vercel
- Netlify
- GitHub Pages
- Any static hosting service

## Security Notes

- The API key is stored in `config.yaml` - keep this file secure
- In production, use HTTPS for both frontend and backend
- Consider adding authentication to the API endpoints
- Validate all inputs on the backend

## Next Steps

- Configure your devices in the UI
- Set up schedules with cron expressions
- Use the preview feature to test views
- Save and use the generated `config.yaml` with the main daemon

For more information, see:
- `frontend/README.md` - Frontend documentation
- `README.md` - Main dotmate documentation
- `CLAUDE.md` - Developer documentation
