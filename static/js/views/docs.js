// Документация проекта: ТЗ, OpenAPI, схема БД и демо-данные.
import { icon } from "../icons.js";
import { esc } from "../utils.js";

const FILES = [
  {
    id: "tz-md",
    icon: "file",
    title: "Техническое задание",
    format: "Markdown",
    text: "Полное ТЗ MVP: экраны, API, серии, заморозки, AI и критерии приёмки.",
    actions: [
      { label: "Открыть", href: "/docs/tz.md?inline=1", primary: true },
      { label: "Скачать .md", href: "/docs/tz.md", download: true },
    ],
  },
  {
    id: "tz-pdf",
    icon: "download",
    title: "Техническое задание",
    format: "PDF",
    text: "Та же версия документа для печати и передачи. Кириллица и таблицы сохраняются.",
    actions: [
      { label: "Открыть", href: "/docs/tz.pdf?inline=1", primary: true },
      { label: "Скачать .pdf", href: "/docs/tz.pdf", download: true },
    ],
  },
  {
    id: "openapi",
    icon: "docs",
    title: "OpenAPI",
    format: "YAML",
    text: "Описание всех публичных эндпоинтов, схем запросов и ответов.",
    actions: [{ label: "Открыть openapi.yaml", href: "/openapi.yaml", primary: true }],
  },
  {
    id: "schema",
    icon: "table",
    title: "Схема базы данных",
    format: "SQL",
    text: "Таблицы SQLite, индексы и ограничения. Подходит для локального развёртывания.",
    actions: [{ label: "Скачать schema.sql", href: "/docs/file/schema.sql", download: true, primary: true }],
  },
  {
    id: "seed",
    icon: "list",
    title: "Демо-данные",
    format: "JSON",
    text: "Набор безопасных демонстрационных привычек и настроек для быстрого старта.",
    actions: [{ label: "Скачать seed.json", href: "/docs/file/seed.json", download: true, primary: true }],
  },
  {
    id: "readme",
    icon: "book",
    title: "README",
    format: "Markdown",
    text: "Как запустить проект, настроить окружение, Telegram и AI-провайдера.",
    actions: [{ label: "Открыть README", href: "/docs/file/README.md?inline=1", primary: true }],
  },
];

export async function mount(root, ctx) {
  root.removeAttribute("aria-busy");

  root.innerHTML = `
    <div class="page-head">
      <div class="page-title-block">
        <span class="kicker">Документы</span>
        <h1 class="display">Всё <em>прозрачно</em></h1>
        <p class="page-sub">ТЗ, API и схема данных доступны без сборки и скрытых сервисов. Скачайте нужный файл или откройте его в браузере.</p>
      </div>
      <div class="page-actions">
        ${ctx.user?.role === "admin" ? `<a class="btn btn-soft" href="#/admin">${icon("admin")} Админка</a>` : ""}
        <a class="btn btn-primary" href="/docs/tz.pdf" download>${icon("download")} Скачать ТЗ PDF</a>
      </div>
    </div>

    <div class="doc-grid">
      ${FILES.map((file) => `
        <article class="card doc-card">
          <span class="doc-icon">${icon(file.icon)}</span>
          <div class="row between" style="gap:8px">
            <h3>${esc(file.title)}</h3>
            <span class="badge badge-muted">${esc(file.format)}</span>
          </div>
          <p>${esc(file.text)}</p>
          <div class="doc-actions">
            ${file.actions.map((action) => `
              <a class="btn ${action.primary ? "btn-primary" : "btn-soft"} btn-sm"
                 href="${esc(action.href)}"${action.download ? " download" : ""}
                 ${action.download ? "" : 'target="_blank" rel="noopener"'}>
                ${esc(action.label)}
              </a>
            `).join("")}
          </div>
        </article>
      `).join("")}
    </div>

    <div class="section-head">
      <h2 class="section-title">Что входит в MVP</h2>
    </div>
    <div class="settings-grid">
      <div class="card card-pad">
        <h3 class="h3">Привычки и ритм</h3>
        <ul class="rec-list" style="margin-top:10px">
          ${[
            "Boolean, quantity и duration — отметка в один тап или через значение.",
            "Расписания daily, weekdays и times_per_week с недельной логикой.",
            "Серии, частичные шаги и две заморозки в календарный месяц.",
            "Календарь месяца и годовая тепловая карта с редактированием задним числом.",
          ].map((text) => `
            <li class="rec-item"><span class="rec-num">${icon("check")}</span><span class="rec-text">${esc(text)}</span></li>
          `).join("")}
        </ul>
      </div>
      <div class="card card-pad">
        <h3 class="h3">AI и данные</h3>
        <ul class="rec-list" style="margin-top:10px">
          ${[
            "Подбор 3–5 привычек с превью и применением после согласия.",
            "Недельный обзор без токсичной мотивации и медицинских советов.",
            "Лимит 10 AI-запросов в день и локальный fallback без ключа.",
            "Экспорт CSV/JSON/PDF и полное удаление аккаунта по подтверждению.",
          ].map((text) => `
            <li class="rec-item"><span class="rec-num">${icon("check")}</span><span class="rec-text">${esc(text)}</span></li>
          `).join("")}
        </ul>
      </div>
    </div>

    <div class="ai-note mt-3">
      ${icon("shield")}
      <span>Пароли хранятся только в виде хэшей, сессии — в HttpOnly cookie, AI-ключи не попадают в браузер.
        Документация и файлы доступны на этом сервере; внешние трекеры не используются.</span>
    </div>
  `;
}
