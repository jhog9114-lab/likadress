const charts = {};

function setStatus(text) {
  document.getElementById("sync-status").textContent = text;
}

async function api(path, options = {}) {
  const resp = await fetch(path, { method: "GET", ...options });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

function fmtMoney(n) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n || 0) + " ₽";
}

function upsertChart(canvasId, config) {
  if (charts[canvasId]) {
    charts[canvasId].destroy();
  }
  const ctx = document.getElementById(canvasId).getContext("2d");
  charts[canvasId] = new Chart(ctx, config);
  return charts[canvasId];
}

function renderRows(tbodySelector, rows, rowFn) {
  const tbody = document.querySelector(tbodySelector);
  tbody.innerHTML = "";
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 10;
    td.className = "empty";
    td.textContent = "Нет данных. Нажми «Обновить», чтобы загрузить из WB API.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = rowFn(row);
    tbody.appendChild(tr);
  }
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

document.querySelectorAll("nav.tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav.tabs .tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
    loadView(btn.dataset.view);
  });
});

// ---------------------------------------------------------------------------
// Sales
// ---------------------------------------------------------------------------

async function loadSales() {
  const days = document.getElementById("sales-days").value;
  const [summary, daily] = await Promise.all([
    api(`/api/sales/summary?days=${days}`),
    api(`/api/sales/daily?days=${days}`),
  ]);

  document.getElementById("sales-cards").innerHTML = `
    <div class="card"><div class="label">Выручка (выкупы)</div><div class="value">${fmtMoney(summary.revenue)}</div></div>
    <div class="card"><div class="label">Продаж</div><div class="value">${summary.sales_count}</div></div>
    <div class="card"><div class="label">Возвратов</div><div class="value">${summary.returns_count}</div></div>
    <div class="card"><div class="label">Заказов</div><div class="value">${summary.orders_count}</div></div>
    <div class="card"><div class="label">Сумма заказов</div><div class="value">${fmtMoney(summary.orders_revenue)}</div></div>
  `;

  upsertChart("sales-chart", {
    type: "line",
    data: {
      labels: daily.map((d) => d.date),
      datasets: [
        { label: "Выручка", data: daily.map((d) => d.revenue), borderColor: "#6c8cff", tension: 0.25 },
      ],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  renderRows(
    "#sales-subjects-table tbody",
    summary.top_subjects,
    (r) => `<td>${r.subject}</td><td>${fmtMoney(r.revenue)}</td>`
  );
}

document.getElementById("sales-days").addEventListener("change", loadSales);
document.getElementById("sales-sync-btn").addEventListener("click", async () => {
  const days = document.getElementById("sales-days").value;
  setStatus("Синхронизация продаж...");
  await api(`/api/sync/sales?days=${days}`, { method: "POST" });
  await api(`/api/sync/orders?days=${days}`, { method: "POST" });
  setStatus("Готово");
  loadSales();
});

// ---------------------------------------------------------------------------
// Stocks
// ---------------------------------------------------------------------------

async function loadStocks() {
  const [byWarehouse, items] = await Promise.all([
    api("/api/stocks/by-warehouse"),
    api("/api/stocks"),
  ]);

  upsertChart("stocks-chart", {
    type: "bar",
    data: {
      labels: byWarehouse.map((w) => w.warehouse_name),
      datasets: [{ label: "Остаток, шт", data: byWarehouse.map((w) => w.quantity), backgroundColor: "#3ecf8e" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  renderRows(
    "#stocks-table tbody",
    items.slice(0, 200),
    (r) => `<td>${r.supplier_article || ""}</td><td>${r.subject || ""}</td><td>${r.warehouse_name || ""}</td><td>${r.quantity}</td><td>${r.in_way_to_client}</td><td>${fmtMoney(r.price)}</td>`
  );
}

document.getElementById("stocks-sync-btn").addEventListener("click", async () => {
  setStatus("Синхронизация остатков...");
  await api("/api/sync/stocks", { method: "POST" });
  setStatus("Готово");
  loadStocks();
});

// ---------------------------------------------------------------------------
// Feedbacks & Questions
// ---------------------------------------------------------------------------

async function loadFeedbacks() {
  const unanswered = document.getElementById("feedbacks-unanswered").checked;
  const [feedbacks, questions, ratingSummary] = await Promise.all([
    api(`/api/feedbacks?unanswered=${unanswered}`),
    api(`/api/questions?unanswered=${unanswered}`),
    api("/api/feedbacks/rating-summary"),
  ]);

  const unansweredFeedbacks = feedbacks.filter((f) => !f.is_answered).length;
  const unansweredQuestions = questions.filter((q) => !q.is_answered).length;

  document.getElementById("feedbacks-cards").innerHTML = `
    <div class="card"><div class="label">Отзывов</div><div class="value">${feedbacks.length}</div></div>
    <div class="card"><div class="label">Неотвеченных отзывов</div><div class="value">${unansweredFeedbacks}</div></div>
    <div class="card"><div class="label">Вопросов</div><div class="value">${questions.length}</div></div>
    <div class="card"><div class="label">Неотвеченных вопросов</div><div class="value">${unansweredQuestions}</div></div>
  `;

  upsertChart("feedbacks-chart", {
    type: "bar",
    data: {
      labels: ratingSummary.map((r) => `${r.rating} ★`),
      datasets: [{ label: "Кол-во отзывов", data: ratingSummary.map((r) => r.count), backgroundColor: "#6c8cff" }],
    },
    options: { responsive: true, plugins: { legend: { display: false } } },
  });

  renderRows(
    "#feedbacks-table tbody",
    feedbacks.slice(0, 200),
    (r) => `<td>${r.product_name || ""}</td><td>${r.rating ?? ""}</td><td>${(r.text || "").slice(0, 120)}</td><td>${(r.created_date || "").slice(0, 10)}</td><td><span class="badge ${r.is_answered ? "ok" : "pending"}">${r.is_answered ? "отвечен" : "ждёт ответа"}</span></td>`
  );

  renderRows(
    "#questions-table tbody",
    questions.slice(0, 200),
    (r) => `<td>${r.product_name || ""}</td><td>${(r.text || "").slice(0, 160)}</td><td>${(r.created_date || "").slice(0, 10)}</td><td><span class="badge ${r.is_answered ? "ok" : "pending"}">${r.is_answered ? "отвечен" : "ждёт ответа"}</span></td>`
  );
}

document.getElementById("feedbacks-unanswered").addEventListener("change", loadFeedbacks);
document.getElementById("feedbacks-sync-btn").addEventListener("click", async () => {
  setStatus("Синхронизация отзывов и вопросов...");
  await api("/api/sync/feedbacks", { method: "POST" });
  setStatus("Готово");
  loadFeedbacks();
});

// ---------------------------------------------------------------------------
// Advert
// ---------------------------------------------------------------------------

async function loadAdvert() {
  const days = document.getElementById("advert-days").value;
  const [campaigns, stats] = await Promise.all([
    api("/api/advert/campaigns"),
    api(`/api/advert/stats?days=${days}`),
  ]);

  const totalSpend = stats.reduce((s, d) => s + d.spend, 0);
  const totalOrders = stats.reduce((s, d) => s + d.orders, 0);
  const totalOrdersSum = stats.reduce((s, d) => s + d.orders_sum, 0);
  const drr = totalOrdersSum ? ((totalSpend / totalOrdersSum) * 100).toFixed(1) : "—";

  document.getElementById("advert-cards").innerHTML = `
    <div class="card"><div class="label">Кампаний</div><div class="value">${campaigns.length}</div></div>
    <div class="card"><div class="label">Расход</div><div class="value">${fmtMoney(totalSpend)}</div></div>
    <div class="card"><div class="label">Заказов из рекламы</div><div class="value">${totalOrders}</div></div>
    <div class="card"><div class="label">ДРР</div><div class="value">${drr}${drr !== "—" ? "%" : ""}</div></div>
  `;

  upsertChart("advert-chart", {
    type: "bar",
    data: {
      labels: stats.map((d) => d.date),
      datasets: [
        { label: "Расход", data: stats.map((d) => d.spend), backgroundColor: "#ff6b6b", yAxisID: "y" },
        { label: "Заказы", data: stats.map((d) => d.orders), type: "line", borderColor: "#3ecf8e", yAxisID: "y1" },
      ],
    },
    options: {
      responsive: true,
      scales: {
        y: { position: "left" },
        y1: { position: "right", grid: { drawOnChartArea: false } },
      },
    },
  });

  renderRows(
    "#advert-table tbody",
    campaigns,
    (r) => `<td>${r.name || ""}</td><td>${r.type_name || ""}</td><td>${r.status_name || ""}</td><td>${(r.created_at || "").slice(0, 10)}</td>`
  );
}

document.getElementById("advert-days").addEventListener("change", loadAdvert);
document.getElementById("advert-sync-btn").addEventListener("click", async () => {
  const days = document.getElementById("advert-days").value;
  setStatus("Синхронизация рекламы...");
  await api(`/api/sync/advert?days=${days}`, { method: "POST" });
  setStatus("Готово");
  loadAdvert();
});

// ---------------------------------------------------------------------------
// Sync all + init
// ---------------------------------------------------------------------------

document.getElementById("sync-all-btn").addEventListener("click", async () => {
  setStatus("Синхронизация всех данных... это может занять минуту");
  try {
    await api("/api/sync/all?days=30", { method: "POST" });
    setStatus("Готово: " + new Date().toLocaleTimeString("ru-RU"));
  } catch (err) {
    setStatus("Ошибка: " + err.message);
  }
  loadView(document.querySelector("nav.tabs .tab.active").dataset.view);
});

function loadView(view) {
  const loaders = { sales: loadSales, stocks: loadStocks, feedbacks: loadFeedbacks, advert: loadAdvert };
  loaders[view]().catch((err) => setStatus("Ошибка: " + err.message));
}

loadView("sales");
