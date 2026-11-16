// Экран входа и регистрации.
import { api } from "../api.js";
import { icon } from "../icons.js";
import { setButtonBusy, toast } from "../ui.js";
import { esc, safeTimezone, todayISO, formatDate } from "../utils.js";

const DEMO_EMAIL = "demo@treker.local";
const DEMO_PASSWORD = "demo1234";

export function mount(root, ctx) {
  root.removeAttribute("aria-busy");
  let mode = "login";

  function previewRow(label, meta, done) {
    return `
      <div class="auth-demo-habit">
        <span class="auth-demo-check${done ? " done" : ""}">${icon("check")}</span>
        <span>${esc(label)}</span>
        <span class="m">${esc(meta)}</span>
      </div>
    `;
  }

  function render() {
    const isLogin = mode === "login";
    root.innerHTML = `
      <div class="auth-wrap">
        <section class="auth-visual" aria-hidden="true">
          <div class="auth-brand">ритм<span>.</span></div>
          <div>
            <div class="auth-quote">Привычки без <em>давления</em> и идеальности.</div>
            <p class="auth-sub">Отмечайте маленькие шаги, возвращайтесь после пауз и смотрите на ритм, а не на ошибки.</p>
            <div class="auth-preview">
              <div class="auth-preview-head">
                <span class="t">Сегодня</span>
                <span class="d">${formatDate(todayISO())}</span>
              </div>
              ${previewRow("Stories до 12:00", "09:30", true)}
              ${previewRow("Сценарий Reels", "20 мин", true)}
              ${previewRow("Прогулка 30 минут", "18:00", false)}
              ${previewRow("Вода 6 стаканов", "11:00", false)}
            </div>
          </div>
          <div class="auth-foot">Личный кабинет · данные не уходят третьим лицам без вашего согласия</div>
        </section>

        <section class="auth-form-side">
          <div class="auth-card">
            <div class="brand">ритм<span>.</span></div>
            <h1 class="auth-title">${isLogin ? "С возвращением" : "Начнём спокойно"}</h1>
            <p class="auth-subtitle">${isLogin
              ? "Войдите, чтобы увидеть свой ритм."
              : "Один аккаунт, без лишних полей. Пароль — не короче 8 символов."}</p>

            <div class="segmented block auth-tabs" role="tablist" aria-label="Вход или регистрация">
              <button type="button" class="seg-btn${isLogin ? " active" : ""}" role="tab"
                      aria-selected="${isLogin}" data-mode="login">Вход</button>
              <button type="button" class="seg-btn${!isLogin ? " active" : ""}" role="tab"
                      aria-selected="${!isLogin}" data-mode="register">Регистрация</button>
            </div>

            <div class="auth-error" id="auth-error" role="alert" hidden></div>

            <form class="auth-form" id="auth-form" novalidate>
              ${isLogin ? "" : `
                <div class="field">
                  <label class="label" for="auth-name">Как вас зовут</label>
                  <input class="input" id="auth-name" name="name" maxlength="80" autocomplete="name"
                         placeholder="Имя" required>
                </div>
              `}
              <div class="field">
                <label class="label" for="auth-email">Email</label>
                <input class="input" id="auth-email" name="email" type="email" autocomplete="email"
                       placeholder="you@example.com" required value="${isLogin ? esc(DEMO_EMAIL) : ""}">
              </div>
              <div class="field">
                <label class="label" for="auth-password">Пароль</label>
                <div class="password-wrap">
                  <input class="input" id="auth-password" name="password" type="password"
                         autocomplete="${isLogin ? "current-password" : "new-password"}"
                         placeholder="Не короче 8 символов" minlength="8" required
                         value="${isLogin ? esc(DEMO_PASSWORD) : ""}">
                  <button type="button" class="icon-btn sm password-toggle" data-action="toggle-password"
                          aria-label="Показать пароль">${icon("eye")}</button>
                </div>
              </div>
              <input type="hidden" name="timezone" value="${esc(safeTimezone())}">
              <button type="submit" class="btn btn-primary btn-block" data-role="submit">
                ${isLogin ? "Войти" : "Создать аккаунт"}
              </button>
            </form>

            <div class="auth-demo">
              <p>Хотите посмотреть без регистрации? В демо-кабинете уже есть история за 75 дней.</p>
              <button type="button" class="btn btn-soft btn-block" data-action="demo">
                ${icon("sparkles")} Открыть демо-кабинет
              </button>
              <p class="tiny faint mt-1">${DEMO_EMAIL} · ${DEMO_PASSWORD}</p>
            </div>

            <div class="auth-legal">
              Продолжая, вы соглашаетесь с бережной обработкой данных внутри приложения.
              Часовой пояс определяется автоматически.
            </div>
          </div>
        </section>
      </div>
    `;

    const form = root.querySelector("#auth-form");
    const errorBox = root.querySelector("#auth-error");
    const submit = form.querySelector('[data-role="submit"]');

    root.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.mode === mode) return;
        mode = button.dataset.mode;
        render();
      });
    });

    root.querySelector('[data-action="toggle-password"]')?.addEventListener("click", (event) => {
      const input = form.querySelector("#auth-password");
      const button = event.currentTarget;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.innerHTML = icon(show ? "eyeOff" : "eye");
      button.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
    });

    function showError(message) {
      errorBox.textContent = message;
      errorBox.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorBox.hidden = true;
      const nameInput = form.elements.namedItem("name");
      const emailInput = form.elements.namedItem("email");
      const passwordInput = form.elements.namedItem("password");
      const name = nameInput?.value.trim() || "";
      const email = emailInput.value.trim();
      const password = passwordInput.value;
      if (mode === "register" && !name) {
        showError("Введите имя.");
        nameInput.focus();
        return;
      }
      if (!email || !email.includes("@")) {
        showError("Введите корректный email.");
        emailInput.focus();
        return;
      }
      if (password.length < 8) {
        showError("Пароль должен содержать не менее 8 символов.");
        passwordInput.focus();
        return;
      }
      setButtonBusy(submit, true, mode === "login" ? "Входим…" : "Создаём…");
      try {
        const payload = mode === "login"
          ? { email, password }
          : { name, email, password, timezone: form.timezone.value || safeTimezone() };
        const data = await api.post(mode === "login" ? "/auth/login" : "/auth/register", payload);
        toast(mode === "login" ? "С возвращением" : "Аккаунт создан. Осталось несколько шагов.", { type: "success" });
        ctx.onAuth?.(data);
      } catch (error) {
        showError(error.message || "Не удалось войти.");
      } finally {
        setButtonBusy(submit, false);
      }
    });

    root.querySelector('[data-action="demo"]').addEventListener("click", async (event) => {
      const button = event.currentTarget;
      setButtonBusy(button, true, "Открываем…");
      try {
        const data = await api.post("/auth/demo");
        toast("Демо-кабинет открыт", { type: "success" });
        ctx.onAuth?.(data);
      } catch (error) {
        showError(error.message || "Демо-кабинет недоступен.");
      } finally {
        setButtonBusy(button, false);
      }
    });
  }

  render();
}
