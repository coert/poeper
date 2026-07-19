const elements = {
  loading: document.querySelector("#loading"),
  ladder: document.querySelector("#ladder"),
  goal: document.querySelector("#goal"),
  goalWord: document.querySelector("#goal-word"),
  form: document.querySelector("#entry-form"),
  input: document.querySelector("#word-input"),
  submit: document.querySelector("#submit-button"),
  message: document.querySelector("#message"),
  keyboard: document.querySelector("#keyboard"),
  attempts: document.querySelector("#attempt-count"),
  date: document.querySelector("#puzzle-date"),
  target: document.querySelector("#target-label"),
  result: document.querySelector("#result"),
  resultTitle: document.querySelector("#result-title"),
  resultAttempts: document.querySelector("#result-attempts"),
  resultMinimum: document.querySelector("#result-minimum"),
  resultCopy: document.querySelector("#result-copy"),
  shareButton: document.querySelector("#share-button"),
  shareDialog: document.querySelector("#share-dialog"),
  shareClose: document.querySelector("#share-close"),
  sharePreview: document.querySelector("#share-preview"),
  shareCopyButton: document.querySelector("#share-copy-button"),
  copyStatus: document.querySelector("#copy-status"),
  statisticsButton: document.querySelector("#statistics-button"),
  statisticsDialog: document.querySelector("#statistics-dialog"),
  statisticsClose: document.querySelector("#statistics-close"),
  statisticsPlayed: document.querySelector("#statistics-played"),
  statisticsAverage: document.querySelector("#statistics-average"),
  statisticsAbovePar: document.querySelector("#statistics-above-par"),
  statisticsHistogram: document.querySelector("#statistics-histogram"),
  countdownTimer: document.querySelector("#countdown-timer"),
  helpButton: document.querySelector("#help-button"),
  helpDialog: document.querySelector("#help-dialog"),
  helpClose: document.querySelector("#help-close"),
};

const statisticsCookieName = "poeper_results";
const statisticsCookieMaxAge = 60 * 60 * 24 * 400;

const keyboardRows = [
  [..."QWERTYUIOP"],
  [..."ASDFGHJKL"],
  ["ENTER", ..."ZXCVBNM", "BACKSPACE"],
];
let gameState = null;
let nextWordAt = getNextMidnight();

function readStatistics() {
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${statisticsCookieName}=`));
  if (!cookie) {
    return {
      lastDate: null,
      lastParDate: null,
      distribution: {},
      aboveParTotal: 0,
      aboveParGames: 0,
    };
  }

  try {
    const stored = JSON.parse(decodeURIComponent(cookie.slice(cookie.indexOf("=") + 1)));
    if (!stored || typeof stored.distribution !== "object") throw new Error("Invalid statistics");
    const distribution = {};
    Object.entries(stored.distribution).forEach(([attempts, count]) => {
      if (/^[1-9]\d*$/.test(attempts) && Number.isInteger(count) && count > 0) {
        distribution[attempts] = count;
      }
    });
    return {
      lastDate: typeof stored.lastDate === "string" ? stored.lastDate : null,
      lastParDate: typeof stored.lastParDate === "string" ? stored.lastParDate : null,
      distribution,
      aboveParTotal: Number.isInteger(stored.aboveParTotal) && stored.aboveParTotal >= 0
        ? stored.aboveParTotal
        : 0,
      aboveParGames: Number.isInteger(stored.aboveParGames) && stored.aboveParGames >= 0
        ? stored.aboveParGames
        : 0,
    };
  } catch (error) {
    return {
      lastDate: null,
      lastParDate: null,
      distribution: {},
      aboveParTotal: 0,
      aboveParGames: 0,
    };
  }
}

function writeStatistics(statistics) {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${statisticsCookieName}=${encodeURIComponent(JSON.stringify(statistics))}`
    + `; Max-Age=${statisticsCookieMaxAge}; Path=/; SameSite=Lax${secure}`;
}

function recordCompletedGame(state) {
  if (!state.completed) return;
  const statistics = readStatistics();
  let changed = false;

  if (statistics.lastDate !== state.date) {
    const attempts = String(state.attempts);
    statistics.distribution[attempts] = (statistics.distribution[attempts] || 0) + 1;
    statistics.lastDate = state.date;
    changed = true;
  }
  if (statistics.lastParDate !== state.date) {
    statistics.aboveParTotal += state.attempts - state.minimum_attempts;
    statistics.aboveParGames += 1;
    statistics.lastParDate = state.date;
    changed = true;
  }
  if (changed) writeStatistics(statistics);
}

function renderStatistics() {
  const statistics = readStatistics();
  const entries = Object.entries(statistics.distribution)
    .map(([attempts, count]) => [Number(attempts), count])
    .sort((first, second) => first[0] - second[0]);
  const gamesPlayed = entries.reduce((total, [, count]) => total + count, 0);
  const attemptsTotal = entries.reduce(
    (total, [attempts, count]) => total + attempts * count,
    0,
  );
  const largestCount = Math.max(1, ...entries.map(([, count]) => count));

  elements.statisticsPlayed.textContent = gamesPlayed;
  elements.statisticsAverage.textContent = gamesPlayed
    ? (attemptsTotal / gamesPlayed).toLocaleString("nl-NL", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })
    : "0";
  elements.statisticsAbovePar.textContent = statistics.aboveParGames
    ? `+${(statistics.aboveParTotal / statistics.aboveParGames).toLocaleString("nl-NL", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`
    : "—";
  elements.statisticsHistogram.replaceChildren();

  entries.forEach(([attempts, count]) => {
    const row = document.createElement("div");
    row.className = "histogram-row";
    const label = document.createElement("span");
    label.className = "histogram-label";
    label.textContent = attempts;
    label.setAttribute("aria-label", `${attempts} ${attempts === 1 ? "zet" : "zetten"}`);
    const track = document.createElement("div");
    track.className = "histogram-track";
    const bar = document.createElement("div");
    bar.className = "histogram-bar";
    bar.style.width = `${(count / largestCount) * 100}%`;
    bar.textContent = count;
    track.append(bar);
    row.append(label, track);
    elements.statisticsHistogram.append(row);
  });
}

function openStatisticsDialog() {
  renderStatistics();
  elements.statisticsDialog.showModal();
}

function getNextMidnight() {
  const midnight = new Date();
  midnight.setHours(24, 0, 0, 0);
  return midnight;
}

function updateCountdown() {
  const remaining = nextWordAt.getTime() - Date.now();
  if (remaining <= 0) {
    nextWordAt = getNextMidnight();
    loadGame();
    return;
  }

  const totalSeconds = Math.ceil(remaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const value = [hours, minutes, seconds]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
  elements.countdownTimer.textContent = value;
  elements.countdownTimer.setAttribute(
    "aria-label",
    `${hours} uur, ${minutes} minuten en ${seconds} seconden tot het volgende woord`,
  );
}

function createShareText(state) {
  let previousWord = state.start_word;
  const rows = state.entries.map((word) => {
    const squares = [...word].map((letter, index) => {
      if (state.target_word[index] === letter) return "🟩";
      if (previousWord[index] !== letter) return "🟨";
      return "⬜";
    }).join("");
    previousWord = word;
    return squares;
  });
  const distanceFromPar = state.attempts - state.minimum_attempts;
  const parLine = distanceFromPar === 0
    ? `Op par (${state.minimum_attempts})`
    : `${distanceFromPar > 0 ? "+" : ""}${distanceFromPar} van par (${state.minimum_attempts})`;
  return [
    `POEPER 💩 ${state.date}`,
    "",
    ...rows,
    "",
    parLine,
  ].join("\n");
}

function createWordRow(word, previousWord = "", targetWord = "") {
  const row = document.createElement("div");
  row.className = "word-row";

  [...word].forEach((letter, index) => {
    const tile = document.createElement("span");
    tile.className = "tile";
    if (targetWord && targetWord[index] === letter) {
      tile.classList.add("correct");
    } else if (previousWord && previousWord[index] !== letter) {
      tile.classList.add("changed");
    }
    tile.textContent = letter;
    row.append(tile);
  });
  return row;
}

function addLadderStep(word, previousWord, targetWord, label, completed) {
  const step = document.createElement("div");
  step.className = `ladder-step${completed ? " completed" : ""}`;
  const stepLabel = document.createElement("span");
  stepLabel.className = "step-label";
  stepLabel.textContent = label;
  step.append(stepLabel, createWordRow(word, previousWord, targetWord));
  elements.ladder.append(step);
}

function renderState(state) {
  gameState = state;
  elements.loading.hidden = true;
  elements.ladder.replaceChildren();
  elements.goalWord.replaceChildren(...createWordRow(state.target_word).children);
  elements.attempts.textContent = state.attempts;
  elements.target.textContent = state.target_word;
  elements.date.textContent = new Intl.DateTimeFormat("nl-NL", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(`${state.date}T12:00:00`));

  addLadderStep(state.start_word, "", state.target_word, "START", false);
  let previousWord = state.start_word;
  state.entries.forEach((word, index) => {
    const isFinal = state.completed && index === state.entries.length - 1;
    addLadderStep(
      word,
      previousWord,
      state.target_word,
      String(index + 1).padStart(2, "0"),
      isFinal,
    );
    previousWord = word;
  });

  elements.goal.hidden = state.completed;
  elements.form.hidden = state.completed;
  elements.keyboard.hidden = state.completed;
  elements.result.hidden = !state.completed;

  if (state.completed) {
    recordCompletedGame(state);
    const extra = state.attempts - state.minimum_attempts;
    elements.resultTitle.textContent = extra > 2
      ? "Je hebt ’m eruit geperst."
      : "Die boodschap kwam er vlot uit.";
    elements.resultAttempts.textContent = state.attempts;
    elements.resultMinimum.textContent = state.minimum_attempts;
    elements.resultCopy.textContent = extra === 0
      ? "De kortste route — perfect gespeeld."
      : `${extra} ${extra === 1 ? "zet" : "zetten"} boven de kortste route.`;
    elements.sharePreview.textContent = createShareText(state);
  } else {
    elements.input.value = "";
    elements.input.focus();
  }
}

async function copyShareResult() {
  const shareText = createShareText(gameState);
  try {
    await navigator.clipboard.writeText(shareText);
  } catch (error) {
    const textArea = document.createElement("textarea");
    textArea.value = shareText;
    textArea.setAttribute("readonly", "");
    textArea.className = "clipboard-fallback";
    document.body.append(textArea);
    textArea.select();
    const copied = document.execCommand("copy");
    textArea.remove();
    if (!copied) {
      elements.copyStatus.textContent = "Kopiëren lukte niet. Selecteer het overzicht hierboven.";
      return;
    }
  }
  elements.copyStatus.textContent = "Overzicht gekopieerd!";
  elements.shareCopyButton.textContent = "Gekopieerd";
}

function openShareDialog() {
  if (!gameState?.completed) return;
  elements.sharePreview.textContent = createShareText(gameState);
  elements.copyStatus.textContent = "";
  elements.shareCopyButton.textContent = "Kopieer overzicht";
  elements.shareDialog.showModal();
}

async function requestGame(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.detail || "Er ging iets mis.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function loadGame() {
  try {
    renderState(await requestGame("game"));
  } catch (error) {
    elements.loading.textContent = error.message;
  }
}

async function submitWord(event) {
  event.preventDefault();
  const word = elements.input.value.replace(/[^a-z]/gi, "").toUpperCase();
  if (word.length !== 4) {
    showError("Vul precies vier letters in.");
    return;
  }

  elements.submit.disabled = true;
  elements.message.textContent = "";
  const wasCompleted = gameState?.completed ?? false;
  try {
    const state = await requestGame("game/entries", {
      method: "POST",
      body: JSON.stringify({ word }),
    });
    renderState(state);
    if (state.completed && !wasCompleted) launchPoopExplosion();
  } catch (error) {
    showError(error.message);
  } finally {
    elements.submit.disabled = false;
  }
}

async function useDevelopmentCheat(event) {
  const isCheatShortcut = (event.ctrlKey || event.metaKey)
    && event.shiftKey
    && event.key === "Enter";
  if (!isCheatShortcut || gameState?.completed) return;

  event.preventDefault();
  elements.submit.disabled = true;
  elements.message.textContent = "";
  try {
    const state = await requestGame("game/cheat", { method: "POST" });
    renderState(state);
    launchPoopExplosion();
  } catch (error) {
    if (error.status !== 404) showError(error.message);
  } finally {
    elements.submit.disabled = false;
  }
}

function launchPoopExplosion() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const canvas = document.createElement("canvas");
  canvas.className = "poop-explosion";
  canvas.setAttribute("aria-hidden", "true");
  document.body.append(canvas);

  const context = canvas.getContext("2d");
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  const width = window.innerWidth;
  const height = window.innerHeight;
  canvas.width = width * pixelRatio;
  canvas.height = height * pixelRatio;
  context.scale(pixelRatio, pixelRatio);

  const gravity = 1200;
  const particles = Array.from({ length: 55 }, () => ({
    x: width / 2 + (Math.random() - 0.5) * 80,
    y: height * 0.48,
    velocityX: (Math.random() - 0.5) * 760,
    velocityY: -350 - Math.random() * 520,
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: (Math.random() - 0.5) * 8,
    size: 22 + Math.random() * 24,
  }));
  let previousTime = performance.now();

  function animate(currentTime) {
    const elapsed = Math.min((currentTime - previousTime) / 1000, 0.035);
    previousTime = currentTime;
    context.clearRect(0, 0, width, height);

    let particlesOnScreen = false;
    particles.forEach((particle) => {
      particle.velocityY += gravity * elapsed;
      particle.x += particle.velocityX * elapsed;
      particle.y += particle.velocityY * elapsed;
      particle.rotation += particle.rotationSpeed * elapsed;

      if (particle.y < height + particle.size) particlesOnScreen = true;
      context.save();
      context.translate(particle.x, particle.y);
      context.rotate(particle.rotation);
      context.font = `${particle.size}px sans-serif`;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText("💩", 0, 0);
      context.restore();
    });

    if (particlesOnScreen) {
      requestAnimationFrame(animate);
    } else {
      canvas.remove();
    }
  }

  requestAnimationFrame(animate);
}

function showError(message) {
  elements.message.textContent = message;
  elements.form.classList.remove("shake");
  void elements.form.offsetWidth;
  elements.form.classList.add("shake");
  elements.input.select();
}

function buildKeyboard() {
  keyboardRows.forEach((keys) => {
    const row = document.createElement("div");
    row.className = "key-row";
    keys.forEach((keyValue) => {
      const key = document.createElement("button");
      key.type = "button";
      key.className = `key${keyValue.length > 1 ? " wide" : ""}`;
      key.textContent = keyValue === "BACKSPACE" ? "⌫" : keyValue;
      key.setAttribute("aria-label", keyValue);
      key.addEventListener("click", () => handleKey(keyValue));
      row.append(key);
    });
    elements.keyboard.append(row);
  });
}

function handleKey(key) {
  if (key === "ENTER") {
    elements.form.requestSubmit();
  } else if (key === "BACKSPACE") {
    elements.input.value = elements.input.value.slice(0, -1);
  } else if (elements.input.value.length < 4) {
    elements.input.value += key;
  }
  elements.input.focus();
}

elements.input.addEventListener("input", () => {
  elements.input.value = elements.input.value.replace(/[^a-z]/gi, "").toUpperCase();
  elements.message.textContent = "";
});
document.addEventListener("keydown", useDevelopmentCheat);
elements.form.addEventListener("submit", submitWord);
elements.helpButton.addEventListener("click", () => elements.helpDialog.showModal());
elements.helpClose.addEventListener("click", () => elements.helpDialog.close());
elements.shareButton.addEventListener("click", openShareDialog);
elements.shareClose.addEventListener("click", () => elements.shareDialog.close());
elements.shareCopyButton.addEventListener("click", copyShareResult);
elements.statisticsButton.addEventListener("click", openStatisticsDialog);
elements.statisticsClose.addEventListener("click", () => elements.statisticsDialog.close());
elements.helpDialog.addEventListener("click", (event) => {
  if (event.target === elements.helpDialog) elements.helpDialog.close();
});
elements.shareDialog.addEventListener("click", (event) => {
  if (event.target === elements.shareDialog) elements.shareDialog.close();
});
elements.statisticsDialog.addEventListener("click", (event) => {
  if (event.target === elements.statisticsDialog) elements.statisticsDialog.close();
});

buildKeyboard();
updateCountdown();
window.setInterval(updateCountdown, 1000);
loadGame();
