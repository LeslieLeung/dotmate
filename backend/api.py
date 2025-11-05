"""FastAPI backend for dotmate configuration management."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import yaml
from pathlib import Path
import sys
import base64
from io import BytesIO

# Add parent directory to path to import dotmate modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotmate.config.models import Config, Device, Schedule
from dotmate.view.factory import ViewFactory
from dotmate.api.demo import DemoClient

app = FastAPI(title="Dotmate API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
PREVIEW_DIR = Path(__file__).parent.parent / "preview_cache"
PREVIEW_DIR.mkdir(exist_ok=True)


class ConfigResponse(BaseModel):
    """Response model for config."""
    api_key: str
    devices: List[Dict[str, Any]]


class ViewTypeInfo(BaseModel):
    """Information about a view type."""
    name: str
    params_schema: Dict[str, Any]


class PreviewRequest(BaseModel):
    """Request model for preview generation."""
    view_type: str
    params: Dict[str, Any]


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Dotmate API is running"}


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration."""
    try:
        if not CONFIG_PATH.exists():
            # Return empty config if file doesn't exist
            return ConfigResponse(api_key="", devices=[])

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return ConfigResponse(api_key="", devices=[])

        return ConfigResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading config: {str(e)}")


@app.post("/api/config")
async def save_config(config: ConfigResponse):
    """Save configuration."""
    try:
        # Convert to dict for YAML serialization
        config_dict = {
            "api_key": config.api_key,
            "devices": config.devices
        }

        # Validate the config by parsing it
        Config(**config_dict)

        # Save to file
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return {"message": "Configuration saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error saving config: {str(e)}")


@app.get("/api/views", response_model=List[ViewTypeInfo])
async def get_view_types():
    """Get available view types with their parameter schemas."""
    try:
        view_types = ViewFactory.get_available_types()
        result = []

        for view_type in view_types:
            params_class = ViewFactory.get_params_class(view_type)
            schema = params_class.model_json_schema()
            result.append(ViewTypeInfo(
                name=view_type,
                params_schema=schema
            ))

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting view types: {str(e)}")


@app.post("/api/preview")
async def generate_preview(request: PreviewRequest):
    """Generate preview image for a view type."""
    try:
        # Create demo client
        demo_client = DemoClient(str(PREVIEW_DIR))

        # Generate preview
        ViewFactory.execute_view(
            request.view_type,
            demo_client,
            "preview-device",
            request.params
        )

        # Find the most recently created image
        preview_files = list(PREVIEW_DIR.glob("*.png"))
        if not preview_files:
            raise HTTPException(status_code=404, detail="Preview image not generated")

        # Get the most recent file
        latest_file = max(preview_files, key=lambda p: p.stat().st_mtime)

        # Read and encode as base64
        with open(latest_file, 'rb') as f:
            image_data = f.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')

        return {
            "image": f"data:image/png;base64,{base64_image}",
            "filename": latest_file.name
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating preview: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
