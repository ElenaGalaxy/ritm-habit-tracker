// Админка: сводка, пользователи, шаблоны привычек, журнал ошибок и тик напоминаний.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { modal, setButtonBusy, skeleton, toast } from "../ui.js";
import { esc, formatDateTime, pluralRu } from "../utils.js";

const TYPE_LABELS = { boolean: "Да / нет", quantity: "Количество", duration: "Время" };
const SCHEDULE_LABELS = { daily: "Ежедневно", weekdays: "По будням", times_per_week: "N раз в неделю" };

export async function mount(root, ctx) {
  let data = null;
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      data = await api.get("/admin/overview");
      if (!alive) return;
      render();
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Админка недоступна</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <div class="row mt-3" style="justify-content:center;gap:8px">
            <a class="btn btn-soft" href="#/today">На главную</a>
            <button type="button" class="btn btn-primary" data-action="retry">Повторить</button>
          </div>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function render() {
    const counts = data.counts || {};
    const users = data.users || [];
    const templates = data.templates || [];
    const errors = data.errors || [];

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">Администрирование</span>
          <h1 class="display">Сводка <em>без лишнего</em></h1>
          <p class="page-sub">Только технические метрики, шаблоны и ошибки. Личные заметки пользователей здесь не показываются.</p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-soft" data-action="refresh">${icon("refresh")} Обновить</button>
          <button type="button" class="btn btn-primary" data-action="tick">${icon("bell")} Запустить напоминания</button>
        </div>
      </div>

      <div class="count-grid">
        ${countCell("Пользователи", counts.users, "users")}
        ${countCell("Привычки", counts.habits, "habits")}
        ${countCell("Отметки", counts.logs, "checkCircle")}
        ${countCell("AI-запросы", counts.ai_requests, "sparkles")}
        ${countCell("Напоминания", counts.reminders, "bell")}
        ${countCell("Ошибки", counts.errors, "alert")}
      </div>

      <div class="row wrap mt-3" style="gap:7px">
        <span class="badge ${data.bot_configured ? "badge-moss" : "badge-muted"}">
          ${icon("telegram")} Бот ${data.bot_configured ? "настроен" : "не настроен"}
        </span>
        <span class="badge ${data.ai_configured ? "badge-moss" : "badge-muted"}">
          ${icon("sparkles")} AI ${data.ai_configured ? "подключён" : "локальный fallback"}
        </span>
        <span class="badge ${data.docs_public ? "badge-blue" : "badge-sand"}">
          ${icon("docs")} Документация ${data.docs_public ? "публичная" : "только для админа"}
        </span>
      </div>

      <div class="section-head">
        <h2 class="section-title">Пользователи</h2>
        <span class="tiny faint">${users.length} ${pluralRu(users.length, "запись", "записи", "записей")}</span>
      </div>
      <div class="card card-pad" style="overflow-x:auto">
        <table class="admin-table">
          <thead>
            <tr><th>ID</th><th>Имя</th><th>Email</th><th>Роль</th><th>Часовой пояс</th><th>Создан</th></tr>
          </thead>
          <tbody>
            ${users.map((user) => `
              <tr>
                <td>${user.id}</td>
                <td>${esc(user.name)}</td>
                <td>${esc(user.email)}</td>
                <td><span class="badge ${user.role === "admin" ? "badge-accent" : "badge-muted"}">${esc(user.role)}</span></td>
                <td>${esc(user.timezone || "—")}</td>
                <td class="faint">${esc(formatDateTime(user.created_at))}</td>
              </tr>
            `).join("") || `<tr><td colspan="6" class="faint">Пользователей пока нет.</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="section-head">
        <h2 class="section-title">Шаблоны привычек</h2>
        <span class="tiny faint">${templates.filter((item) => item.is_active).length} активных</span>
      </div>
      <div class="card card-pad" style="overflow-x:auto">
        <table class="admin-table">
          <thead>
            <tr><th>ID</th><th>Название</th><th>Тип</th><th>Расписание</th><th>Активен</th><th></th></tr>
          </thead>
          <tbody>
            ${templates.map((template) => `
              <tr data-template-id="${template.id}">
                <td>${template.id}</td>
                <td>${esc(template.title)}</td>
                <td>${esc(TYPE_LABELS[template.type] || template.type)}</td>
                <td>${esc(SCHEDULE_LABELS[template.schedule] || template.schedule)}</td>
                <td>
                  <button type="button" class="switch${template.is_active ? " on" : ""}" data-template-toggle="${template.id}"
                          role="switch" aria-checked="${Boolean(template.is_active)}" aria-label="Шаблон ${esc(template.title)}"></button>
                </td>
                <td>
                  <button type="button" class="btn btn-xs btn-soft" data-template-edit="${template.id}">${icon("edit")} Название</button>
                </td>
              </tr>
            `).join("") || `<tr><td colspan="6" class="faint">Шаблонов пока нет.</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="section-head">
        <h2 class="section-title">Журнал ошибок</h2>
        <span class="tiny faint">последние ${errors.length}</span>
      </div>
      <div class="card card-pad" style="overflow-x:auto">
        <table class="admin-table">
          <thead>
            <tr><th>ID</th><th>Уровень</th><th>Сообщение</th><th>Маршрут</th><th>Когда</th></tr>
          </thead>
          <tbody>
            ${errors.map((error) => `
              <tr>
                <td>${error.id}</td>
                <td><span class="badge ${error.level === "error" ? "badge-accent" : "badge-muted"}">${esc(error.level)}</span></td>
                <td class="error-msg">${esc(error.message)}</td>
                <td class="nowrap faint">${esc(error.method || "")} ${esc(error.path || "")}</td>
                <td class="nowrap faint">${esc(formatDateTime(error.created_at))}</td>
              </tr>
            `).join("") || `<tr><td colspan="5" class="faint">Ошибок нет — отличная новость.</td></tr>`}
          </tbody>
        </table>
      </div>

      <div class="ai-note mt-3">
        ${icon("info")}
        <span>Запуск напоминаний вручную полезен при локальной проверке. В production планировщик работает автоматически
          при запуске через <code>app.py</code>.</span>
      </div>
    `;
    bind();
  }

  function countCell(label, value, iconName) {
    return `
      <div class="count-cell">
        <div class="k">${icon(iconName)} ${esc(label)}</div>
        <div class="v">${Number(value) || 0}</div>
      </div>
    `;
  }

  function bind() {
    root.querySelector('[data-action="refresh"]')?.addEventListener("click", () => load(false));
    root.querySelector('[data-action="tick"]')?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      setButtonBusy(button, true, "Отправляем…");
      try {
        const result = await api.post("/reminders/tick");
        const parts = [];
        if (result.sent !== undefined) parts.push(`отправлено: ${result.sent}`);
        if (result.skipped !== undefined) parts.push(`пропущено: ${result.skipped}`);
        if (result.due !== undefined) parts.push(`к отправке: ${result.due}`);
        toast(parts.length ? `Напоминания обработаны — ${parts.join(", ")}` : "Напоминания обработаны", {
          type: "success",
        });
      } catch (error) {
        toast(error.message || "Не удалось запустить напоминания.", { type: "error" });
      } finally {
        setButtonBusy(button, false);
      }
    });

    root.querySelectorAll("[data-template-toggle]").forEach((button) => {
      button.addEventListener("click", () => toggleTemplate(button));
    });
    root.querySelectorAll("[data-template-edit]").forEach((button) => {
      button.addEventListener("click", () => renameTemplate(button));
    });
  }

  async function toggleTemplate(button) {
    const id = Number(button.dataset.templateToggle);
    const template = (data.templates || []).find((item) => Number(item.id) === id);
    if (!template) return;
    const next = !button.classList.contains("on");
    button.disabled = true;
    try {
      const response = await api.patch(`/admin/templates/${id}`, { is_active: next });
      template.is_active = response.template?.is_active ?? (next ? 1 : 0);
      button.classList.toggle("on", Boolean(template.is_active));
      button.setAttribute("aria-checked", String(Boolean(template.is_active)));
      toast(next ? "Шаблон включён" : "Шаблон скрыт", { type: "info" });
    } catch (error) {
      toast(error.message || "Не удалось изменить шаблон.", { type: "error" });
    } finally {
      button.disabled = false;
    }
  }

  function renameTemplate(button) {
    const id = Number(button.dataset.templateEdit);
    const template = (data.templates || []).find((item) => Number(item.id) === id);
    if (!template) return;
    const dialog = modal({
      title: "Название шаблона",
      narrow: true,
      body: `
        <div class="field">
          <label class="label" for="template-title">Название</label>
          <input class="input" id="template-title" maxlength="80" value="${esc(template.title)}" autofocus>
        </div>
        <p class="error-text" data-role="error" hidden></p>
      `,
      footer: `
        <button type="button" class="btn btn-ghost" data-role="cancel">Отмена</button>
        <button type="button" class="btn btn-primary" data-role="save">Сохранить</button>
      `,
    });
    const input = dialog.body.querySelector("#template-title");
    const errorBox = dialog.body.querySelector('[data-role="error"]');
    const saveButton = dialog.foot.querySelector('[data-role="save"]');
    dialog.foot.querySelector('[data-role="cancel"]').addEventListener("click", () => dialog.close());
    saveButton.addEventListener("click", async () => {
      const title = input.value.trim();
      if (!title) {
        errorBox.textContent = "Введите название.";
        errorBox.hidden = false;
        return;
      }
      setButtonBusy(saveButton, true, "Сохраняем…");
      try {
        const response = await api.patch(`/admin/templates/${id}`, { title });
        template.title = response.template?.title || title;
        dialog.close();
        toast("Шаблон обновлён", { type: "success" });
        render();
      } catch (error) {
        errorBox.textContent = error.message || "Не удалось сохранить.";
        errorBox.hidden = false;
        setButtonBusy(saveButton, false);
      }
    });
  }

  await load(true);
  return () => {
    alive = false;
  };
}
