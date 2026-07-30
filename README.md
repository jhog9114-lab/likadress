# WB Dashboard

Локальное приложение для парсинга и обработки данных Wildberries Seller API:
продажи и аналитика, остатки на складах, отзывы и вопросы, рекламные кампании.
Данные сохраняются в локальную SQLite-базу и отображаются в веб-дашборде.

## Установка

```bash
cd wb-dashboard
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Открой `.env` и вставь токен продавца WB:

```
WB_API_TOKEN=твой_токен
```

Токен выпускается в личном кабинете WB: **Настройки → Доступ к API → Создать токен**.
При создании включи категории: **Статистика**, **Аналитика**, **Вопросы и отзывы**, **Продвижение**.

## Запуск

```bash
python run.py
```

Дашборд откроется на `http://127.0.0.1:8000`. Открой этот адрес в Chrome.

## Использование

1. На вкладках «Продажи», «Остатки», «Отзывы и вопросы», «Реклама» нажми соответствующую
   кнопку «Обновить» — приложение сходит в WB API и сохранит данные в `wb_dashboard.sqlite3`.
2. Кнопка «Синхронизировать всё» в шапке обновляет все 4 раздела за один клик.
3. Графики и таблицы обновляются автоматически после синхронизации; можно переключать
   период (7/30/90 дней) без повторного похода в API — данные уже лежат в базе.

## Структура проекта

```
wb-dashboard/
  app/
    main.py          FastAPI-приложение и HTTP-роуты
    wb_client.py      запросы к WB API (Statistics, Feedbacks, Advert)
    sync.py            загрузка данных из WB API и запись в БД
    models.py          таблицы SQLAlchemy
    database.py        подключение к SQLite
    config.py           переменные окружения
    static/              фронтенд дашборда (HTML/CSS/JS, Chart.js)
  run.py                 точка входа (uvicorn)
  requirements.txt
```

## Используемые эндпоинты WB API

- `statistics-api.wildberries.ru` — `/api/v1/supplier/sales`, `/api/v1/supplier/orders`,
  `/api/v1/supplier/stocks`
- `feedbacks-api.wildberries.ru` — `/api/v1/feedbacks`, `/api/v1/questions`
- `advert-api.wildberries.ru` — `/adv/v1/promotion/count`, `/adv/v1/promotion/adverts`,
  `/adv/v2/fullstats`

## Примечания

- У WB API есть лимиты на частоту запросов; клиент сам делает повторные попытки при
  ответе 429 (Too Many Requests).
- Остатки (`/api/sync/stocks`) — это полный снапшот на момент синхронизации: старые
  записи в таблице `stocks` заменяются новыми при каждой синхронизации.
- Продажи, заказы, отзывы, вопросы и статистика рекламы сохраняются накопительно
  (upsert по уникальному id), старые данные не теряются.
