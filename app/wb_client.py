"""Тонкий клиент для WB Seller API (Statistics, Feedbacks, Advert)."""

import time
from typing import Any

import requests

from app.config import ADVERT_API, FEEDBACKS_API, STATISTICS_API, WB_API_TOKEN


class WBApiError(RuntimeError):
    pass


def _headers() -> dict:
    if not WB_API_TOKEN:
        raise WBApiError(
            "WB_API_TOKEN не задан. Укажи его в файле .env (см. .env.example)."
        )
    return {"Authorization": WB_API_TOKEN}


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Запрос к WB API с ретраями по 429 (лимит запросов)."""
    for attempt in range(5):
        resp = requests.request(method, url, headers=_headers(), timeout=60, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            time.sleep(min(wait, 30))
            continue
        if resp.status_code >= 400:
            raise WBApiError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
        return resp
    raise WBApiError(f"{method} {url}: превышено число попыток (429 Too Many Requests)")


# ---------------------------------------------------------------------------
# Statistics API — продажи, заказы, остатки
# ---------------------------------------------------------------------------

def get_sales(date_from: str, flag: int = 0) -> list[dict[str, Any]]:
    url = f"{STATISTICS_API}/api/v1/supplier/sales"
    resp = _request("GET", url, params={"dateFrom": date_from, "flag": flag})
    return resp.json() or []


def get_orders(date_from: str, flag: int = 0) -> list[dict[str, Any]]:
    url = f"{STATISTICS_API}/api/v1/supplier/orders"
    resp = _request("GET", url, params={"dateFrom": date_from, "flag": flag})
    return resp.json() or []


def get_stocks(date_from: str = "2020-01-01") -> list[dict[str, Any]]:
    url = f"{STATISTICS_API}/api/v1/supplier/stocks"
    resp = _request("GET", url, params={"dateFrom": date_from})
    return resp.json() or []


# ---------------------------------------------------------------------------
# Feedbacks API — отзывы и вопросы
# ---------------------------------------------------------------------------

def _paginate_feedbacks_or_questions(
    endpoint: str, data_key: str, is_answered: bool | None, max_items: int
) -> list[dict[str, Any]]:
    url = f"{FEEDBACKS_API}/api/v1/{endpoint}"
    items: list[dict[str, Any]] = []
    skip = 0
    take = 1000
    while len(items) < max_items:
        params = {"take": take, "skip": skip, "order": "dateDesc"}
        if is_answered is not None:
            params["isAnswered"] = str(is_answered).lower()
        resp = _request("GET", url, params=params)
        payload = (resp.json() or {}).get("data") or {}
        batch = payload.get(data_key) or []
        if not batch:
            break
        items.extend(batch)
        if len(batch) < take:
            break
        skip += take
    return items[:max_items]


def get_feedbacks(is_answered: bool | None = None, max_items: int = 5000) -> list[dict[str, Any]]:
    return _paginate_feedbacks_or_questions("feedbacks", "feedbacks", is_answered, max_items)


def get_questions(is_answered: bool | None = None, max_items: int = 5000) -> list[dict[str, Any]]:
    return _paginate_feedbacks_or_questions("questions", "questions", is_answered, max_items)


# ---------------------------------------------------------------------------
# Advert API — рекламные кампании и статистика
# ---------------------------------------------------------------------------

def get_advert_campaign_ids() -> list[int]:
    url = f"{ADVERT_API}/adv/v1/promotion/count"
    resp = _request("GET", url)
    payload = resp.json() or {}
    ids: list[int] = []
    for group in payload.get("adverts", []):
        for item in group.get("advert_list", []):
            advert_id = item.get("advertId")
            if advert_id is not None:
                ids.append(advert_id)
    return ids


def get_advert_details(campaign_ids: list[int]) -> list[dict[str, Any]]:
    if not campaign_ids:
        return []
    url = f"{ADVERT_API}/adv/v1/promotion/adverts"
    results: list[dict[str, Any]] = []
    for i in range(0, len(campaign_ids), 50):
        chunk = campaign_ids[i : i + 50]
        resp = _request("POST", url, json=chunk)
        results.extend(resp.json() or [])
    return results


def get_advert_fullstats(
    campaign_ids: list[int], date_from: str, date_to: str
) -> list[dict[str, Any]]:
    if not campaign_ids:
        return []
    url = f"{ADVERT_API}/adv/v2/fullstats"
    body = [
        {"id": cid, "interval": {"begin": date_from, "end": date_to}}
        for cid in campaign_ids
    ]
    resp = _request("POST", url, json=body)
    return resp.json() or []
