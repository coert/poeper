const elements = {
  loginCard: document.querySelector("#login-card"),
  tokenForm: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  loginMessage: document.querySelector("#login-message"),
  schedule: document.querySelector("#schedule"),
  scheduleMessage: document.querySelector("#schedule-message"),
  daysSelect: document.querySelector("#days-select"),
  wordList: document.querySelector("#word-list"),
};

const TOKEN_KEY = "poeper-admin-token";
let adminToken = sessionStorage.getItem(TOKEN_KEY) || "";
let pollTimer = null;

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

    row.append(dateBlock, word, details, rotateButton);
    elements.wordList.append(row);
  });
  return words.some((item) => item.common === null && !item.warning);
}

async function loadSchedule() {
  elements.scheduleMessage.textContent = "Laden…";
  try {
    const words = await adminRequest(
      `/admin/api/daily-words?days=${elements.daysSelect.value}`,
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
    await adminRequest(`/admin/api/daily-words/${date}/rotate`, { method: "POST" });
    await loadSchedule();
  } catch (error) {
    elements.scheduleMessage.textContent = error.message;
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
if (adminToken) loadSchedule();
