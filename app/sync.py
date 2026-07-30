"""Загрузка данных из WB API и запись в локальную SQLite-базу."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app import wb_client
from app.models import (
    AdvertCampaign,
    AdvertStat,
    Feedback,
    Order,
    Question,
    Sale,
    Stock,
)

ADVERT_TYPE_NAMES = {
    4: "Кампания в каталоге",
    5: "Автоматическая",
    6: "Поиск",
    7: "Рекомендации на карточке",
    8: "Автоматическая (новая)",
    9: "Поиск + Каталог",
}
ADVERT_STATUS_NAMES = {
    -1: "Ошибка",
    4: "Готова к запуску",
    7: "Завершена",
    8: "Отказалась",
    9: "Активна",
    11: "Приостановлена",
}


def _upsert(session: Session, model, rows: list[dict[str, Any]], conflict_cols: list[str]) -> int:
    if not rows:
        return 0
    table = model.__table__
    stmt = sqlite_insert(table)
    update_cols = {
        c.name: stmt.excluded[c.name] for c in table.columns if c.name not in conflict_cols
    }
    stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
    session.execute(stmt, rows)
    session.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Продажи / заказы
# ---------------------------------------------------------------------------

def sync_sales(session: Session, date_from: str) -> int:
    raw = wb_client.get_sales(date_from)
    rows = [
        {
            "srid": item.get("srid"),
            "date": item.get("date"),
            "last_change_date": item.get("lastChangeDate"),
            "warehouse_name": item.get("warehouseName"),
            "region_name": item.get("regionName"),
            "nm_id": item.get("nmId"),
            "supplier_article": item.get("supplierArticle"),
            "subject": item.get("subject"),
            "category": item.get("category"),
            "brand": item.get("brand"),
            "tech_size": item.get("techSize"),
            "barcode": item.get("barcode"),
            "total_price": item.get("totalPrice"),
            "discount_percent": item.get("discountPercent"),
            "price_with_disc": item.get("priceWithDisc"),
            "finished_price": item.get("finishedPrice"),
            "for_pay": item.get("forPay"),
            "is_return": str(item.get("saleID", "")).startswith("R"),
        }
        for item in raw
        if item.get("srid")
    ]
    return _upsert(session, Sale, rows, ["srid"])


def sync_orders(session: Session, date_from: str) -> int:
    raw = wb_client.get_orders(date_from)
    rows = [
        {
            "srid": item.get("srid"),
            "date": item.get("date"),
            "last_change_date": item.get("lastChangeDate"),
            "warehouse_name": item.get("warehouseName"),
            "region_name": item.get("regionName"),
            "nm_id": item.get("nmId"),
            "supplier_article": item.get("supplierArticle"),
            "subject": item.get("subject"),
            "category": item.get("category"),
            "brand": item.get("brand"),
            "tech_size": item.get("techSize"),
            "total_price": item.get("totalPrice"),
            "discount_percent": item.get("discountPercent"),
            "price_with_disc": item.get("priceWithDisc"),
            "is_cancel": bool(item.get("isCancel")),
            "cancel_date": item.get("cancelDate"),
        }
        for item in raw
        if item.get("srid")
    ]
    return _upsert(session, Order, rows, ["srid"])


# ---------------------------------------------------------------------------
# Остатки (полный снапшот — старые записи заменяются)
# ---------------------------------------------------------------------------

def sync_stocks(session: Session) -> int:
    raw = wb_client.get_stocks()
    rows = [
        {
            "last_change_date": item.get("lastChangeDate"),
            "warehouse_name": item.get("warehouseName"),
            "nm_id": item.get("nmId"),
            "supplier_article": item.get("supplierArticle"),
            "barcode": item.get("barcode"),
            "subject": item.get("subject"),
            "category": item.get("category"),
            "brand": item.get("brand"),
            "tech_size": item.get("techSize"),
            "quantity": item.get("quantity"),
            "in_way_to_client": item.get("inWayToClient"),
            "in_way_from_client": item.get("inWayFromClient"),
            "quantity_full": item.get("quantityFull"),
            "price": item.get("Price", item.get("price")),
            "discount": item.get("Discount", item.get("discount")),
        }
        for item in raw
    ]
    session.query(Stock).delete()
    if rows:
        session.bulk_insert_mappings(Stock, rows)
    session.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Отзывы / вопросы
# ---------------------------------------------------------------------------

def sync_feedbacks(session: Session, only_unanswered: bool = False) -> int:
    raw = wb_client.get_feedbacks(is_answered=(False if only_unanswered else None))
    rows = []
    for item in raw:
        details = item.get("productDetails") or {}
        answer = item.get("answer") or {}
        rows.append(
            {
                "id": item.get("id"),
                "nm_id": details.get("nmId"),
                "product_name": details.get("productName"),
                "text": item.get("text"),
                "pros": item.get("pros"),
                "cons": item.get("cons"),
                "rating": item.get("productValuation"),
                "created_date": item.get("createdDate"),
                "is_answered": bool(answer.get("text")),
                "answer_text": answer.get("text"),
            }
        )
    rows = [r for r in rows if r["id"]]
    return _upsert(session, Feedback, rows, ["id"])


def sync_questions(session: Session, only_unanswered: bool = False) -> int:
    raw = wb_client.get_questions(is_answered=(False if only_unanswered else None))
    rows = []
    for item in raw:
        details = item.get("productDetails") or {}
        answer = item.get("answer") or {}
        rows.append(
            {
                "id": item.get("id"),
                "nm_id": details.get("nmId"),
                "product_name": details.get("productName"),
                "text": item.get("text"),
                "created_date": item.get("createdDate"),
                "is_answered": bool(answer.get("text")),
                "answer_text": answer.get("text"),
            }
        )
    rows = [r for r in rows if r["id"]]
    return _upsert(session, Question, rows, ["id"])


# ---------------------------------------------------------------------------
# Реклама
# ---------------------------------------------------------------------------

def sync_advert(session: Session, days: int = 30) -> dict[str, int]:
    campaign_ids = wb_client.get_advert_campaign_ids()
    details = wb_client.get_advert_details(campaign_ids)

    campaign_rows = [
        {
            "advert_id": item.get("advertId"),
            "name": item.get("name") or f"Кампания {item.get('advertId')}",
            "type_name": ADVERT_TYPE_NAMES.get(item.get("type"), str(item.get("type"))),
            "status_name": ADVERT_STATUS_NAMES.get(item.get("status"), str(item.get("status"))),
            "created_at": item.get("createTime"),
            "start_time": item.get("startTime"),
            "end_time": item.get("endTime"),
        }
        for item in details
        if item.get("advertId")
    ]
    campaigns_saved = _upsert(session, AdvertCampaign, campaign_rows, ["advert_id"])

    date_to = date.today()
    date_from = date_to - timedelta(days=days)
    stats = wb_client.get_advert_fullstats(
        campaign_ids, date_from.isoformat(), date_to.isoformat()
    )

    stat_rows = []
    for campaign in stats:
        advert_id = campaign.get("advertId")
        for day in campaign.get("days", []):
            apps = day.get("apps", [])
            views = sum(a.get("views", 0) for a in apps)
            clicks = sum(a.get("clicks", 0) for a in apps)
            spend = sum(a.get("sum", 0) for a in apps)
            atbs = sum(a.get("atbs", 0) for a in apps)
            orders = sum(a.get("orders", 0) for a in apps)
            orders_sum = sum(a.get("sum_price", 0) for a in apps)
            stat_rows.append(
                {
                    "advert_id": advert_id,
                    "date": (day.get("date") or "")[:10],
                    "views": views,
                    "clicks": clicks,
                    "ctr": round(clicks / views * 100, 2) if views else 0,
                    "cpc": round(spend / clicks, 2) if clicks else 0,
                    "sum": spend,
                    "atbs": atbs,
                    "orders": orders,
                    "cr": round(orders / clicks * 100, 2) if clicks else 0,
                    "orders_sum": orders_sum,
                }
            )
    stats_saved = _upsert(session, AdvertStat, stat_rows, ["advert_id", "date"])

    return {"campaigns": campaigns_saved, "stat_days": stats_saved}
