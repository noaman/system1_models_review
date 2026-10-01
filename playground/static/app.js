const TYPES = [
  { id: "choice", name: "Choice", hint: "Pick one option from a list you write." },
  { id: "score", name: "Score", hint: "Place the answer on levels, starting at 0." },
  { id: "noul", name: "Noul", hint: "Ask a yes or no. The answer comes back as a probability." },
];

const bench = {
  mode: "single",
  modelIds: ["typesafe"],
  format: "text",
  catalog: null,
  running: false,
};

const resultsEl = document.getElementById("results");
const questionList = document.getElementById("question-list");
const modelPicker = document.getElementById("model-picker");
const stateText = document.getElementById("state-text");
const runButton = document.getElementById("run-button");
const runLabel = document.getElementById("run-label");
const runNote = document.getElementById("run-note");

document.getElementById("run-kbd").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ Enter" : "Ctrl Enter";

document.getElementById("mode-single").addEventListener("click", () => setMode("single"));
document.getElementById("mode-compare").addEventListener("click", () => setMode("compare"));
document.getElementById("format-text").addEventListener("click", () => setFormat("text"));
document.getElementById("format-json").addEventListener("click", () => setFormat("json"));
document.getElementById("load-sample").addEventListener("click", () => {
  const preset = bench.catalog && bench.catalog.presets.find((item) => item.id === "billing_triage");
  if (preset) applySample(preset);
});
document.getElementById("bench").addEventListener("submit", onSubmit);
document.getElementById("bench").addEventListener("input", onEdit);
document.getElementById("bench").addEventListener("change", onEdit);

modelPicker.addEventListener("click", (event) => {
  const card = event.target.closest("[data-model-id]");
  if (!card) return;
  toggleModel(card.dataset.modelId);
});

questionList.addEventListener("click", (event) => {
  const add = event.target.closest("[data-add-type]");
  if (add) {
    addQuestion(add.dataset.addType);
    return;
  }
  const button = event.target.closest("button");
  if (!button) return;
  const card = button.closest(".question");
  if (!card) return;
  if (button.dataset.action === "remove") removeQuestion(card);
  if (button.dataset.action === "add-option") addChoiceRow(card);
  if (button.dataset.action === "add-level") addScoreRow(card);
  if (button.dataset.action === "remove-row") {
    const row = button.closest(".option-row, .level-row");
    if (row) row.remove();
    refreshExpectedChoice(card);
  }
  onEdit();
});

questionList.addEventListener("input", (event) => {
  const card = event.target.closest(".question");
  if (!card) return;
  if (event.target.classList.contains("choice-key") || event.target.classList.contains("choice-description")) {
    refreshExpectedChoice(card);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    document.getElementById("bench").requestSubmit();
  }
});

boot();

async function boot() {
  try {
    const response = await fetch("/api/catalog");
    if (!response.ok) throw new Error("catalog");
    bench.catalog = await response.json();
  } catch {
    renderError("Could not load the playground.");
    return;
  }
  renderModels();
  renderTypeSections();
  const draft = loadDraft();
  if (draft) restoreDraft(draft);
  else addQuestion("choice");
  updateRunLabel();
}

function setMode(mode) {
  bench.mode = mode;
  if (mode === "single" && bench.modelIds.length !== 1) {
    bench.modelIds = [bench.modelIds[0] || "typesafe"];
  }
  if (mode === "compare" && bench.catalog) {
    bench.modelIds = bench.catalog.models.map((model) => model.id);
  }
  document.getElementById("mode-single").classList.toggle("is-on", mode === "single");
  document.getElementById("mode-compare").classList.toggle("is-on", mode === "compare");
  document.getElementById("mode-single").setAttribute("aria-selected", String(mode === "single"));
  document.getElementById("mode-compare").setAttribute("aria-selected", String(mode === "compare"));
  document.getElementById("mode-copy").textContent = mode === "single"
    ? "One model answers the questions."
    : "Every selected model sees the same state and the same questions.";
  renderModels();
  updateRunLabel();
  saveDraft();
}

function setFormat(format) {
  bench.format = format;
  document.getElementById("format-text").classList.toggle("is-on", format === "text");
  document.getElementById("format-json").classList.toggle("is-on", format === "json");
  stateText.classList.toggle("is-json", format === "json");
  stateText.placeholder = format === "json"
    ? '{\n  "ticket": "..."\n}'
    : "Paste the text the model should judge.";
  stateText.spellcheck = format !== "json";
}

function toggleModel(modelId) {
  if (bench.mode === "single") {
    bench.modelIds = [modelId];
  } else if (bench.modelIds.includes(modelId)) {
    if (bench.modelIds.length === 1) return;
    bench.modelIds = bench.modelIds.filter((id) => id !== modelId);
  } else {
    bench.modelIds = bench.catalog.models.map((model) => model.id).filter((id) => bench.modelIds.includes(id) || id === modelId);
  }
  renderModels();
  updateRunLabel();
  saveDraft();
}

function renderModels() {
  modelPicker.replaceChildren(...bench.catalog.models.map((model) => {
    const selected = bench.modelIds.includes(model.id);
    return el("button", {
      className: "model-card" + (selected ? " is-on" : ""),
      type: "button",
      attrs: { "data-model-id": model.id, "aria-pressed": String(selected) },
    }, [
      el("span", { className: "model-kicker", text: model.kind + " · " + model.subtitle }),
      el("strong", { text: model.name }),
      el("p", { text: model.summary }),
      el("span", { className: "status-chip" + (model.ready ? "" : " is-warn"), text: model.status }),
    ]);
  }));
}

function renderTypeSections() {
  questionList.replaceChildren(...TYPES.map((type) => {
    const block = el("section", { className: "type-block", attrs: { "data-type": type.id } });
    block.append(el("div", { className: "type-head" }, [
      el("h3", { text: type.name }),
      el("p", { text: type.hint }),
    ]));
    block.append(el("div", { className: "type-questions" }));
    block.append(el("button", {
      className: "add-row",
      type: "button",
      attrs: { "data-add-type": type.id },
      text: "Add a " + type.name.toLowerCase() + " question",
    }));
    return block;
  }));
}

function addQuestion(type, question) {
  const section = questionList.querySelector('.type-block[data-type="' + type + '"]');
  if (!section) return;
  section.querySelector(".type-questions").append(questionCard(question || blankQuestion(type)));
  refreshAddLabel(section);
  saveDraft();
}

function refreshAddLabel(section) {
  const button = section.querySelector("[data-add-type]");
  const count = section.querySelectorAll(".question").length;
  const name = TYPES.find((type) => type.id === section.dataset.type).name.toLowerCase();
  button.textContent = count ? "Add another " + name : "Add a " + name + " question";
}

function applySample(preset) {
  stateText.value = preset.state;
  setFormat(preset.state_format || "text");
  for (const list of questionList.querySelectorAll(".type-questions")) list.replaceChildren();
  for (const question of preset.questions) addQuestion(question.type, question);
  for (const section of questionList.querySelectorAll(".type-block")) refreshAddLabel(section);
  saveDraft();
}

function blankQuestion(type) {
  const count = questionList.querySelectorAll('.question[data-type="' + type + '"]').length + 1;
  return {
    id: type + "_" + count,
    type,
    instructions: "",
    choice_options: [{ key: "", description: "" }, { key: "", description: "" }],
    score_levels: ["", ""],
    noul_true: "",
    noul_false: "",
    expected: null,
  };
}

function questionCard(question) {
  const type = question.type || "choice";
  const card = el("article", { className: "question", attrs: { "data-type": type } });
  card.append(questionHeader(question.id || ""));
  card.append(el("label", { className: "field" }, [
    el("span", { text: "Question" }),
    textarea(question.instructions || "", questionPrompt(type)),
  ]));
  const mount = el("div", { className: "criteria-mount" });
  card.append(mount);
  fillCriteria(card, question);
  return card;
}

function questionPrompt(type) {
  if (type === "score") return "How urgent is this?";
  if (type === "noul") return "Does the user threaten to cancel?";
  return "Which department should handle this?";
}

function questionHeader(questionId) {
  const header = el("div", { className: "question-top" });
  const idInput = el("input", {
    className: "question-id",
    attrs: { type: "text", spellcheck: "false", "aria-label": "Name", placeholder: "Name, such as department" },
  });
  idInput.value = questionId;
  header.append(idInput);
  header.append(el("button", { className: "text-button", type: "button", attrs: { "data-action": "remove" }, text: "Remove" }));
  return header;
}

function textarea(value, placeholder) {
  const node = el("textarea", { className: "instructions", attrs: { placeholder: placeholder || "Write the question." } });
  node.value = value;
  return node;
}

function fillCriteria(card, question) {
  const mount = card.querySelector(".criteria-mount");
  mount.replaceChildren();
  const type = card.dataset.type;
  if (type === "choice") mount.append(choiceEditor(question));
  else if (type === "score") mount.append(scoreEditor(question));
  else mount.append(noulEditor(question));
}

function choiceEditor(question) {
  const wrap = el("div");
  wrap.append(el("span", { className: "option-label", text: "Options" }));
  const list = el("div", { className: "option-list" });
  const options = question.choice_options && question.choice_options.length
    ? question.choice_options
    : [{ key: "", description: "" }, { key: "", description: "" }];
  for (const option of options) list.append(choiceRow(option));
  wrap.append(list);
  wrap.append(el("button", { className: "add-row", type: "button", attrs: { "data-action": "add-option" }, text: "Add option" }));
  wrap.append(expectedChoice(options, question.expected));
  return wrap;
}

function choiceRow(option) {
  const row = el("div", { className: "option-row" });
  row.append(textInput("choice-key", "Option", option.key || ""));
  row.append(textInput("choice-description", "What it means", option.description || ""));
  row.append(el("button", { className: "row-remove", type: "button", attrs: { "data-action": "remove-row", "aria-label": "Remove option" }, text: "×" }));
  return row;
}

function addChoiceRow(card) {
  card.querySelector(".option-list").append(choiceRow({ key: "", description: "" }));
  refreshExpectedChoice(card);
}

function expectedChoice(options, expected) {
  const field = el("label", { className: "field expected-row" }, [el("span", { text: "Expected answer" })]);
  const select = el("select", { className: "expected-choice" });
  select.append(el("option", { value: "", text: "No expected answer" }));
  for (const option of options) {
    if (!option.key) continue;
    select.append(el("option", { value: option.key, text: option.key }));
  }
  select.value = typeof expected === "string" ? expected : "";
  field.append(select);
  return field;
}

function refreshExpectedChoice(card) {
  const select = card.querySelector(".expected-choice");
  if (!select) return;
  const current = select.value;
  const keys = [...card.querySelectorAll(".choice-key")].map((input) => input.value.trim()).filter(Boolean);
  select.replaceChildren(el("option", { value: "", text: "No expected answer" }));
  for (const key of keys) select.append(el("option", { value: key, text: key }));
  select.value = keys.includes(current) ? current : "";
}

function scoreEditor(question) {
  const wrap = el("div");
  wrap.append(el("span", { className: "option-label", text: "Levels, lowest first" }));
  const list = el("div", { className: "level-list" });
  const levels = question.score_levels && question.score_levels.length ? question.score_levels : ["", ""];
  levels.forEach((level, index) => list.append(scoreRow(index, level)));
  wrap.append(list);
  wrap.append(el("button", { className: "add-row", type: "button", attrs: { "data-action": "add-level" }, text: "Add level" }));
  const expected = el("label", { className: "field expected-row" }, [
    el("span", { text: "Expected score" }),
  ]);
  const input = el("input", { className: "expected-score", attrs: { type: "number", step: "0.1", placeholder: "Optional" } });
  if (typeof question.expected === "number") input.value = String(question.expected);
  expected.append(input);
  wrap.append(expected);
  return wrap;
}

function scoreRow(index, level) {
  const row = el("div", { className: "level-row" });
  row.append(el("span", { className: "level-index", text: String(index) }));
  row.append(textInput("score-level", "Level " + index, level || ""));
  row.append(el("button", { className: "row-remove", type: "button", attrs: { "data-action": "remove-row", "aria-label": "Remove level" }, text: "×" }));
  return row;
}

function addScoreRow(card) {
  const list = card.querySelector(".level-list");
  list.append(scoreRow(list.children.length, ""));
}

function noulEditor(question) {
  const wrap = el("div");
  const grid = el("div", { className: "noul-grid" });
  grid.append(labeledInput("Yes means", "noul-true", question.noul_true || "Optional"));
  grid.append(labeledInput("No means", "noul-false", question.noul_false || "Optional"));
  const trueInput = grid.querySelector(".noul-true");
  const falseInput = grid.querySelector(".noul-false");
  trueInput.value = question.noul_true || "";
  falseInput.value = question.noul_false || "";
  trueInput.placeholder = "Optional";
  falseInput.placeholder = "Optional";
  wrap.append(grid);
  const expected = question.expected === true ? "yes" : question.expected === false ? "no" : "";
  wrap.append(noulExpected(expected));
  return wrap;
}

function labeledInput(label, className, placeholder) {
  const field = el("label", { className: "field" }, [el("span", { text: label })]);
  field.append(el("input", { className, attrs: { type: "text", placeholder } }));
  return field;
}

let noulGroup = 0;

function noulExpected(value) {
  const field = el("div", { className: "field expected-row" });
  field.append(el("span", { text: "Expected answer" }));
  const groupName = "noul-expected-" + (++noulGroup);
  const group = el("div", { className: "choice-group" });
  for (const item of [["", "Not set"], ["yes", "Yes"], ["no", "No"]]) {
    const label = el("label");
    const input = el("input", { attrs: { type: "radio", name: groupName, value: item[0] } });
    input.checked = value === item[0];
    label.append(input, document.createTextNode(item[1]));
    group.append(label);
  }
  field.append(group);
  return field;
}

function textInput(className, aria, value) {
  const input = el("input", { className, attrs: { type: "text", "aria-label": aria, placeholder: aria } });
  input.value = value;
  return input;
}

function removeQuestion(card) {
  const section = card.closest(".type-block");
  card.remove();
  if (section) refreshAddLabel(section);
}

function readCriteria(card) {
  const type = card.dataset.type;
  if (type === "choice") {
    return {
      choice_options: [...card.querySelectorAll(".option-row")].map((row) => ({
        key: row.querySelector(".choice-key").value,
        description: row.querySelector(".choice-description").value,
      })),
      expected: card.querySelector(".expected-choice").value || null,
    };
  }
  if (type === "score") {
    const raw = card.querySelector(".expected-score").value.trim();
    return {
      score_levels: [...card.querySelectorAll(".score-level")].map((input) => input.value),
      expected: raw === "" ? null : Number(raw),
    };
  }
  const selected = card.querySelector("input[type='radio']:checked");
  return {
    noul_true: card.querySelector(".noul-true").value,
    noul_false: card.querySelector(".noul-false").value,
    expected: !selected || selected.value === "" ? null : selected.value === "yes",
  };
}

function scrapeQuestion(card) {
  const criteria = readCriteria(card);
  return {
    id: card.querySelector(".question-id").value.trim(),
    type: card.dataset.type,
    instructions: card.querySelector(".instructions").value.trim(),
    choice_options: criteria.choice_options || [],
    score_levels: criteria.score_levels || [],
    noul_true: criteria.noul_true || "",
    noul_false: criteria.noul_false || "",
    expected: criteria.expected,
  };
}

function payloadFromForm() {
  return {
    mode: bench.mode,
    model_ids: bench.modelIds.slice(),
    state_format: bench.format,
    state: stateText.value,
    score_tolerance: Number(document.getElementById("score-tolerance").value),
    questions: [...questionList.querySelectorAll(".question")].map(scrapeQuestion).filter((question) => !isBlank(question)),
  };
}

function isBlank(question) {
  if (question.instructions) return false;
  if (question.expected != null && question.expected !== "") return false;
  if (question.type === "choice" && question.choice_options.some((option) => option.key.trim() || option.description.trim())) return false;
  if (question.type === "score" && question.score_levels.some((level) => level.trim())) return false;
  if (question.type === "noul" && (question.noul_true.trim() || question.noul_false.trim())) return false;
  return true;
}

function clientError(payload) {
  if (!payload.model_ids.length) return "Select a model.";
  if (payload.mode === "compare" && payload.model_ids.length < 1) return "Select one or more models.";
  if (!payload.state.trim()) return "Paste the text to judge.";
  if (!payload.questions.length) return "Write a question to test.";
  for (const question of payload.questions) {
    if (!question.id) return "Give each question a short name.";
    if (!question.instructions) return "Write the question for " + question.id + ".";
  }
  if (Number.isNaN(payload.score_tolerance)) return "Score tolerance must be a number.";
  return "";
}

async function onSubmit(event) {
  event.preventDefault();
  if (bench.running) return;
  const payload = payloadFromForm();
  const problem = clientError(payload);
  if (problem) {
    renderError(problem);
    return;
  }
  bench.running = true;
  runButton.disabled = true;
  runLabel.textContent = "Running";
  renderLoading(payload);
  const laya = bench.catalog && bench.catalog.models.find((model) => model.id === "laya");
  const noteTimer = window.setTimeout(() => {
    if (payload.model_ids.includes("laya") && (!laya || laya.status !== "In memory")) {
      runNote.hidden = false;
      runNote.textContent = "Laya is still loading into memory. The first startup can take several minutes.";
    }
  }, 1200);
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (!response.ok) {
      renderError(formatDetail(body && body.detail) || "Request failed (" + response.status + ").");
      return;
    }
    renderResults(body);
  } catch {
    renderError("Could not reach the playground server.");
  } finally {
    window.clearTimeout(noteTimer);
    runNote.hidden = true;
    bench.running = false;
    runButton.disabled = false;
    updateRunLabel();
  }
}

function renderLoading(payload) {
  const names = payload.model_ids.map(modelName).join(payload.mode === "compare" ? " and " : "");
  resultsEl.replaceChildren(
    el("div", { className: "loading" }, [
      el("p", { className: "eyebrow", text: "Running" }),
      el("h2", { className: "q-title", text: "Asking " + names + "." }),
      el("div", { className: "skeleton card" }),
      el("div", { className: "skeleton card" }),
    ]),
  );
}

function renderError(message) {
  resultsEl.replaceChildren(el("div", { className: "error-banner" }, [
    el("strong", { text: "Could not run" }),
    el("p", { text: message }),
  ]));
}

function renderResults(data) {
  const summary = data.summary || {};
  const root = el("div", { className: "summary" }, [
    el("p", { className: "eyebrow", text: data.mode === "compare" ? "Comparison" : "Result" }),
    el("h2", { className: "q-title", text: summary.sentence || "Finished." }),
  ]);
  root.append(metrics(summary, (data.results || []).length));
  const board = el("div");
  for (const question of data.questions || []) {
    board.append(questionBlock(question, data.results || []));
  }
  const pre = el("pre", { className: "mono", text: JSON.stringify(data, null, 2) });
  const raw = el("details", { className: "raw" }, [el("summary", { text: "Response JSON" }), pre]);
  resultsEl.replaceChildren(root, board, raw);
  resultsEl.scrollTop = 0;
}

function metrics(summary, resultCount) {
  const tiles = [
    summary.check_count
      ? metric(summary.match_count + "/" + summary.check_count, "Expected matches")
      : metric("—", "No expected answer"),
    summary.comparison_count
      ? metric(summary.agreement_count + "/" + summary.comparison_count, "Agreed")
      : metric(String(resultCount || 1), resultCount === 1 ? "Model" : "Models"),
    metric(formatMs(summary.slowest_ms || 0), "Slowest"),
  ];
  return el("div", { className: "metrics" }, tiles);
}

function metric(value, label) {
  return el("div", { className: "metric" }, [
    el("b", { text: value }),
    el("span", { text: label }),
  ]);
}

function questionBlock(question, modelResults) {
  const head = el("div", { className: "q-head" }, [
    el("h3", { className: "q-title", text: question.id }),
    el("span", { className: "type-pill " + question.type, text: question.type }),
  ]);
  if (question.expected_label) {
    head.append(el("span", { className: "pill", text: "Expected " + question.expected_label }));
  }
  const agreement = question.agreement;
  if (agreement && agreement.comparable) {
    head.append(el("span", {
      className: "pill " + (agreement.agreed ? "agree" : "split"),
      text: agreement.agreed ? "Agreed" : "Split",
    }));
  }
  const block = el("section", { className: "q-block" }, [
    head,
    el("p", { className: "instruction", text: question.instructions }),
    el("div", { className: "q-grid" }, modelResults.map((result) => answerCard(result, question.id))),
  ]);
  if (agreement && agreement.comparable) {
    block.append(el("p", { className: "agreement", text: agreement.detail }));
  }
  return block;
}

function answerCard(result, questionId) {
  if (result.error) {
    return el("article", { className: "model-error" }, [
      el("span", { className: "answer-kicker model", text: result.name }),
      el("strong", { text: "The model did not answer." }),
      el("p", { text: result.error }),
    ]);
  }
  const answer = (result.answers || {})[questionId];
  if (!answer) {
    return el("article", { className: "model-error" }, [
      el("span", { className: "answer-kicker model", text: result.name }),
      el("p", { text: "No answer for this question." }),
    ]);
  }
  const card = el("article", { className: "answer-card" });
  const top = el("div", { className: "answer-top" }, [
    el("span", { className: "answer-kicker model", text: result.name }),
    el("span", { className: "latency mono", text: formatMs(result.elapsed_ms) }),
  ]);
  card.append(top);
  const meta = [result.backend_model, result.routing_reason, usageLabel(result.usage)].filter(Boolean).join(" · ");
  if (meta) card.append(el("p", { className: "backend", text: meta }));
  card.append(el("p", { className: "answer-value", text: answer.headline }));
  card.append(el("p", { className: "answer-sub", text: answer.subhead || "" }));
  const confidence = confidenceLabel(answer.confidence);
  if (confidence) card.append(el("p", { className: "confidence", text: confidence }));
  if (answer.rows && answer.rows.some((row) => row.probability != null)) card.append(bars(answer.rows));
  if (answer.meter != null && answer.type !== "choice") card.append(meter(answer));
  if (answer.evaluation) {
    card.append(el("p", {
      className: "verdict " + (answer.evaluation.matched ? "match" : "miss"),
      text: answer.evaluation.detail,
    }));
  }
  return card;
}

function bars(rows) {
  const wrap = el("div", { className: "bars" });
  for (const row of rows) {
    const pct = Math.max(0, Math.min(1, Number(row.probability))) * 100;
    const fill = el("span", { className: "bar-fill" });
    const name = el("span", { className: "bar-name" }, [el("strong", { text: row.key })]);
    if (row.label && row.label !== row.key) name.append(el("span", { text: row.label }));
    const line = el("div", { className: "bar-row" + (row.selected ? " is-selected" : "") }, [
      name,
      el("span", { className: "bar-track" }, [fill]),
      el("span", { className: "bar-value mono", text: Math.round(pct) + "%" }),
    ]);
    wrap.append(line);
    requestAnimationFrame(() => { fill.style.width = pct + "%"; });
  }
  return wrap;
}

function meter(answer) {
  const wrap = el("div", { className: "meter-wrap" });
  const mark = el("span", { className: "meter-mark" });
  const fill = el("span", { className: "meter-fill" });
  wrap.append(el("div", { className: "meter " + answer.type }, [fill, mark]));
  if (answer.type === "noul") {
    wrap.append(el("div", { className: "meter-ends" }, [el("span", { text: "No" }), el("span", { text: "Yes" })]));
  } else if (answer.rows && answer.rows.length > 1) {
    wrap.append(el("div", { className: "ticks" }, answer.rows.map((row) => el("span", { text: row.key }))));
  }
  const clamped = Math.max(0, Math.min(1, Number(answer.meter)));
  requestAnimationFrame(() => {
    fill.style.width = (clamped * 100) + "%";
    mark.style.left = (clamped * 100) + "%";
  });
  return wrap;
}

function onEdit() {
  renumberScoreLevels();
  saveDraft();
  updateRunLabel();
}

function renumberScoreLevels() {
  for (const list of questionList.querySelectorAll(".level-list")) {
    [...list.children].forEach((row, index) => {
      const badge = row.querySelector(".level-index");
      if (badge) badge.textContent = String(index);
    });
  }
}

function updateRunLabel() {
  if (bench.running) return;
  const names = bench.modelIds.map(modelName);
  if (bench.mode === "compare") {
    runLabel.textContent = names.length > 1 ? "Compare " + names.length + " models" : "Run " + (names[0] || "model");
  } else {
    runLabel.textContent = "Run " + (names[0] || "model");
  }
}

function modelName(modelId) {
  const model = bench.catalog && bench.catalog.models.find((item) => item.id === modelId);
  return model ? model.name : modelId;
}

function formatMs(value) {
  const ms = Number(value) || 0;
  if (ms < 1000) return Math.round(ms) + " ms";
  return (ms / 1000).toFixed(ms < 10000 ? 1 : 0) + " s";
}

function confidenceLabel(value) {
  if (value == null || Number.isNaN(Number(value))) return "";
  if (value >= 0 && value <= 1) return Math.round(value * 100) + "% confidence";
  return String(value) + " confidence";
}

function usageLabel(usage) {
  if (!usage) return "";
  const parts = [];
  if (usage.input_tokens != null) parts.push(usage.input_tokens + " in");
  if (usage.output_tokens != null) parts.push(usage.output_tokens + " out");
  return parts.join(" · ");
}

function formatDetail(detail) {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const where = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
      return where ? where + ": " + item.msg : item.msg;
    }).join(" ");
  }
  return "";
}

function saveDraft() {
  try {
    if (!questionList.querySelector(".question")) return;
    const draft = payloadFromForm();
    sessionStorage.setItem("system1-playground-draft-v2", JSON.stringify(draft));
  } catch {
    /* Ignore private-mode storage failures. */
  }
}

function loadDraft() {
  try {
    const raw = sessionStorage.getItem("system1-playground-draft-v2");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function restoreDraft(draft) {
  bench.mode = draft.mode === "compare" ? "compare" : "single";
  bench.modelIds = Array.isArray(draft.model_ids) && draft.model_ids.length ? draft.model_ids : ["typesafe"];
  document.getElementById("mode-single").classList.toggle("is-on", bench.mode === "single");
  document.getElementById("mode-compare").classList.toggle("is-on", bench.mode === "compare");
  document.getElementById("mode-copy").textContent = bench.mode === "single"
    ? "One model answers the questions."
    : "Every selected model sees the same state and the same questions.";
  renderModels();
  stateText.value = draft.state || "";
  setFormat(draft.state_format === "json" ? "json" : "text");
  document.getElementById("score-tolerance").value = draft.score_tolerance ?? 0.5;
  const questions = Array.isArray(draft.questions) ? draft.questions : [];
  if (!questions.length) addQuestion("choice");
  for (const question of questions) addQuestion(question.type || "choice", question);
}

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.type) node.type = options.type;
  if (options.value != null) node.value = options.value;
  if (options.text != null) node.textContent = options.text;
  if (options.attrs) {
    for (const [key, value] of Object.entries(options.attrs)) node.setAttribute(key, value);
  }
  for (const child of children) if (child) node.append(child);
  return node;
}
