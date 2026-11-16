// Короткий онбординг: имя, часовой пояс, цель и канал напоминаний.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { setButtonBusy, toast } from "../ui.js";
import { esc, safeTimezone, timezoneOptions } from "../utils.js";

const GOAL_EXAMPLES = [
  "Регулярно вести блог без выгорания",
  "Больше движения и меньше усталости",
  "Учить язык по 15 минут в день",
  "Спокойнее завершать день",
];

export function mount(root, ctx) {
  root.removeAttribute("aria-busy");
  const user = store.user || {};
  const state = {
    step: 1,
    name: user.name || "",
    timezone: user.timezone || safeTimezone(),
    goal: user.goal || "",
    channel: user.reminder_channel || "telegram",
  };
  const total = 3;

  function stepCopy() {
    if (state.step === 1) {
      return {
        title: "Как вас зовут?",
        sub: "Имя нужно только для тёплого приветствия. Часовой пояс помогает считать «сегодня» по вашему времени.",
      };
    }
    if (state.step === 2) {
      return {
        title: "Что хочется изменить?",
        sub: "Одна спокойная цель. AI-ассистент сможет предложить маленькие привычки под неё — без медицинских советов.",
      };
    }
    return {
      title: "Как напоминать?",
      sub: "Мягкие напоминания в Telegram. Время, тихие часы и отложить на час можно настроить позже.",
    };
  }

  function bodyHTML() {
    if (state.step === 1) {
      return `
        <div class="field">
          <label class="label" for="onboard-name">Имя</label>
          <input class="input" id="onboard-name" name="name" maxlength="80" autocomplete="given-name"
                 placeholder="Как к вам обращаться" value="${esc(state.name)}" autofocus>
        </div>
        <div class="field">
          <label class="label" for="onboard-tz">Часовой пояс</label>
          <select class="select" id="onboard-tz" name="timezone">
            ${timezoneOptions(state.timezone)}
          </select>
          <p class="hint">Определили автоматически. От него зависит дата отметок и время напоминаний.</p>
        </div>
      `;
    }
    if (state.step === 2) {
      return `
        <div class="field">
          <label class="label" for="onboard-goal">Цель <span class="optional">можно пропустить</span></label>
          <textarea class="textarea" id="onboard-goal" name="goal" maxlength="500"
                    placeholder="Например: вести блог 5 раз в неделю и не выгорать">${esc(state.goal)}</textarea>
        </div>
        <div class="field">
          <span class="hint">Можно взять пример:</span>
          <div class="goal-examples">
            ${GOAL_EXAMPLES.map((text) => `<button type="button" class="chip" data-goal="${esc(text)}">${esc(text)}</button>`).join("")}
          </div>
        </div>
      `;
    }
    return `
      <div class="choice-grid">
        <button type="button" class="choice-card${state.channel === "telegram" ? " active" : ""}" data-channel="telegram">
          <span class="choice-icon">${icon("telegram")}</span>
          <span>
            <span class="t">Telegram</span>
            <span class="d">Напоминания в удобное время, тихие часы и пауза на час.</span>
          </span>
        </button>
        <button type="button" class="choice-card${state.channel === "none" ? " active" : ""}" data-channel="none">
          <span class="choice-icon">${icon("bell")}</span>
          <span>
            <span class="t">Пока без напоминаний</span>
            <span class="d">Можно включить позже в настройках. Отмечать привычки это не мешает.</span>
          </span>
        </button>
      </div>
      <div class="ai-note consent">
        ${icon("shield")}
        <span>AI-ассистент работает только с обезличенными данными и только после отдельного согласия в настройках. Внешний ключ хранится на сервере.</span>
      </div>
      <div class="tip-card">
        ${icon("info")}
        <span><strong>Пропуск — не провал.</strong> Пропущенные дни остаются серыми, а заморозка помогает сохранить серию. Формулировки в приложении — «Пауза» и «Вернёмся завтра».</span>
      </div>
    `;
  }

  function render() {
    const copy = stepCopy();
    root.innerHTML = `
      <div class="onboard-wrap">
        <div class="onboard-top">
          <div class="brand">ритм<span>.</span></div>
          <div class="row">
            <div class="onboard-progress" aria-label="Шаг ${state.step} из ${total}">
              ${Array.from({ length: total }, (_, index) => {
                const n = index + 1;
                return `<span class="step-dot${n < state.step ? " done" : n === state.step ? " active" : ""}"></span>`;
              }).join("")}
            </div>
            <button type="button" class="icon-btn sm" data-action="logout" aria-label="Выйти">${icon("logout")}</button>
          </div>
        </div>

        <div class="onboard-card">
          <div class="onboard-step-label">Шаг ${state.step} из ${total}</div>
          <h1 class="onboard-title">${esc(copy.title)}</h1>
          <p class="onboard-sub">${esc(copy.sub)}</p>
          <div class="onboard-body">${bodyHTML()}</div>
          <div class="onboard-foot">
            <button type="button" class="btn btn-ghost" data-action="back"${state.step === 1 ? " disabled" : ""}>
              ${icon("chevronLeft")} Назад
            </button>
            <button type="button" class="btn btn-primary" data-action="next">
              ${state.step === total ? "Начать" : "Дальше"} ${state.step === total ? icon("check") : icon("chevronRight")}
            </button>
          </div>
        </div>
      </div>
    `;

    root.querySelectorAll("[data-goal]").forEach((button) => {
      button.addEventListener("click", () => {
        state.goal = button.dataset.goal;
        const textarea = root.querySelector("#onboard-goal");
        if (textarea) textarea.value = state.goal;
      });
    });
    root.querySelectorAll("[data-channel]").forEach((button) => {
      button.addEventListener("click", () => {
        state.channel = button.dataset.channel;
        root.querySelectorAll("[data-channel]").forEach((item) => {
          item.classList.toggle("active", item.dataset.channel === state.channel);
        });
      });
    });

    root.querySelector('[data-action="logout"]').addEventListener("click", () => ctx.logout?.());
    root.querySelector('[data-action="back"]').addEventListener("click", () => {
      collect();
      if (state.step > 1) {
        state.step -= 1;
        render();
      }
    });
    const nextButton = root.querySelector('[data-action="next"]');
    nextButton.addEventListener("click", async () => {
      collect();
      if (state.step < total) {
        if (state.step === 1 && !state.name.trim()) {
          toast("Введите имя — так приветствие будет теплее.", { type: "error" });
          root.querySelector("#onboard-name")?.focus();
          return;
        }
        state.step += 1;
        render();
        return;
      }
      if (!state.name.trim()) {
        state.step = 1;
        render();
        toast("Введите имя.", { type: "error" });
        return;
      }
      setButtonBusy(nextButton, true, "Сохраняем…");
      try {
        const data = await api.post("/auth/onboarding", {
          name: state.name.trim(),
          timezone: state.timezone,
          goal: state.goal.trim(),
          reminder_channel: state.channel,
        });
        toast("Готово. Начнём с сегодняшнего дня.", { type: "success" });
        ctx.onAuth?.({ user: data.user, onboarding_needed: false });
      } catch (error) {
        toast(error.message || "Не удалось завершить настройку.", { type: "error" });
        setButtonBusy(nextButton, false);
      }
    });
  }

  function collect() {
    const name = root.querySelector("#onboard-name");
    const timezone = root.querySelector("#onboard-tz");
    const goal = root.querySelector("#onboard-goal");
    if (name) state.name = name.value;
    if (timezone) state.timezone = timezone.value;
    if (goal) state.goal = goal.value;
  }

  render();
}
