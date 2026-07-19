const elements = {
  backToGameLink: document.querySelector("#back-to-game-link"),
  loginCard: document.querySelector("#login-card"),
  tokenForm: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  loginMessage: document.querySelector("#login-message"),
  schedule: document.querySelector("#schedule"),
  scheduleMessage: document.querySelector("#schedule-message"),
  daysSelect: document.querySelector("#days-select"),
  rotateVerificationButton: document.querySelector("#rotate-verification-button"),
  wordList: document.querySelector("#word-list"),
};

const TOKEN_KEY = "poeper-admin-token";
let adminToken = sessionStorage.getItem(TOKEN_KEY) || "";
let pollTimer = null;

function adminApiUrl(path) {
  const basePath = window.location.pathname.replace(/\/admin\/?$/, "");
  return `${basePath}/admin/api${path}`;
}

function gameUrl() {
  const basePath = window.location.pathname.replace(/\/admin\/?$/, "");
  return basePath || "/";
}

async function adminRequest(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "X-Admin-Token": adminToken,
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.detail || "Het beheer kon niet worden geladen.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function formatDate(value) {
  const date = new Date(`${value}T12:00:00`);
  return {
    weekday: new Intl.DateTimeFormat("nl-NL", { weekday: "long" }).format(date),
    date: new Intl.DateTimeFormat("nl-NL", {
      day: "numeric",
      month: "long",
    }).format(date),
  };
}

function renderWords(words) {
  elements.wordList.replaceChildren();
  words.forEach((item) => {
    const formattedDate = formatDate(item.date);
    const row = document.createElement("article");
    row.className = "word-item";

    const dateBlock = document.createElement("div");
    dateBlock.className = "word-date";
    dateBlock.innerHTML = `<strong>${formattedDate.weekday}</strong><span>${formattedDate.date}</span>`;

    const word = document.createElement("div");
    word.className = "word-tiles";
    [...item.word].forEach((letter) => {
      const tile = document.createElement("span");
      tile.textContent = letter;
      word.append(tile);
    });

    const details = document.createElement("div");
    const minimum = document.createElement("span");
    minimum.className = "minimum";
    minimum.textContent = `${item.minimum_attempts} minimale zetten`;
    details.append(minimum);
    if (item.overridden) {
      const badge = document.createElement("span");
      badge.className = "custom-badge";
      badge.textContent = "Aangepast";
      details.append(badge);
    }
    const assessmentBadge = document.createElement("span");
    const verificationState = item.common === true
      ? "common"
      : item.warning
        ? "unverified"
        : "verifying";
    assessmentBadge.className = `assessment-badge ${verificationState}`;
    assessmentBadge.textContent = item.common === true
      ? "Geverifieerd"
      : item.warning
        ? "Niet geverifieerd"
        : "Wordt geverifieerd…";
    details.append(assessmentBadge);
    if (item.warning) {
      const warning = document.createElement("span");
      warning.className = "warning-text";
      warning.textContent = item.warning;
      details.append(warning);
    }

    const rotateButton = document.createElement("button");
    rotateButton.className = "rotate-button";
    rotateButton.type = "button";
    rotateButton.textContent = "Wissel";
    rotateButton.addEventListener("click", () => rotateWord(item.date, rotateButton));

    const blacklistButton = document.createElement("button");
    blacklistButton.className = "blacklist-button";
    blacklistButton.type = "button";
    blacklistButton.textContent = "Blokkeer";
    blacklistButton.setAttribute("aria-label", `${item.word} op de zwarte lijst zetten`);
    blacklistButton.addEventListener("click", () => blacklistWord(
      item.date,
      item.word,
      blacklistButton,
    ));

    const actions = document.createElement("div");
    actions.className = "word-actions";
    actions.append(rotateButton, blacklistButton);

    row.append(dateBlock, word, details, actions);
    elements.wordList.append(row);
  });
  return words.some((item) => item.common === null && !item.warning);
}

async function blacklistWord(date, word, button) {
  if (!window.confirm(
    `${word} blokkeren? Het woord verdwijnt uit de planning en uit het spel.`,
  )) return;

  button.disabled = true;
  elements.scheduleMessage.textContent = "";
  try {
    await adminRequest(adminApiUrl(`/daily-words/${date}/blacklist`), {
      method: "POST",
    });
    await loadSchedule();
    elements.scheduleMessage.textContent = `${word} is geblokkeerd en vervangen.`;
  } catch (error) {
    elements.scheduleMessage.textContent = error.message;
    button.disabled = false;
  }
}

async function loadSchedule() {
  elements.scheduleMessage.textContent = "Laden…";
  try {
    const words = await adminRequest(
      adminApiUrl(`/daily-words?days=${elements.daysSelect.value}`),
    );
    const verificationPending = renderWords(words);
    elements.loginCard.hidden = true;
    elements.schedule.hidden = false;
    elements.scheduleMessage.textContent = verificationPending
      ? "Verificatie loopt op de achtergrond…"
      : "";
    clearTimeout(pollTimer);
    if (verificationPending) pollTimer = setTimeout(loadSchedule, 2000);
  } catch (error) {
    if (error.status === 401 || error.status === 503) {
      sessionStorage.removeItem(TOKEN_KEY);
      adminToken = "";
      elements.loginCard.hidden = false;
      elements.schedule.hidden = true;
      elements.loginMessage.textContent = error.message;
    } else {
      elements.scheduleMessage.textContent = error.message;
    }
  }
}

async function rotateWord(date, button) {
  button.disabled = true;
  elements.scheduleMessage.textContent = "";
  try {
    await adminRequest(adminApiUrl(`/daily-words/${date}/rotate`), {
      method: "POST",
    });
    await loadSchedule();
  } catch (error) {
    elements.scheduleMessage.textContent = error.message;
    button.disabled = false;
  }
}

async function rotateVerification() {
  const button = elements.rotateVerificationButton;
  button.disabled = true;
  elements.scheduleMessage.textContent = "Verificatie-rotatie gestart…";
  try {
    const result = await adminRequest(
      adminApiUrl(`/daily-words/rotate-verification?days=${elements.daysSelect.value}`),
      { method: "POST" },
    );
    await loadSchedule();
    elements.scheduleMessage.textContent =
      `Verificatierotatie voltooid: ${result.rotated_days}/${result.days} gewisseld.`
      + (result.failed_days
        ? ` ${result.failed_days} dag(en) konden niet worden gewisseld.`
        : "");
  } catch (error) {
    elements.scheduleMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

elements.tokenForm.addEventListener("submit", (event) => {
  event.preventDefault();
  adminToken = elements.tokenInput.value.trim();
  sessionStorage.setItem(TOKEN_KEY, adminToken);
  elements.loginMessage.textContent = "";
  loadSchedule();
});

elements.daysSelect.addEventListener("change", loadSchedule);
elements.rotateVerificationButton.addEventListener("click", rotateVerification);
elements.backToGameLink.href = gameUrl();
if (adminToken) loadSchedule();
