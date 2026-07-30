from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import sync
from app.database import get_session, init_db
from app.models import AdvertCampaign, AdvertStat, Feedback, Order, Question, Sale, Stock
from app.wb_client import WBApiError

app = FastAPI(title="WB Dashboard")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _handle_wb_errors(func_):
    try:
        return func_()
    except WBApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Синхронизация
# ---------------------------------------------------------------------------

@app.post("/api/sync/sales")
def sync_sales_endpoint(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    saved = _handle_wb_errors(lambda: sync.sync_sales(session, date_from))
    return {"saved": saved}


@app.post("/api/sync/orders")
def sync_orders_endpoint(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    saved = _handle_wb_errors(lambda: sync.sync_orders(session, date_from))
    return {"saved": saved}


@app.post("/api/sync/stocks")
def sync_stocks_endpoint(session: Session = Depends(get_session)):
    saved = _handle_wb_errors(lambda: sync.sync_stocks(session))
    return {"saved": saved}


@app.post("/api/sync/feedbacks")
def sync_feedbacks_endpoint(session: Session = Depends(get_session)):
    feedbacks = _handle_wb_errors(lambda: sync.sync_feedbacks(session))
    questions = _handle_wb_errors(lambda: sync.sync_questions(session))
    return {"feedbacks": feedbacks, "questions": questions}


@app.post("/api/sync/advert")
def sync_advert_endpoint(days: int = 30, session: Session = Depends(get_session)):
    result = _handle_wb_errors(lambda: sync.sync_advert(session, days))
    return result


@app.post("/api/sync/all")
def sync_all_endpoint(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    return {
        "sales": _handle_wb_errors(lambda: sync.sync_sales(session, date_from)),
        "orders": _handle_wb_errors(lambda: sync.sync_orders(session, date_from)),
        "stocks": _handle_wb_errors(lambda: sync.sync_stocks(session)),
        "feedbacks": _handle_wb_errors(lambda: sync.sync_feedbacks(session)),
        "questions": _handle_wb_errors(lambda: sync.sync_questions(session)),
        "advert": _handle_wb_errors(lambda: sync.sync_advert(session, days)),
    }


# ---------------------------------------------------------------------------
# Продажи / заказы
# ---------------------------------------------------------------------------

@app.get("/api/sales/daily")
def sales_daily(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        session.query(Sale)
        .filter(Sale.date >= date_from)
        .all()
    )
    by_day: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "count": 0, "returns": 0})
    for row in rows:
        day = (row.date or "")[:10]
        if row.is_return:
            by_day[day]["returns"] += 1
        else:
            by_day[day]["revenue"] += row.price_with_disc or 0
            by_day[day]["count"] += 1
    return [
        {"date": day, **values} for day, values in sorted(by_day.items())
    ]


@app.get("/api/sales/summary")
def sales_summary(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    rows = session.query(Sale).filter(Sale.date >= date_from).all()
    revenue = sum(r.price_with_disc or 0 for r in rows if not r.is_return)
    sales_count = sum(1 for r in rows if not r.is_return)
    returns_count = sum(1 for r in rows if r.is_return)

    orders = session.query(Order).filter(Order.date >= date_from).all()
    orders_count = sum(1 for o in orders if not o.is_cancel)
    orders_revenue = sum(o.price_with_disc or 0 for o in orders if not o.is_cancel)

    by_subject: dict[str, float] = defaultdict(float)
    for r in rows:
        if not r.is_return:
            by_subject[r.subject or "Без категории"] += r.price_with_disc or 0
    top_subjects = sorted(by_subject.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "revenue": revenue,
        "sales_count": sales_count,
        "returns_count": returns_count,
        "orders_count": orders_count,
        "orders_revenue": orders_revenue,
        "top_subjects": [{"subject": s, "revenue": v} for s, v in top_subjects],
    }


# ---------------------------------------------------------------------------
# Остатки
# ---------------------------------------------------------------------------

@app.get("/api/stocks")
def stocks(warehouse: str | None = None, session: Session = Depends(get_session)):
    query = session.query(Stock)
    if warehouse:
        query = query.filter(Stock.warehouse_name == warehouse)
    rows = query.order_by(Stock.quantity.desc()).limit(2000).all()
    return [
        {
            "nm_id": r.nm_id,
            "supplier_article": r.supplier_article,
            "subject": r.subject,
            "brand": r.brand,
            "tech_size": r.tech_size,
            "warehouse_name": r.warehouse_name,
            "quantity": r.quantity,
            "in_way_to_client": r.in_way_to_client,
            "in_way_from_client": r.in_way_from_client,
            "price": r.price,
        }
        for r in rows
    ]


@app.get("/api/stocks/by-warehouse")
def stocks_by_warehouse(session: Session = Depends(get_session)):
    rows = (
        session.query(Stock.warehouse_name, func.sum(Stock.quantity))
        .group_by(Stock.warehouse_name)
        .order_by(func.sum(Stock.quantity).desc())
        .all()
    )
    return [{"warehouse_name": w or "—", "quantity": int(q or 0)} for w, q in rows]


# ---------------------------------------------------------------------------
# Отзывы / вопросы
# ---------------------------------------------------------------------------

@app.get("/api/feedbacks")
def feedbacks(unanswered: bool = False, session: Session = Depends(get_session)):
    query = session.query(Feedback)
    if unanswered:
        query = query.filter(Feedback.is_answered.is_(False))
    rows = query.order_by(Feedback.created_date.desc()).limit(500).all()
    return [
        {
            "id": r.id,
            "nm_id": r.nm_id,
            "product_name": r.product_name,
            "text": r.text,
            "rating": r.rating,
            "created_date": r.created_date,
            "is_answered": r.is_answered,
        }
        for r in rows
    ]


@app.get("/api/questions")
def questions(unanswered: bool = False, session: Session = Depends(get_session)):
    query = session.query(Question)
    if unanswered:
        query = query.filter(Question.is_answered.is_(False))
    rows = query.order_by(Question.created_date.desc()).limit(500).all()
    return [
        {
            "id": r.id,
            "nm_id": r.nm_id,
            "product_name": r.product_name,
            "text": r.text,
            "created_date": r.created_date,
            "is_answered": r.is_answered,
        }
        for r in rows
    ]


@app.get("/api/feedbacks/rating-summary")
def rating_summary(session: Session = Depends(get_session)):
    rows = session.query(Feedback.rating, func.count(Feedback.id)).group_by(Feedback.rating).all()
    return [{"rating": rating or 0, "count": count} for rating, count in sorted(rows, key=lambda r: r[0] or 0)]


# ---------------------------------------------------------------------------
# Реклама
# ---------------------------------------------------------------------------

@app.get("/api/advert/campaigns")
def advert_campaigns(session: Session = Depends(get_session)):
    rows = session.query(AdvertCampaign).all()
    return [
        {
            "advert_id": r.advert_id,
            "name": r.name,
            "type_name": r.type_name,
            "status_name": r.status_name,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.get("/api/advert/stats")
def advert_stats(days: int = 30, session: Session = Depends(get_session)):
    date_from = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        session.query(AdvertStat)
        .filter(AdvertStat.date >= date_from)
        .order_by(AdvertStat.date)
        .all()
    )
    by_day: dict[str, dict[str, float]] = defaultdict(
        lambda: {"spend": 0.0, "views": 0, "clicks": 0, "orders": 0, "orders_sum": 0.0}
    )
    for r in rows:
        day = r.date
        by_day[day]["spend"] += r.sum or 0
        by_day[day]["views"] += r.views or 0
        by_day[day]["clicks"] += r.clicks or 0
        by_day[day]["orders"] += r.orders or 0
        by_day[day]["orders_sum"] += r.orders_sum or 0
    return [{"date": day, **values} for day, values in sorted(by_day.items())]
