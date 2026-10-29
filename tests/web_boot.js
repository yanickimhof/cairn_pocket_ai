// Loads the web page in a bare Node context and drives it with fake clicks.
// Usage: node web_boot.js <app.js> <fixture.json>. Any exception or failed check ends with a non-zero exit code.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [, , appPath, fixturePath] = process.argv;
const fx = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const source = fs.readFileSync(appPath, "utf8");

const listeners = {};
const page = { innerHTML: "" };
const toast = { className: "", textContent: "" };
const fakeNode = () => ({
  style: {}, setAttribute() {}, addEventListener() {}, click() {}, remove() {}, appendChild() {}, parentNode: null,
});
const doc = {
  getElementById: (id) => (id === "app" ? page : id === "toast" ? toast : null),
  addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
  documentElement: {},
  body: { appendChild() {}, removeChild() {}, style: {} },
  activeElement: null,
  createElement: fakeNode,
};
const timers = [];
const calls = [];
function fetchStub(path, opt) {
  calls.push(((opt && opt.method) || "GET") + " " + path);
  let body = {};
  if (path.split("?")[0] === "/api/state") { body = fx.state; }
  else if (path.indexOf("/api/search") === 0) {
    body = { results: [{ id: "n1", title: "Call", date: "2026-10-08T08:06:00", score: 3, hits: [{ where: "transcript", start: 12, parts: [{ t: "see the ", m: false }, { t: "acme", m: true }] }] }] };
  }
  else if (path === "/api/actions") {
    body = { actions: [{ note: "n1", title: "Call", date: "2026-10-08T08:06:00", what: "Send the plan", who: "Sophie", when: "Friday", done: false },
                       { note: "n2", title: "Check-in", date: "2026-10-07T08:06:00", what: "Call the supplier", who: "", when: "", done: true }] };
  }
  else if (path.indexOf("/api/note/") === 0 && !(opt && opt.method === "POST")) { body = fx.note; }
  return Promise.resolve({
    ok: true, status: 200, json: () => Promise.resolve(body), text: () => Promise.resolve(""), blob: () => Promise.resolve({}),
  });
}
const context = {
  document: doc, navigator: { language: "en", clipboard: { writeText: () => Promise.resolve() } }, fetch: fetchStub,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout() {}, console,
  URL: { createObjectURL: () => "", revokeObjectURL() {} }, Blob: function () {},
};
context.window = context;
vm.createContext(context);

process.on("unhandledRejection", (error) => { console.error("unhandled rejection:", error); process.exit(1); });
process.on("uncaughtException", (error) => { console.error("uncaught exception:", error); process.exit(1); });

const settle = async () => { for (let i = 0; i < 8; i += 1) { await new Promise((resolve) => setImmediate(resolve)); } };
function check(condition, message) {
  if (!condition) { console.error("FAILED: " + message); process.exit(1); }
}
function click(attrs, inPopover) {
  const el = { disabled: false, getAttribute: (name) => (attrs[name] === undefined ? null : attrs[name]) };
  const event = { target: { closest: (selector) => (selector === "[data-a]" ? el : selector === ".pop" && inPopover ? el : null) } };
  (listeners.click || []).forEach((fn) => fn(event));
}
const tipOf = (key) => { const m = page.innerHTML.match(new RegExp('data-a="cycle" data-v="' + key + '" data-tip="([^"]*)"')); return m && m[1]; };

(async () => {
  vm.runInContext(source, context);
  await settle();
  check(page.innerHTML.indexOf('class="brand"') !== -1, "the page renders its header");
  check(page.innerHTML.indexOf('data-a="ui"') !== -1, "the interface language toggle is shown");

  // a finished note opens with its tools
  click({ "data-a": "eye" });
  await settle();
  const done = fx.state.notes.filter((n) => n.status === "done")[0];
  click({ "data-a": "row", "data-id": done.id });
  await settle();
  for (const needle of ['data-a="cycle" data-v="lvl"', 'data-a="cycle" data-v="lang"', 'data-a="rerun"', 'data-a="viewText"', 'data-a="toggleExport"']) {
    check(page.innerHTML.indexOf(needle) !== -1, "a finished note shows " + needle);
  }
  check(page.innerHTML.indexOf('data-a="rr"') === -1, "no leftover selector buttons");

  // one tap moves to the next choice, in a loop
  const seen = [tipOf("lvl")];
  for (let i = 0; i < 3; i += 1) { click({ "data-a": "cycle", "data-v": "lvl" }); await settle(); seen.push(tipOf("lvl")); }
  check(seen[0] === seen[3] && seen[0] !== seen[1] && seen[1] !== seen[2], "the level changes on each tap and loops: " + seen.join(" | "));
  const lang = tipOf("lang");
  click({ "data-a": "cycle", "data-v": "lang" });
  await settle();
  check(tipOf("lang") !== lang, "the language changes on tap");

  // export list opens over the page and closes again
  click({ "data-a": "toggleExport" }, true);
  await settle();
  check(page.innerHTML.indexOf("pop-list") !== -1 && page.innerHTML.indexOf('data-a="expMd"') !== -1, "the export list opens");
  click({ "data-a": "toggleExport" }, true);
  await settle();
  check(page.innerHTML.indexOf("pop-list") === -1, "the export list closes");

  // a waiting recording offers its actions
  const waiting = fx.state.notes.filter((n) => n.status === "waiting")[0];
  click({ "data-a": "row", "data-id": waiting.id });
  await settle();
  for (const needle of ['data-a="procOne"', 'data-a="skipOne"', 'data-a="cycle" data-v="lvl"']) {
    check(page.innerHTML.indexOf(needle) !== -1, "a waiting recording shows " + needle);
  }

  // settings: no global level or language any more
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="autocheck"') !== -1, "settings are shown");
  check(page.innerHTML.indexOf('data-a="tr"') === -1 && page.innerHTML.indexOf('data-a="lvl"') === -1 && page.innerHTML.indexOf('data-a="polish"') === -1,
    "no global level, language or polish setting");

  // search: a panel with a field, results with the searched words marked, a tap on a line opens the transcript there
  click({ "data-a": "find" });
  await settle();
  check(page.innerHTML.indexOf('id="findInput"') !== -1 && page.innerHTML.indexOf('data-a="autocheck"') === -1, "the search opens and replaces the settings");
  (listeners.input || []).forEach((fn) => fn({ target: { id: "findInput", value: "acme" } }));
  timers.splice(0).forEach((fn) => fn());
  await settle();
  check(calls.some((c) => c === "GET /api/search?q=acme"), "typing searches");
  check(page.innerHTML.indexOf("<mark>acme</mark>") !== -1 && page.innerHTML.indexOf('data-a="findGo"') !== -1, "the results mark the searched word");
  check(page.innerHTML.indexOf('data-v="12"') !== -1, "a transcript result carries its moment");

  // all actions, grouped by person, with the ticked ones at the end
  click({ "data-a": "tasksToggle" });
  await settle();
  check(page.innerHTML.indexOf('id="findInput"') === -1 && page.innerHTML.indexOf("Sophie") !== -1 && page.innerHTML.indexOf('data-a="tick"') !== -1, "the actions list opens and replaces the search");
  click({ "data-a": "tick", "data-v": "0" });
  await settle();
  check(calls.some((c) => c === "POST /api/note/n1/action"), "ticking an action is saved on its note");

  // a finished note can write its follow-up email
  click({ "data-a": "tasksToggle" });
  click({ "data-a": "row", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('data-a="mailOpen"') !== -1, "a finished note offers its follow-up email");

  // vocabulary: how many notes are out of date, update them all, or tick some
  fx.state.settings.vocabulary = ["Sion, Cion => Acme"];
  fx.state.totals.vocab_todo = 2;
  timers.splice(0).forEach((fn) => fn());
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="vocabAll"') !== -1 && page.innerHTML.indexOf('id="vFrom"') !== -1, "the vocabulary offers to update the notes");
  click({ "data-a": "pickStart" });
  await settle();
  check(page.innerHTML.indexOf('data-a="pickTog"') !== -1 && page.innerHTML.indexOf('data-a="row"') === -1 && page.innerHTML.indexOf('data-a="pickGo" disabled') !== -1, "choosing notes turns the list into a selection, nothing chosen yet");
  click({ "data-a": "pickTog", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('data-a="pickGo" disabled') === -1, "a ticked note enables the update");
  click({ "data-a": "pickGo" });
  await settle();
  check(calls.some((c) => c === "POST /api/vocabulary/apply") && page.innerHTML.indexOf('data-a="pickTog"') === -1, "the chosen notes are sent, the list comes back");

  // a running job shows its progress on the right row
  fx.state.job = { running: true, kind: "import", step: "transcribing", id: waiting.id, done: 0, total: 1, pct: 40, errors: [] };
  timers.splice(0).forEach((fn) => fn());
  await settle();
  check(page.innerHTML.indexOf("pbar") !== -1, "a running job shows a progress bar");

  // French interface
  click({ "data-a": "ui", "data-v": "fr" });
  await settle();
  check(page.innerHTML.indexOf("Réglages") !== -1 || page.innerHTML.indexOf("souverain") !== -1, "the interface switches to French");
  console.log("web page checks passed");
  process.exit(0);
})();
