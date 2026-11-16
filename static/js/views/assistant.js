// AI-ассистент: подбор привычек, недельный обзор и история запросов.
import { api } from "../api.js";
import { habitIcon, icon } from "../icons.js";
import { emptyState, setButtonBusy, skeleton, toast } from "../ui.js";
import { esc, formatDateTime, pluralRu } from "../utils.js";

const TYPES = [
  { id: "boolean", label: "Да / нет" },
  { id: "quantity", label: "Количество" },
  { id: "duration", label: "Время" },
];
const SCHEDULES = [
  { id: "daily", label: "Каждый день" },
  { id: "weekdays", label: "По будням" },
  { id: "times_per_week", label: "N раз в неделю" },
];

const REQUEST_LABELS = {
  generate_habits: "Подбор привычек",
  weekly_review: "Недельный обзор",
};

export async function mount(root, ctx) {
  let tab = "generate";
  let status = null;
  let history = [];
  let plan = null;
  let provider = "";
  let fallback = false;
  let review = null;
  let reviewMeta = null;
  let alive = true;
  root.innerHTML = skeleton();

  async function load(showSkeleton = false) {
    if (showSkeleton) root.innerHTML = skeleton();
    try {
      const [statusData, historyData] = await Promise.all([
        api.get("/ai/status"),
        api.get("/ai/history", { limit: 8 }).catch(() => ({ requests: [] })),
      ]);
      if (!alive) return;
      status = statusData;
      history = historyData.requests || [];
      render();
    } catch (error) {
      if (!alive) return;
      root.innerHTML = `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("alert")}</div>
          <h2 class="h2">Ассистент временно недоступен</h2>
          <p class="muted small mt-1">${esc(error.message)}</p>
          <button type="button" class="btn btn-primary mt-3" data-action="retry">Попробовать снова</button>
        </div>
      `;
      root.querySelector('[data-action="retry"]')?.addEventListener("click", () => load(true));
    }
  }

  function canUse() {
    return Boolean(status?.enabled && status?.consent) && Number(status?.remaining ?? 1) > 0;
  }

  function accessNotice() {
    if (!status?.enabled) {
      return `
        <div class="ai-note consent">
          ${icon("shield")}
          <span>AI-рекомендации отключены. Включите их и дайте согласие в настройках — ключ хранится только на сервере.
            <button type="button" class="btn-link" data-action="open-settings">Открыть настройки</button>
          </span>
        </div>
      `;
    }
    if (!status?.consent) {
      return `
        <div class="ai-note consent">
          ${icon("shield")}
          <span>Нужно отдельное согласие на отправку обезличенных данных AI. Без него подбор и обзор недоступны.
            <button type="button" class="btn-link" data-action="open-settings">Дать согласие</button>
          </span>
        </div>
      `;
    }
    if (Number(status?.remaining ?? 0) <= 0) {
      return `
        <div class="ai-note">
          ${icon("clock")}
          <span>Лимит ${status.limit} AI-запросов в день исчерпан. Лимит обновится завтра — шаблоны привычек доступны в разделе «Привычки».</span>
        </div>
      `;
    }
    return "";
  }

  function render() {
    const remaining = Number(status?.remaining ?? 0);
    const limit = Number(status?.limit ?? 10);

    root.innerHTML = `
      <div class="page-head">
        <div class="page-title-block">
          <span class="kicker">AI-ассистент</span>
          <h1 class="display">Маленькие шаги <em>под вашу цель</em></h1>
          <p class="page-sub">Ассистент предлагает привычки и разбирает неделю. Без медицинских советов, давления и токсичной мотивации.</p>
        </div>
        <div class="page-actions">
          <span class="badge ${status?.provider_ready ? "badge-moss" : "badge-sand"}">
            ${icon(status?.provider_ready ? "sparkles" : "leaf")}
            ${status?.provider_ready ? "AI подключён" : "Локальный план"}
          </span>
          <span class="pill">${icon("zap")} осталось ${remaining} из ${limit}</span>
        </div>
      </div>

      ${accessNotice()}

      <div class="tabs mt-3" role="tablist" aria-label="Раздел ассистента">
        <button type="button" class="tab${tab === "generate" ? " active" : ""}" data-tab="generate"
                role="tab" aria-selected="${tab === "generate"}">Подобрать привычки</button>
        <button type="button" class="tab${tab === "review" ? " active" : ""}" data-tab="review"
                role="tab" aria-selected="${tab === "review"}">Недельный обзор</button>
      </div>

      <div class="mt-3">${tab === "generate" ? generateHTML() : reviewHTML()}</div>

      ${historyHTML()}

      <div class="ai-note mt-3">
        ${icon("info")}
        <span>AI работает с обезличенным описанием цели и статистикой выполнения. Персональные заметки и контакты не отправляются.
          Если внешний провайдер не настроен, используется локальный шаблонный план — приложение продолжает работать.</span>
      </div>
    `;
    bind();
  }

  function generateHTML() {
    const goal = plan?.goal || statusGoal();
    return `
      <div class="ai-grid">
        <div class="card card-pad">
          <h2 class="h2" style="font-size:20px">Опишите цель</h2>
          <p class="tiny muted mt-1 mb-2">Например: «вести блог 5 раз в неделю без выгорания» или «больше двигаться».</p>
          <div class="field">
            <label class="label" for="ai-goal">Цель <span class="optional">до 500 символов</span></label>
            <textarea class="textarea" id="ai-goal" maxlength="500" rows="4"
                      placeholder="Что хочется изменить и почему это важно">${esc(goal)}</textarea>
          </div>
          <button type="button" class="btn btn-primary btn-block mt-2" data-action="generate"${canUse() ? "" : " disabled"}>
            ${icon("sparkles")} Подобрать 3–5 привычек
          </button>
          <p class="hint mt-2">Сначала покажем превью. Вы сможете изменить названия и применить только то, что подходит.</p>
        </div>

        <div class="card card-pad" data-role="preview">
          ${plan ? planHTML(plan) : emptyState({
            iconName: "sparkles",
            title: "Здесь появится превью",
            text: "Опишите цель и нажмите кнопку. Привычки можно отредактировать до применения.",
          })}
        </div>
      </div>
    `;
  }

  function planHTML(current) {
    const habits = current.habits || [];
    return `
      <div class="row between mb-2" style="gap:10px;flex-wrap:wrap">
        <div>
          <h2 class="h2" style="font-size:20px">${habits.length} ${pluralRu(habits.length, "привычка", "привычки", "привычек")}</h2>
          <p class="tiny faint">${fallback ? "Локальный план — проверьте формулировки" : `Предложено ${provider || "AI"}`}</p>
        </div>
        <span class="badge badge-sand">Превью</span>
      </div>
      ${current.summary ? `<div class="ai-summary mb-2">${esc(current.summary)}</div>` : ""}
      ${habits.map((habit, index) => previewHabit(habit, index)).join("")}
      <div class="row between mt-3" style="gap:10px;flex-wrap:wrap">
        <span class="tiny faint">Применятся только отмеченные вами привычки.</span>
        <div class="row" style="gap:7px">
          <button type="button" class="btn btn-ghost btn-sm" data-action="discard">Отменить</button>
          <button type="button" class="btn btn-primary btn-sm" data-action="apply"${canUse() ? "" : " disabled"}>
            ${icon("check")} Применить
          </button>
        </div>
      </div>
    `;
  }

  function previewHabit(habit, index) {
    return `
      <div class="preview-habit" data-index="${index}">
        <div class="preview-habit-head">
          <input type="checkbox" class="preview-select" data-field="selected" checked
                 aria-label="Применить привычку ${index + 1}">
          <span class="habit-icon" style="--icon-color:${esc(habit.color || "#2E685F")}" aria-hidden="true">${habitIcon(habit.icon)}</span>
          <input class="input" data-field="title" maxlength="80" value="${esc(habit.title || "")}"
                 aria-label="Название привычки ${index + 1}">
        </div>
        ${habit.micro_step || habit.trigger ? `
          <div class="preview-trigger">
            ${icon("target")}
            <span>
              ${habit.micro_step ? `<strong>Микро-шаг:</strong> ${esc(habit.micro_step)}` : ""}
              ${habit.micro_step && habit.trigger ? " · " : ""}
              ${habit.trigger ? `<strong>Когда:</strong> ${esc(habit.trigger)}` : ""}
            </span>
          </div>
        ` : ""}
        <div class="preview-fields">
          <select class="select" data-field="type" aria-label="Тип привычки ${index + 1}">
            ${TYPES.map((item) => `<option value="${item.id}"${item.id === habit.type ? " selected" : ""}>${esc(item.label)}</option>`).join("")}
          </select>
          <input class="input input-sm" data-field="target_value" type="number" inputmode="decimal" min="0.1" step="any"
                 value="${esc(Number(habit.target_value) || 1)}" aria-label="Цель привычки ${index + 1}"
                 ${habit.type === "boolean" ? "hidden" : ""}>
          <input class="input input-sm" data-field="unit" maxlength="20" value="${esc(habit.unit || "")}"
                 placeholder="единица" aria-label="Единица привычки ${index + 1}" ${habit.type === "boolean" ? "hidden" : ""}>
          <select class="select" data-field="schedule" aria-label="Расписание привычки ${index + 1}">
            ${SCHEDULES.map((item) => `<option value="${item.id}"${item.id === habit.schedule ? " selected" : ""}>${esc(item.label)}</option>`).join("")}
          </select>
          <input class="input input-sm" data-field="times_per_week" type="number" min="1" max="7" step="1"
                 value="${esc(Number(habit.times_per_week) || 3)}" aria-label="Раз в неделю"
                 ${habit.schedule === "times_per_week" ? "" : "hidden"}>
        </div>
      </div>
    `;
  }

  function reviewHTML() {
    if (!review) {
      return `
        <div class="card card-pad text-center">
          <div class="empty-art" style="margin:0 auto 16px">${icon("calendar")}</div>
          <h2 class="h2">Недельный обзор</h2>
          <p class="muted small mt-1" style="max-width:52ch;margin-left:auto;margin-right:auto">
            Соберём мягкий разбор за 7 дней: что получилось, где были паузы и какие 2–3 маленьких шага
            помогут на следующей неделе.
          </p>
          <button type="button" class="btn btn-primary mt-3" data-action="review"${canUse() ? "" : " disabled"}>
            ${icon("sparkles")} Собрать обзор
          </button>
        </div>
      `;
    }

    const wins = review.wins || [];
    const gaps = review.gaps || [];
    const recommendations = review.recommendations || [];
    const habits = reviewMeta?.habits || [];
    return `
      <div class="card card-pad">
        <div class="row between mb-2" style="gap:10px;flex-wrap:wrap">
          <div>
            <h2 class="h2" style="font-size:20px">Итоги недели</h2>
            <p class="tiny faint">${reviewMeta?.period ? `${reviewMeta.period.from} — ${reviewMeta.period.to}` : "7 дней"}</p>
          </div>
          <button type="button" class="btn btn-soft btn-sm" data-action="review">
            ${icon("refresh")} Обновить
          </button>
        </div>
        ${review.summary ? `<div class="ai-summary mb-2">${esc(review.summary)}</div>` : ""}
        <div class="review-grid">
          <div class="review-col">
            <h4>${icon("checkCircle")} Что получилось</h4>
            <ul>${wins.map((item) => `<li>${esc(item)}</li>`).join("") || "<li>Пока нет данных — это тоже нормально.</li>"}</ul>
          </div>
          <div class="review-col gaps">
            <h4>${icon("pause")} Где была пауза</h4>
            <ul>${gaps.map((item) => `<li>${esc(item)}</li>`).join("") || "<li>Пауз не было или они не отмечены.</li>"}</ul>
          </div>
        </div>
        <div class="section-head" style="margin-bottom:8px">
          <h3 class="h3">Маленькие шаги на неделю</h3>
          <span class="tiny faint">${recommendations.length} ${pluralRu(recommendations.length, "рекомендация", "рекомендации", "рекомендаций")}</span>
        </div>
        <div class="rec-list" style="margin-top:0">
          ${recommendations.map((item, index) => `
            <div class="rec-item">
              <span class="rec-num">${index + 1}</span>
              <div class="rec-text">
                ${esc(item.text || "")}
                ${item.habit_title ? `<div class="tiny faint mt-1">Привычка: ${esc(item.habit_title)}${item.suggested_target ? ` · цель ${esc(item.suggested_target)}` : ""}</div>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
        ${habits.length ? `
          <div class="row wrap mt-3" style="gap:7px">
            ${habits.map((habit) => `<span class="pill">${esc(habit.title)}: ${Math.round(Number(habit.completion_percent ?? habit.week_percent ?? 0))}%</span>`).join("")}
          </div>
        ` : ""}
      </div>
    `;
  }

  function historyHTML() {
    if (!history.length) return "";
    return `
      <div class="section-head">
        <h2 class="section-title">История запросов</h2>
        <span class="tiny faint">последние ${history.length}</span>
      </div>
      <div class="card card-pad">
        <div class="rec-list" style="margin-top:0">
          ${history.map((item) => {
            const output = item.output || {};
            const summary = output.summary || (Array.isArray(output.habits) ? `${output.habits.length} привычек в плане` : "Ответ получен");
            return `
              <div class="rec-item">
                <span class="rec-num">${icon(item.type === "weekly_review" ? "calendar" : "sparkles")}</span>
                <div class="rec-text">
                  <div class="row between" style="gap:8px">
                    <strong>${esc(REQUEST_LABELS[item.type] || "Запрос")}</strong>
                    <span class="tiny faint">${esc(formatDateTime(item.created_at))}</span>
                  </div>
                  <div class="tiny muted mt-1">${esc(summary)}</div>
                  <div class="tiny faint mt-1">${esc(item.provider || "локально")} · ${item.status === "ok" ? "получено" : esc(item.status || "")}${item.type === "generate_habits" && Array.isArray(output.habits) ? ` · ${output.habits.length} привычек` : ""}</div>
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  function statusGoal() {
    return ctx.user?.goal || "";
  }

  function bind() {
    root.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.tab === tab) return;
        tab = button.dataset.tab;
        render();
      });
    });
    root.querySelector('[data-action="open-settings"]')?.addEventListener("click", () => ctx.navigate("settings"));
    root.querySelector('[data-action="generate"]')?.addEventListener("click", generate);
    root.querySelector('[data-action="review"]')?.addEventListener("click", runReview);
    root.querySelector('[data-action="discard"]')?.addEventListener("click", () => {
      plan = null;
      render();
    });
    root.querySelector('[data-action="apply"]')?.addEventListener("click", applyPlan);

    const preview = root.querySelector('[data-role="preview"]');
    if (!preview || !plan) return;
    preview.addEventListener("input", (event) => {
      const field = event.target.closest("[data-field]");
      const box = event.target.closest("[data-index]");
      if (!field || !box) return;
      const habit = plan.habits[Number(box.dataset.index)];
      if (!habit) return;
      const key = field.dataset.field;
      if (key === "selected") {
        habit.selected = field.checked;
        box.classList.toggle("is-off", !field.checked);
        return;
      }
      habit[key] = key === "times_per_week" || key === "target_value"
        ? Number(String(field.value).replace(",", ".")) || 0
        : field.value;
    });
    preview.addEventListener("change", (event) => {
      const field = event.target.closest("[data-field]");
      const box = event.target.closest("[data-index]");
      if (!field || !box) return;
      const habit = plan.habits[Number(box.dataset.index)];
      if (!habit) return;
      if (field.dataset.field === "type") {
        habit.type = field.value;
        const targetInput = box.querySelector('[data-field="target_value"]');
        const unitInput = box.querySelector('[data-field="unit"]');
        if (targetInput) targetInput.hidden = habit.type === "boolean";
        if (unitInput) unitInput.hidden = habit.type === "boolean";
      }
      if (field.dataset.field === "schedule") {
        habit.schedule = field.value;
        const timesInput = box.querySelector('[data-field="times_per_week"]');
        if (timesInput) timesInput.hidden = habit.schedule !== "times_per_week";
      }
    });
  }

  async function generate() {
    const button = root.querySelector('[data-action="generate"]');
    const goal = (root.querySelector("#ai-goal")?.value || "").trim();
    if (goal.length < 3) {
      toast("Опишите цель чуть подробнее — так план будет полезнее.", { type: "error" });
      root.querySelector("#ai-goal")?.focus();
      return;
    }
    setButtonBusy(button, true, "Подбираем…");
    try {
      const response = await api.post("/ai/generate", { goal });
      plan = {
        goal: response.goal || goal,
        summary: response.plan?.summary || "",
        habits: (response.plan?.habits || []).map((habit) => ({ ...habit, selected: true })),
      };
      provider = response.provider || "";
      fallback = Boolean(response.fallback);
      if (status) {
        status.requests_today = response.requests_today;
        status.remaining = response.remaining;
      }
      toast(fallback ? "Готов локальный план — можно отредактировать." : "План готов. Проверьте превью.", {
        type: "success",
      });
      await loadHistory();
      render();
    } catch (error) {
      if (["ai_disabled", "consent_required", "ai_rate_limit"].includes(error.code)) {
        toast(error.message, { type: "info" });
        await load(false);
      } else {
        toast(error.message || "Не удалось подобрать привычки.", { type: "error" });
        setButtonBusy(button, false);
      }
    }
  }

  async function runReview() {
    const button = root.querySelector('[data-action="review"]');
    setButtonBusy(button, true, "Собираем…");
    try {
      const response = await api.post("/ai/review");
      review = response.review || { wins: [], gaps: [], recommendations: [], summary: "" };
      reviewMeta = { period: response.period, habits: response.habits || [] };
      provider = response.provider || provider;
      fallback = Boolean(response.fallback);
      if (status) {
        status.requests_today = response.requests_today;
        status.remaining = response.remaining;
      }
      toast("Обзор готов — без оценок и давления.", { type: "success" });
      await loadHistory();
      render();
    } catch (error) {
      if (["ai_disabled", "consent_required", "ai_rate_limit"].includes(error.code)) {
        toast(error.message, { type: "info" });
        await load(false);
      } else {
        toast(error.message || "Не удалось собрать обзор.", { type: "error" });
        setButtonBusy(button, false);
      }
    }
  }

  async function loadHistory() {
    try {
      const response = await api.get("/ai/history", { limit: 8 });
      history = response.requests || [];
    } catch {
      /* история не критична */
    }
  }

  async function applyPlan() {
    if (!plan) return;
    const button = root.querySelector('[data-action="apply"]');
    const picked = plan.habits.filter((habit) => habit.selected !== false);
    if (!picked.length) {
      toast("Отметьте хотя бы одну привычку для применения.", { type: "error" });
      return;
    }
    const habits = picked.map((habit) => {
      const type = habit.type || "boolean";
      return {
        title: String(habit.title || "").trim(),
        description: habit.description || "",
        type,
        target_value: type === "boolean" ? 1 : Number(habit.target_value) || 1,
        unit: type === "boolean" ? "" : habit.unit || "раз",
        schedule: habit.schedule || "daily",
        times_per_week: Number(habit.times_per_week) || 3,
        reminder_time: habit.reminder_time || "09:00",
        freeze_limit: 2,
        icon: habit.icon || "spark",
        color: habit.color || "#2E685F",
      };
    });
    if (habits.some((habit) => !habit.title)) {
      toast("У каждой привычки должно быть название.", { type: "error" });
      return;
    }
    setButtonBusy(button, true, "Применяем…");
    try {
      const response = await api.post("/habits/batch", { habits });
      toast(`Добавлено ${response.created || habits.length} ${pluralRu(response.created || habits.length, "привычка", "привычки", "привычек")}.`, {
        type: "success",
      });
      plan = null;
      await load(false);
      ctx.navigate("habits");
    } catch (error) {
      toast(error.message || "Не удалось применить план.", { type: "error" });
      setButtonBusy(button, false);
    }
  }

  await load(true);
  return () => {
    alive = false;
  };
}
