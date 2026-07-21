const elements = {
  backToGameLink: document.querySelector("#back-to-game-link"),
  loginCard: document.querySelector("#login-card"),
  tokenForm: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  loginMessage: document.querySelector("#login-message"),
  schedule: document.querySelector("#schedule"),
  scheduleMessage: document.querySelector("#schedule-message"),
  schedulePageSize: document.querySelector("#schedule-page-size"),
  schedulePagination: document.querySelector("#schedule-pagination"),
  schedulePrevious: document.querySelector("#schedule-previous"),
  scheduleNext: document.querySelector("#schedule-next"),
  schedulePageInfo: document.querySelector("#schedule-page-info"),
  rotateVerificationButton: document.querySelector("#rotate-verification-button"),
  wordList: document.querySelector("#word-list"),
  performance: document.querySelector("#performance"),
  performanceMessage: document.querySelector("#performance-message"),
  performanceEmpty: document.querySelector("#performance-empty"),
  performanceTableWrap: document.querySelector("#performance-table-wrap"),
  performanceBody: document.querySelector("#performance-body"),
  performancePageSize: document.querySelector("#performance-page-size"),
  performancePagination: document.querySelector("#performance-pagination"),
  performancePrevious: document.querySelector("#performance-previous"),
  performanceNext: document.querySelector("#performance-next"),
  performancePageInfo: document.querySelector("#performance-page-info"),
};

const TOKEN_KEY = "poeper-admin-token";
let adminToken = sessionStorage.getItem(TOKEN_KEY) || "";
let pollTimer = null;
const scheduleState = { items: [], page: 1, pageSize: 7 };
const performanceState = { items: [], page: 1, pageSize: 7 };

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
    if (item.warning) {
      const verifyButton = document.createElement("button");
      verifyButton.className = "verify-button";
      verifyButton.type = "button";
      verifyButton.textContent = "Herverifieer";
      verifyButton.addEventListener("click", () => retryVerification(
        item.date,
        item.word,
        verifyButton,
      ));
      actions.prepend(verifyButton);
    }

    row.append(dateBlock, word, details, actions);
    elements.wordList.append(row);
  });
}

function updatePagination(state, paginationElements) {
  const totalPages = Math.max(1, Math.ceil(state.items.length / state.pageSize));
  state.page = Math.min(Math.max(1, state.page), totalPages);
  paginationElements.info.textContent = `Pagina ${state.page} van ${totalPages}`;
  paginationElements.previous.disabled = state.page === 1;
  paginationElements.next.disabled = state.page === totalPages;
}

function pageItems(state) {
  const start = (state.page - 1) * state.pageSize;
  return state.items.slice(start, start + state.pageSize);
}

function renderSchedulePage() {
  updatePagination(scheduleState, {
    previous: elements.schedulePrevious,
    next: elements.scheduleNext,
    info: elements.schedulePageInfo,
  });
  renderWords(pageItems(scheduleState));
}

function formatAverage(value, { abovePar = false } = {}) {
  if (value === null) return "—";
  const formatted = value.toLocaleString("nl-NL", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return abovePar ? `+${formatted}` : formatted;
}

function renderPerformancePage() {
  updatePagination(performanceState, {
    previous: elements.performancePrevious,
    next: elements.performanceNext,
    info: elements.performancePageInfo,
  });
  const results = pageItems(performanceState);
  elements.performanceBody.replaceChildren();
  elements.performanceEmpty.hidden = performanceState.items.length > 0;
  elements.performanceTableWrap.hidden = performanceState.items.length === 0;
  elements.performancePagination.hidden = performanceState.items.length === 0;

  results.forEach((item) => {
    const formattedDate = formatDate(item.date);
    const row = document.createElement("tr");
    const dateCell = document.createElement("th");
    dateCell.scope = "row";
    dateCell.innerHTML = `<strong>${formattedDate.weekday}</strong><span>${formattedDate.date}</span>`;

    const players = document.createElement("td");
    players.textContent = item.players.toLocaleString("nl-NL");
    const solved = document.createElement("td");
    solved.textContent = item.solved.toLocaleString("nl-NL");
    const averageSteps = document.createElement("td");
    averageSteps.textContent = formatAverage(item.average_steps);
    const averageAbovePar = document.createElement("td");
    averageAbovePar.textContent = formatAverage(
      item.average_above_par,
      { abovePar: true },
    );

    row.append(dateCell, players, solved, averageSteps, averageAbovePar);
    elements.performanceBody.append(row);
  });
}

function showLoginError(error) {
  sessionStorage.removeItem(TOKEN_KEY);
  adminToken = "";
  elements.loginCard.hidden = false;
  elements.schedule.hidden = true;
  elements.performance.hidden = true;
  elements.loginMessage.textContent = error.message;
}

async function loadPerformance() {
  elements.performanceMessage.textContent = "Laden…";
  try {
    const results = await adminRequest(adminApiUrl("/performance"));
    performanceState.items = results;
    renderPerformancePage();
    elements.loginCard.hidden = true;
    elements.performance.hidden = false;
    elements.performanceMessage.textContent = "";
  } catch (error) {
    if (error.status === 401 || error.status === 503) {
      showLoginError(error);
    } else {
      elements.performance.hidden = false;
      elements.performanceMessage.textContent = error.message;
    }
  }
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

async function retryVerification(date, word, button) {
  button.disabled = true;
  button.textContent = "Bezig…";
  elements.scheduleMessage.textContent = "";
  try {
    const result = await adminRequest(adminApiUrl(`/daily-words/${date}/verify`), {
      method: "POST",
    });
    await loadSchedule();
    elements.scheduleMessage.textContent = result.warning
      ? `Herverificatie van ${word} is niet gelukt.`
      : `${word} is opnieuw geverifieerd.`;
  } catch (error) {
    elements.scheduleMessage.textContent = error.message;
    button.disabled = false;
    button.textContent = "Herverifieer";
  }
}

async function loadSchedule() {
  elements.scheduleMessage.textContent = "Laden…";
  try {
    const words = await adminRequest(
      adminApiUrl("/daily-words?days=30"),
    );
    scheduleState.items = words;
    renderSchedulePage();
    const verificationPending = words.some(
      (item) => item.common === null && !item.warning,
    );
    elements.loginCard.hidden = true;
    elements.schedule.hidden = false;
    elements.scheduleMessage.textContent = verificationPending
      ? "Verificatie loopt op de achtergrond…"
      : "";
    clearTimeout(pollTimer);
    if (verificationPending) pollTimer = setTimeout(loadSchedule, 2000);
  } catch (error) {
    if (error.status === 401 || error.status === 503) {
      showLoginError(error);
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
      adminApiUrl("/daily-words/rotate-verification?days=30"),
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
  loadPerformance();
});

elements.schedulePageSize.addEventListener("change", () => {
  scheduleState.pageSize = Number(elements.schedulePageSize.value);
  scheduleState.page = 1;
  renderSchedulePage();
});
elements.schedulePrevious.addEventListener("click", () => {
  scheduleState.page -= 1;
  renderSchedulePage();
});
elements.scheduleNext.addEventListener("click", () => {
  scheduleState.page += 1;
  renderSchedulePage();
});
elements.performancePageSize.addEventListener("change", () => {
  performanceState.pageSize = Number(elements.performancePageSize.value);
  performanceState.page = 1;
  renderPerformancePage();
});
elements.performancePrevious.addEventListener("click", () => {
  performanceState.page -= 1;
  renderPerformancePage();
});
elements.performanceNext.addEventListener("click", () => {
  performanceState.page += 1;
  renderPerformancePage();
});
elements.rotateVerificationButton.addEventListener("click", rotateVerification);
elements.backToGameLink.href = gameUrl();
if (adminToken) {
  loadSchedule();
  loadPerformance();
}
