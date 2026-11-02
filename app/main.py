from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Click, Link
from app.utils import generate_code, parse_device
from app.cache import get_cached_link, set_cached_link

app = FastAPI(title="URL Shortener")


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/shorten", response_model=ShortenResponse, status_code=201)
def shorten(body: ShortenRequest, request: Request, db: Session = Depends(get_db)):
    for _ in range(5):
        link = Link(short_code=generate_code(), original_url=str(body.url))
        db.add(link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return ShortenResponse(
            short_code=link.short_code,
            short_url=str(request.base_url) + link.short_code,
            original_url=link.original_url,
        )
    raise HTTPException(status_code=500, detail="Could not generate a unique code")


@app.get("/{short_code}")
def redirect(short_code: str, request: Request, db: Session = Depends(get_db)):
    cached = get_cached_link(short_code)
    if cached:
        link_id, url, cache_status = cached["id"], cached["url"], "HIT"
    else:
        link = db.scalar(select(Link).where(Link.short_code == short_code))
        if link is None:
            raise HTTPException(status_code=404, detail="Short link not found")
        link_id, url, cache_status = link.id, link.original_url, "MISS"
        set_cached_link(short_code, link_id, url)

    db.add(
        Click(
            link_id=link_id,
            device=parse_device(request.headers.get("user-agent")),
            referrer=request.headers.get("referer"),
            country=request.headers.get("cf-ipcountry"),
        )
    )
    db.commit()

    return RedirectResponse(url, status_code=302, headers={"X-Cache": cache_status})