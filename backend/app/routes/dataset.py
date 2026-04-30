from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])

DATA_DIR = Path(__file__).resolve().parents[3] / "dataset"


@router.get("/", response_model=List[str])
async def list_datasets():
    """List available dataset files."""
    if not DATA_DIR.exists():
        return []
    files = [p.name for p in sorted(DATA_DIR.glob("*.json"))]
    return files


@router.get("/{name}")
async def get_dataset(name: str):
    """Return dataset file contents as JSON."""
    target = DATA_DIR / name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        import json

        with target.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
