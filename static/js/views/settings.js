// Настройки: профиль, тема, Telegram, тихие часы, AI, условия, экспорт, удаление.
import { api, download } from "../api.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import {
  confirmDialog, modal, promptWord, setButtonBusy, skeleton, sync, toast,
} from "../ui.js";
import {
  esc, formatDateTime, pluralRu, timezoneOptions,
} from "../utils.js";

const CONDITION_ITEMS = [
  {
    key: "streak_badge",
    title: "Серия от 7 дней",
    text: "Мягко отметить, когда серия достигла недели. Один раз на серию.",
  },
  {
    key: "missed_reminder",
    title: "Два пропуска подряд",
    text: "Предложить паузу или заморозку вместо чувства вины.",
  },
  {
    key: "low_week",
    title: "Неделя ниже 50%",
    text: "Напомнить, что можно уменьшить нагрузку и вернуться завтра.",
  },
];

export async function mount(root, ctx) {
  let user = { ...(store.user || {}) };
  let reminders = null;
  let conditions = null;
  let aiStatus = null;
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      const [me, remindersData, conditionsData, aiData] = await Promise.all([
        api.get("/auth/me"),
        api.get("/reminders"),
        api.get("/conditions"),
        api.get("/ai/status").catch(() => null),
      ]);
      if (!alive) return;
      if (me?.user) {
        user = me.user;
        store.setUser(me.user);
      }
      reminders = remindersData;
      conditions = conditionsData;
      aiStatus = aiData;
      render();
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Не удалось загрузить настройки</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button type="button" class="btn btn-primary mt-3" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function switchHTML(on, key, label) {
    return `<button type="button" class="switch${on ? " on" : ""}" data-toggle="${key}"
              role="switch" aria-checked="${on}" aria-label="${esc(label)}"></button>`;
  }

  function render() {
    const settings = conditions?.settings || user.conditions_enabled || {};
    const quietStart = user.quiet_hours_start || "22:00";
    const quietEnd = user.quiet_hours_end || "08:00";
    const events = (conditions?.events || []).slice(0, 6);
    const notifications = (reminders?.notifications || []).slice(0, 8);

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">Настройки</span>
          <h1 class="display">Всё <em>по-вашему</em></h1>
          <p class="page-sub">Тихие часы, тема, напоминания и AI — меняйте в своём темпе. Данные остаются только у вас.</p>
        </div>
        <div class="page-actions">
          <a class="btn btn-soft" href="#/docs">${icon("docs")} Документы</a>
        </div>
      </div>

      <div class="settings-grid">
        <div class="settings-stack">
          <section class="card settings-card">
            <h3>Профиль</h3>
            <p class="sub">Имя, цель и часовой пояс. Цель поможет ассистенту подобрать привычки.</p>
            <form id="settings-profile" class="stack" novalidate>
              <div class="form-row">
                <div class="field">
                  <label class="label" for="set-name">Имя</label>
                  <input class="input" id="set-name" name="name" maxlength="80" value="${esc(user.name || "")}">
                </div>
                <div class="field">
                  <label class="label" for="set-timezone">Часовой пояс</label>
                  <select class="select" id="set-timezone" name="timezone">
                    ${timezoneOptions(user.timezone)}
                  </select>
                </div>
              </div>
              <div class="field">
                <label class="label" for="set-goal">Цель <span class="optional">необязательно</span></label>
                <textarea class="textarea" id="set-goal" name="goal" maxlength="500"
                          placeholder="Что хочется изменить">${esc(user.goal || "")}</textarea>
              </div>
              <div class="row between" style="gap:10px;flex-wrap:wrap">
                <span class="tiny faint">${esc(user.email || "")}</span>
                <button type="submit" class="btn btn-primary btn-sm" data-role="save-profile">Сохранить профиль</button>
              </div>
            </form>
          </section>

          <section class="card settings-card">
            <h3>Напоминания</h3>
            <p class="sub">Один раз в день, только если привычка ещё не отмечена. В тихие часы не беспокоим.</p>
            <form id="settings-reminders" class="stack">
              <div class="setting-row">
                <div class="setting-info">
                  <div class="t">Канал</div>
                  <div class="d">Telegram или только приложение.</div>
                </div>
                <select class="select" name="reminder_channel">
                  <option value="telegram"${user.reminder_channel === "telegram" ? " selected" : ""}>Telegram</option>
                  <option value="none"${user.reminder_channel !== "telegram" ? " selected" : ""}>Без напоминаний</option>
                </select>
              </div>
              <div class="setting-row">
                <div class="setting-info">
                  <div class="t">Тихие часы</div>
                  <div class="d">В это время уведомления не отправляются.</div>
                </div>
                <div class="quiet-row">
                  <input class="input input-sm" type="time" name="quiet_hours_start" value="${esc(quietStart)}" aria-label="Начало тихих часов">
                  <span class="faint">—</span>
                  <input class="input input-sm" type="time" name="quiet_hours_end" value="${esc(quietEnd)}" aria-label="Конец тихих часов">
                </div>
              </div>
              <div class="row end">
                <button type="submit" class="btn btn-soft btn-sm" data-role="save-reminders">Сохранить напоминания</button>
              </div>
            </form>

            <div class="telegram-card mt-2">
              <span class="telegram-icon">${icon("telegram")}</span>
              <div class="grow">
                <div class="t">Telegram ${user.telegram_connected ? "подключён" : "не подключён"}</div>
                <div class="d">${user.telegram_connected
                  ? "Напоминания приходят в бота. Можно отложить на час прямо из сообщения."
                  : "Подключите бота, чтобы получать мягкие напоминания."}</div>
              </div>
              <div class="actions">
                ${user.telegram_connected
                  ? `<button type="button" class="btn btn-soft btn-sm" data-action="telegram-disconnect">Отключить</button>`
                  : `<button type="button" class="btn btn-primary btn-sm" data-action="telegram-connect">Подключить</button>`}
              </div>
            </div>

            <div class="row between mt-3" style="gap:8px;flex-wrap:wrap">
              <span class="h3" style="font-size:13.5px">Журнал</span>
              <span class="tiny faint">последние ${notifications.length}</span>
            </div>
            ${notifications.length ? `
              <div class="notif-log">
                ${notifications.map((item) => `
                  <div class="notif-item">
                    ${icon("bell")}
                    <span>${esc(item.message || item.title || "Напоминание")}
                      ${item.status ? `<span class="faint"> · ${esc(item.status)}</span>` : ""}
                    </span>
                    <span class="time">${esc(formatDateTime(item.created_at))}</span>
                  </div>
                `).join("")}
              </div>
            ` : `<p class="tiny faint mt-1">Пока нет отправленных напоминаний.</p>`}
          </section>

          <section class="card settings-card">
            <h3>Внешний вид</h3>
            <p class="sub">Тёплая светлая тема или спокойная тёмная — выбор сохраняется.</p>
            <div class="setting-row" style="border-bottom:0;padding-bottom:0">
              <div class="setting-info">
                <div class="t">Тёмная тема</div>
                <div class="d">Мягкий контраст для вечерних отметок.</div>
              </div>
              ${switchHTML(store.theme === "dark", "theme", "Тёмная тема")}
            </div>
          </section>
        </div>

        <div class="settings-stack">
          <section class="card settings-card">
            <h3>AI-ассистент</h3>
            <p class="sub">Ключ хранится на сервере. Данные отправляются обезличенно и только с согласия.</p>
            <div class="setting-row">
              <div class="setting-info">
                <div class="t">AI-рекомендации</div>
                <div class="d">Подбор привычек и недельный обзор.</div>
              </div>
              ${switchHTML(Boolean(user.ai_enabled), "ai_enabled", "AI-рекомендации")}
            </div>
            <div class="setting-row">
              <div class="setting-info">
                <div class="t">Согласие на AI</div>
                <div class="d">Без него ассистент не отправляет даже обезличенные данные.</div>
              </div>
              ${switchHTML(Boolean(user.ai_consent), "ai_consent", "Согласие на AI")}
            </div>
            <div class="ai-note consent mt-2">
              ${icon("shield")}
              <span>${aiStatus
                ? `Сегодня использовано ${aiStatus.requests_today} из ${aiStatus.limit}. ${aiStatus.provider_ready ? "Внешний провайдер подключён." : "Внешний ключ не настроен — работает локальный план."}`
                : "Статус провайдера временно недоступен."}</span>
            </div>
          </section>

          <section class="card settings-card">
            <h3>Условия</h3>
            <p class="sub">Три мягких события. Срабатывают один раз и не повторяются.</p>
            ${CONDITION_ITEMS.map((item) => `
              <div class="setting-row">
                <div class="setting-info">
                  <div class="t">${esc(item.title)}</div>
                  <div class="d">${esc(item.text)}</div>
                </div>
                ${switchHTML(Boolean(settings[item.key]), `condition:${item.key}`, item.title)}
              </div>
            `).join("")}
            ${events.length ? `
              <div class="notif-log">
                ${events.map((item) => `
                  <div class="notif-item">
                    ${icon("bell")}
                    <span><strong>${esc(item.title)}</strong><br>${esc(item.message)}</span>
                    <span class="time">${esc(formatDateTime(item.created_at))}</span>
                  </div>
                `).join("")}
              </div>
            ` : `<p class="tiny faint mt-2">Событий пока нет — это хороший знак.</p>`}
          </section>

          <section class="card settings-card">
            <h3>Экспорт</h3>
            <p class="sub">Скачайте свои данные в удобном формате. PDF — спокойный отчёт за месяц.</p>
            <div class="data-buttons">
              <button type="button" class="btn btn-soft btn-sm" data-export="csv">${icon("table")} CSV</button>
              <button type="button" class="btn btn-soft btn-sm" data-export="json">${icon("file")} JSON</button>
              <button type="button" class="btn btn-soft btn-sm" data-export="pdf">${icon("download")} PDF-отчёт</button>
            </div>
          </section>

          <section class="card settings-card danger-card">
            <h3>Удаление аккаунта</h3>
            <p class="sub">Все привычки, отметки и настройки удалятся без возможности восстановления.</p>
            <button type="button" class="btn btn-danger" data-action="delete-account">${icon("trash")} Удалить аккаунт</button>
          </section>
        </div>
      </div>
    `;
    bind();
  }

  function bind() {
    root.querySelector("#settings-profile")?.addEventListener("submit", saveProfile);
    root.querySelector("#settings-reminders")?.addEventListener("submit", saveReminders);

    root.querySelectorAll("[data-toggle]").forEach((button) => {
      button.addEventListener("click", () => toggle(button));
    });
    root.querySelector('[data-action="telegram-connect"]')?.addEventListener("click", (event) => {
      connectTelegram(event.currentTarget);
    });
    root.querySelector('[data-action="telegram-disconnect"]')?.addEventListener("click", disconnectTelegram);
    root.querySelector('[data-action="delete-account"]')?.addEventListener("click", deleteAccount);
    root.querySelectorAll("[data-export]").forEach((button) => {
      button.addEventListener("click", () => {
        const kind = button.dataset.export;
        const paths = { csv: "/export.csv", json: "/export.json", pdf: "/export/report.pdf" };
        if (paths[kind]) {
          download(paths[kind]);
          toast(kind === "pdf" ? "PDF-отчёт скачивается" : "Файл скачивается", { type: "success" });
        }
      });
    });
  }

  async function patchSettings(payload, message = "Сохранено") {
    const response = await api.patch("/settings", payload);
    if (response?.user) {
      user = response.user;
      store.setUser(response.user);
      ctx.updateUser?.(response.user);
    }
    sync(message);
    return response;
  }

  async function saveProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('[data-role="save-profile"]');
    const nameInput = form.elements.namedItem("name");
    const name = nameInput.value.trim();
    if (!name) {
      toast("Введите имя.", { type: "error" });
      nameInput.focus();
      return;
    }
    setButtonBusy(button, true, "Сохраняем…");
    try {
      await patchSettings({
        name,
        timezone: form.timezone.value,
        goal: form.goal.value.trim(),
      }, "Профиль сохранён");
      toast("Профиль обновлён", { type: "success" });
    } catch (error) {
      toast(error.message || "Не удалось сохранить профиль.", { type: "error" });
    } finally {
      setButtonBusy(button, false);
    }
  }

  async function saveReminders(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('[data-role="save-reminders"]');
    setButtonBusy(button, true, "Сохраняем…");
    try {
      await patchSettings({
        reminder_channel: form.reminder_channel.value,
        quiet_hours_start: form.quiet_hours_start.value,
        quiet_hours_end: form.quiet_hours_end.value,
      }, "Напоминания сохранены");
      toast("Настройки напоминаний сохранены", { type: "success" });
    } catch (error) {
      toast(error.message || "Не удалось сохранить напоминания.", { type: "error" });
    } finally {
      setButtonBusy(button, false);
    }
  }

  async function toggle(button) {
    const key = button.dataset.toggle;
    const on = !button.classList.contains("on");

    if (key === "theme") {
      const theme = store.toggleTheme();
      button.classList.toggle("on", theme === "dark");
      button.setAttribute("aria-checked", String(theme === "dark"));
      try {
        await patchSettings({ theme }, "Тема сохранена");
      } catch {
        /* тема уже применена локально */
      }
      return;
    }

    button.disabled = true;
    try {
      if (key.startsWith("condition:")) {
        const conditionKey = key.split(":")[1];
        const response = await api.patch("/conditions", { [conditionKey]: on });
        conditions = conditions || {};
        conditions.settings = response.settings || { ...(conditions.settings || {}), [conditionKey]: on };
        button.classList.toggle("on", Boolean(conditions.settings[conditionKey]));
        button.setAttribute("aria-checked", String(Boolean(conditions.settings[conditionKey])));
        sync("Сохранено");
        return;
      }
      if (key === "ai_enabled" || key === "ai_consent") {
        const response = await patchSettings({ [key]: on }, "Сохранено");
        user = response.user;
        button.classList.toggle("on", Boolean(user[key]));
        button.setAttribute("aria-checked", String(Boolean(user[key])));
        if (key === "ai_enabled" || key === "ai_consent") {
          aiStatus = await api.get("/ai/status").catch(() => aiStatus);
        }
        return;
      }
    } catch (error) {
      toast(error.message || "Не удалось изменить настройку.", { type: "error" });
    } finally {
      button.disabled = false;
    }
  }

  async function connectTelegram(button) {
    setButtonBusy(button, true, "Готовим…");
    try {
      const response = await api.post("/telegram/connect");
      const isDemo = response.mode === "demo";
      const dialog = modal({
        title: "Подключение Telegram",
        subtitle: isDemo ? "Демо-режим: настоящий бот на сервере не настроен" : "Осталось нажать «Start» в боте",
        body: `
          <div class="stack">
            <p class="small muted">${esc(response.instruction || "")}</p>
            <div class="ai-summary">
              Код подключения: <strong>${esc(response.code)}</strong>
            </div>
            ${response.deep_link ? `
              <a class="btn btn-primary btn-block" href="${esc(response.deep_link)}" target="_blank" rel="noopener">
                ${icon("telegram")} Открыть бота
              </a>
            ` : ""}
            <p class="tiny faint">Код действует до следующего запроса. Не передавайте его другим людям.</p>
          </div>
        `,
        footer: `
          <button type="button" class="btn btn-ghost" data-role="cancel">Закрыть</button>
          ${isDemo ? `<button type="button" class="btn btn-primary" data-role="simulate">Подключить демо-режим</button>` : ""}
        `,
      });
      dialog.foot.querySelector('[data-role="cancel"]').addEventListener("click", () => dialog.close());
      dialog.foot.querySelector('[data-role="simulate"]')?.addEventListener("click", async (event) => {
        const simulateButton = event.currentTarget;
        setButtonBusy(simulateButton, true, "Подключаем…");
        try {
          const connected = await api.post("/telegram/simulate-connect");
          if (connected.user) {
            user = connected.user;
            store.setUser(connected.user);
            ctx.updateUser?.(connected.user);
          }
          dialog.close();
          toast("Telegram подключён в демо-режиме. Напоминания будут в журнале.", { type: "success" });
          await load(false);
        } catch (error) {
          toast(error.message || "Не удалось подключить демо-режим.", { type: "error" });
          setButtonBusy(simulateButton, false);
        }
      });
    } catch (error) {
      toast(error.message || "Не удалось начать подключение.", { type: "error" });
    } finally {
      setButtonBusy(button, false);
    }
  }

  async function disconnectTelegram() {
    const confirmed = await confirmDialog({
      title: "Отключить Telegram?",
      message: "Напоминания перестанут приходить в бота. Отметки и история сохранятся.",
      confirmLabel: "Отключить",
      danger: true,
    });
    if (!confirmed) return;
    try {
      const response = await api.post("/telegram/disconnect");
      if (response?.user) {
        user = response.user;
        store.setUser(response.user);
        ctx.updateUser?.(response.user);
      }
      toast("Telegram отключён", { type: "info" });
      await load(false);
    } catch (error) {
      toast(error.message || "Не удалось отключить Telegram.", { type: "error" });
    }
  }

  async function deleteAccount() {
    const word = await promptWord({
      title: "Удалить аккаунт?",
      message: "Все привычки, отметки, настройки и история AI будут удалены навсегда. Это действие нельзя отменить.",
      word: "УДАЛИТЬ",
      confirmLabel: "Удалить навсегда",
    });
    if (!word) return;
    try {
      await api.delete("/account", { confirm: word });
      store.clear();
      toast("Аккаунт удалён. Спасибо, что были с нами.", { type: "info", duration: 6000 });
      ctx.accountDeleted?.();
    } catch (error) {
      toast(error.message || "Не удалось удалить аккаунт.", { type: "error" });
    }
  }

  await load(true);
  return () => {
    alive = false;
  };
}
