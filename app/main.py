"""Recipe Scaler: FastAPI app. Stateless: recipes live in the user's browser."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import extract
from .scaling import ScalingError, ingredient_factor, portions_factor, recipe_from_dict, scale

STATIC = Path(__file__).parent / "static"
DAILY_PER_IP = int(os.environ.get("DAILY_PER_IP", "10"))
DAILY_GLOBAL = int(os.environ.get("DAILY_GLOBAL", "150"))

app = FastAPI(title="Recipe Scaler", docs_url=None, redoc_url=None)

# Daily AI-call counters, kept in memory (reset on restart; fine for a demo).
_counts: dict[str, int] = {}
_day = ""


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_limits(ip: str) -> None:
    global _day, _counts
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if today != _day:
        _day, _counts = today, {}
    if _counts.get("*", 0) >= DAILY_GLOBAL:
        raise HTTPException(429, "The demo has hit its daily AI limit. Try again tomorrow, or use a sample recipe.")
    if _counts.get(ip, 0) >= DAILY_PER_IP:
        raise HTTPException(429, f"Daily limit of {DAILY_PER_IP} photo reads reached. Sample recipes still work.")
    _counts[ip] = _counts.get(ip, 0) + 1
    _counts["*"] = _counts.get("*", 0) + 1


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/extract")
async def extract_recipe(request: Request, files: list[UploadFile] = File(...)):
    if not 1 <= len(files) <= extract.MAX_IMAGES:
        raise HTTPException(400, "Send one or two photos (front and back of the card).")
    images = []
    try:
        for f in files:
            data = await f.read(extract.MAX_UPLOAD_BYTES + 1)
            images.append(extract.prepare_image(data))
    except extract.ExtractError as e:
        raise HTTPException(400, str(e)) from None
    _check_limits(_client_ip(request))
    try:
        raw = extract.call_claude(images)
    except extract.ExtractError as e:
        raise HTTPException(502, str(e)) from None
    return extract.clean_result(raw)


class ScaleRequest(BaseModel):
    recipe: dict
    mode: Literal["portions", "ingredient"]
    target_portions: Optional[float] = Field(None, gt=0, le=100000)
    ingredient_index: Optional[int] = Field(None, ge=0, le=200)
    amount: Optional[float] = Field(None, gt=0, le=10_000_000)
    unit: Optional[str] = None
    per_portion: bool = False


@app.post("/api/scale")
def scale_recipe(req: ScaleRequest):
    try:
        recipe = recipe_from_dict(req.recipe)
        if req.per_portion and req.mode == "portions" and not req.target_portions:
            factor = 1.0 / recipe.portions  # one portion
        elif req.mode == "portions":
            if not req.target_portions:
                raise ScalingError("Enter how many portions you need")
            factor = portions_factor(recipe, req.target_portions)
        else:
            if req.ingredient_index is None or not req.amount or not req.unit:
                raise ScalingError("Pick an ingredient and enter the amount you have")
            factor = ingredient_factor(recipe, req.ingredient_index, req.amount, req.unit)
        return scale(recipe, factor, per_portion=req.per_portion)
    except ScalingError as e:
        return JSONResponse({"detail": str(e)}, status_code=422)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
