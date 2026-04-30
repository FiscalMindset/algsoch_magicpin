from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/v1/docs", tags=["docs"])

REPO_ROOT = Path(__file__).resolve().parents[3]

# Keep this explicit to avoid exposing arbitrary filesystem reads.
DOC_FILES = [
    "challenge-brief.md",
    "challenge-testing-brief.md",
    "engagement-design.md",
    "engagement-research.md",
    "README-FULL-STACK.md",
    "QUICK-START.md",
    "DEVELOPMENT.md",
    "RUNNING.md",
    "TEST-AND-RUN-REPORT.md",
]


@router.get("/", response_model=List[str])
async def list_docs() -> List[str]:
    return [f for f in DOC_FILES if (REPO_ROOT / f).exists()]


@router.get("/{name}")
async def get_doc(name: str):
    if name not in DOC_FILES:
        raise HTTPException(status_code=404, detail="Doc not found")
    path = REPO_ROOT / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Doc not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}

