from datetime import date, datetime
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Click, Link
from app.utils import generate_code, parse_device
from app.cache import get_cached_link, set_cached_link
from app.ratelimit import rate_limit

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

@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("shorten", 5, 60))],
)
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

class LinkItem(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime


class LinkPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[LinkItem]


@app.get("/links", response_model=LinkPage)
def list_links(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Link))
    links = db.scalars(
        select(Link).order_by(Link.id.desc()).limit(limit).offset(offset)
    ).all()
    return LinkPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            LinkItem(
                short_code=link.short_code,
                original_url=link.original_url,
                created_at=link.created_at,
            )
            for link in links
        ],
    )

def record_click(
    link_id: int, device: str, referrer: str | None, country: str | None
) -> None:
    # Runs after the response is sent, so it opens its own database session
    with SessionLocal() as db:
        db.add(Click(link_id=link_id, device=device, referrer=referrer, country=country))
        db.commit()

@app.get("/{short_code}")
def redirect(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    cached = get_cached_link(short_code)
    if cached:
        link_id, url, cache_status = cached["id"], cached["url"], "HIT"
    else:
        link = db.scalar(select(Link).where(Link.short_code == short_code))
        if link is None:
            raise HTTPException(status_code=404, detail="Short link not found")
        link_id, url, cache_status = link.id, link.original_url, "MISS"
        set_cached_link(short_code, link_id, url)

    background_tasks.add_task(
        record_click,
        link_id,
        parse_device(request.headers.get("user-agent")),
        request.headers.get("referer"),
        request.headers.get("cf-ipcountry"),
    )

    return RedirectResponse(url, status_code=302, headers={"X-Cache": cache_status})

class DayCount(BaseModel):
    day: date
    clicks: int


class StatsResponse(BaseModel):
    short_code: str
    total_clicks: int
    by_device: dict[str, int]
    by_country: dict[str, int]
    last_7_days: list[DayCount]

def _count_by(db: Session, link_id: int, column) -> dict[str, int]:
    rows = db.execute(
        select(column, func.count()).where(Click.link_id == link_id).group_by(column)
    ).all()
    return {value or "unknown": count for value, count in rows}


@app.get("/links/{short_code}/stats", response_model=StatsResponse)
def link_stats(short_code: str, db: Session = Depends(get_db)):
    link = db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="Short link not found")

    total = db.scalar(
        select(func.count()).select_from(Click).where(Click.link_id == link.id)
    )

    day = func.date(Click.clicked_at)
    daily = db.execute(
        select(day, func.count())
        .where(Click.link_id == link.id)
        .group_by(day)
        .order_by(day.desc())
        .limit(7)
    ).all()

    return StatsResponse(
        short_code=short_code,
        total_clicks=total,
        by_device=_count_by(db, link.id, Click.device),
        by_country=_count_by(db, link.id, Click.country),
        last_7_days=[DayCount(day=d, clicks=n) for d, n in daily],
    )

def _count_by(db: Session, link_id: int, column) -> dict[str, int]:
    rows = db.execute(
        select(column, func.count()).where(Click.link_id == link_id).group_by(column)
    ).all()
    return {value or "unknown": count for value, count in rows}


@app.get("/links/{short_code}/stats", response_model=StatsResponse)
def link_stats(short_code: str, db: Session = Depends(get_db)):
    link = db.scalar(select(Link).where(Link.short_code == short_code))
    if link is None:
        raise HTTPException(status_code=404, detail="Short link not found")

    total = db.scalar(
        select(func.count()).select_from(Click).where(Click.link_id == link.id)
    )

    day = func.date(Click.clicked_at)
    daily = db.execute(
        select(day, func.count())
        .where(Click.link_id == link.id)
        .group_by(day)
        .order_by(day.desc())
        .limit(7)
    ).all()

    return StatsResponse(
        short_code=short_code,
        total_clicks=total,
        by_device=_count_by(db, link.id, Click.device),
        by_country=_count_by(db, link.id, Click.country),
        last_7_days=[DayCount(day=d, clicks=n) for d, n in daily],
    )