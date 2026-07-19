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
  helpButton: document.querySelector("#help-button"),
  helpDialog: document.querySelector("#help-dialog"),
  helpClose: document.querySelector("#help-close"),
};

const keyboardRows = [
  [..."QWERTYUIOP"],
  [..."ASDFGHJKL"],
  ["ENTER", ..."ZXCVBNM", "BACKSPACE"],
];
let gameState = null;

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
elements.helpDialog.addEventListener("click", (event) => {
  if (event.target === elements.helpDialog) elements.helpDialog.close();
});
elements.shareDialog.addEventListener("click", (event) => {
  if (event.target === elements.shareDialog) elements.shareDialog.close();
});

buildKeyboard();
loadGame();
