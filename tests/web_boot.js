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
const fakeNode = () => {
  const node = { style: {}, innerHTML: "", handlers: {}, setAttribute() {}, click() {}, remove() {}, appendChild() {}, parentNode: null, querySelector: () => null, focus() {} };
  node.addEventListener = (type, fn) => { node.handlers[type] = fn; };
  return node;
};
let modal = null;  // the last window the page opened (the transcript)
const doc = {
  getElementById: (id) => (id === "app" ? page : id === "toast" ? toast : null),
  addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
  documentElement: {},
  body: { appendChild(node) { modal = node; node.parentNode = doc.body; }, removeChild(node) { if (modal === node) { modal = null; } }, style: {} },
  querySelector: () => null,
  activeElement: null,
  createElement: fakeNode,
};
const timers = [];
const calls = [];
function fetchStub(path, opt) {
  calls.push(((opt && opt.method) || "GET") + " " + path);
  let body = {};
  if (path.split("?")[0] === "/api/state") { body = JSON.parse(JSON.stringify(fx.state)); }  // a copy: the page empties its list in secure mode
  else if (path.indexOf("/api/search?") === 0) {
    body = { results: [{ id: "n1", title: "Call", date: "2026-10-08T08:06:00", score: 3, hits: [{ where: "transcript", start: 12, parts: [{ t: "see the ", m: false }, { t: "brandt", m: true }] }] }] };
  }
  else if (path.indexOf("/api/search/meaning") === 0) {
    body = { results: [{ id: "n9", title: "Meaning hit", date: "2026-10-08T08:06:00", score: 0.7, hits: [{ where: "similar", start: null, parts: [{ t: "an answer in other words", m: false }] }] }] };
  }
  else if (path === "/api/people") {
    body = { people: [{ name: "Anna", seconds: 600, voice: 2, notes: [{ id: "n1", title: "Call", date: "2026-10-08T08:06:00" }] }, { name: "Anna B", seconds: 60, voice: 0, notes: [{ id: "n2", title: "Check-in", date: "2026-10-07T08:06:00" }] }],
             unnamed: [{ id: "n3", title: "Review", date: "2026-10-06T08:06:00", labels: ["Speaker 1"] }], enabled: true, voiceprints: 1, orphans: [] };
  }
  else if (path === "/api/vocabulary/check") {
    body = { items: [{ key: "brandt", forms: [{ text: "Brandt", count: 3 }, { text: "Brant", count: 1 }], suggest: "Brandt", reason: "variants", notes: 2,
                       examples: [{ note: "n1", title: "Call", start: 3, text: "We saw Brant yesterday", word: "Brant", weak: false }] }] };
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
  (listeners.input || []).forEach((fn) => fn({ target: { id: "findInput", value: "brandt" } }));
  timers.splice(0).forEach((fn) => fn());
  await settle();
  check(calls.some((c) => c === "GET /api/search?q=brandt"), "typing searches");
  check(page.innerHTML.indexOf("<mark>brandt</mark>") !== -1 && page.innerHTML.indexOf('data-a="findGo"') !== -1, "the results mark the searched word");
  check(page.innerHTML.indexOf('data-v="12"') !== -1, "a transcript result carries its moment");

  // all actions, grouped by person, with the ticked ones at the end
  click({ "data-a": "tasksToggle" });
  await settle();
  check(page.innerHTML.indexOf('id="findInput"') === -1 && page.innerHTML.indexOf("Sophie") !== -1 && page.innerHTML.indexOf('data-a="tick"') !== -1, "the actions list opens and replaces the search");
  click({ "data-a": "tick", "data-v": "0" });
  await settle();
  check(calls.some((c) => c === "POST /api/note/n1/action"), "ticking an action is saved on its note");

  // an action is corrected in place or deleted after a confirmation
  click({ "data-a": "taskEdit", "data-v": "0" });
  await settle();
  check(page.innerHTML.indexOf('id="tkWhat"') !== -1 && page.innerHTML.indexOf('data-a="taskSave"') !== -1, "an action opens for editing");
  (listeners.input || []).forEach((fn) => fn({ target: { id: "tkWhat", value: "Send the new plan" } }));
  click({ "data-a": "taskSave" });
  await settle();
  check(calls.some((c) => c === "POST /api/note/n1/actionedit") && page.innerHTML.indexOf('id="tkWhat"') === -1, "the corrected action is saved");
  click({ "data-a": "taskDel", "data-v": "0" });
  await settle();
  check(page.innerHTML.indexOf('data-a="taskDelGo"') !== -1, "deleting asks first");
  click({ "data-a": "taskDelNo" });
  await settle();
  check(page.innerHTML.indexOf('data-a="taskDelGo"') === -1, "the confirmation can be dismissed");

  // secure mode: the actions and the search show the same veil as the list
  click({ "data-a": "eye" });
  await settle();
  check(page.innerHTML.indexOf("veil") !== -1 && page.innerHTML.indexOf('data-a="tick"') === -1, "secure mode hides the actions behind the same veil");
  click({ "data-a": "eye" });
  await settle();
  await settle();

  // a finished note can write its follow-up email
  click({ "data-a": "tasksToggle" });
  click({ "data-a": "row", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('data-a="mailOpen"') !== -1, "a finished note offers its follow-up email");

  // vocabulary: how many notes are out of date, update them all, or tick some
  fx.state.settings.vocabulary = ["Brant, Brand => Brandt"];
  fx.state.totals.vocab_todo = 2;
  timers.splice(0).forEach((fn) => fn());
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="vocabAll"') !== -1 && page.innerHTML.indexOf('data-a="vocabRangeToggle"') !== -1 && page.innerHTML.indexOf('id="vFrom"') === -1, "the vocabulary offers to update the notes with icons");
  click({ "data-a": "vocabRangeToggle" });
  await settle();
  check(page.innerHTML.indexOf('id="vFrom"') !== -1 && page.innerHTML.indexOf('data-a="vocabRange"') !== -1, "the period opens on its icon");
  click({ "data-a": "vocabRangeToggle" });
  await settle();
  click({ "data-a": "pickStart" });
  await settle();
  check(page.innerHTML.indexOf('data-a="pickTog"') !== -1 && page.innerHTML.indexOf('data-a="row"') === -1 && page.innerHTML.indexOf('data-a="pickGo" disabled') !== -1, "choosing notes turns the list into a selection, nothing chosen yet");
  click({ "data-a": "pickTog", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('data-a="pickGo" disabled') === -1, "a ticked note enables the update");
  click({ "data-a": "pickGo" });
  await settle();
  check(calls.some((c) => c === "POST /api/vocabulary/apply") && page.innerHTML.indexOf('data-a="pickTog"') === -1, "the chosen notes are sent, the list comes back");

  // note templates of your own: a name and an instruction, one of them can be the default
  fx.state.settings.templates = [{ id: "c-mine-1", name: "Client report", prompt: "goals, risks" }];
  fx.state.settings.template_default = "";
  timers.splice(0).forEach((fn) => fn());
  await settle();
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="tplAsk"') !== -1, "the settings offer the templates");
  click({ "data-a": "tplAsk" });
  await settle();
  check(page.innerHTML.indexOf('data-a="tplStar"') !== -1 && page.innerHTML.indexOf("Client report") !== -1 && page.innerHTML.indexOf('data-a="tplNew"') !== -1, "the templates are listed with their star");
  click({ "data-a": "tplNew" });
  await settle();
  check(page.innerHTML.indexOf('id="tplName"') !== -1 && page.innerHTML.indexOf('id="tplPrompt"') !== -1, "a new template opens its two fields");
  (listeners.input || []).forEach((fn) => fn({ target: { id: "tplName", value: "Weekly" } }));
  (listeners.input || []).forEach((fn) => fn({ target: { id: "tplPrompt", value: "what moved this week" } }));
  click({ "data-a": "tplSave" });
  await settle();
  check(calls.some((c) => c === "POST /api/settings") && page.innerHTML.indexOf('id="tplName"') === -1, "the template is saved");
  click({ "data-a": "tplDelAsk", "data-v": "0" });
  await settle();
  check(page.innerHTML.indexOf('data-a="tplDelGo"') !== -1, "deleting a template asks first");
  click({ "data-a": "tplDelNo" });
  click({ "data-a": "tplAsk" });
  click({ "data-a": "settings" });
  await settle();

  // tags: shown on the row, a filter above the list, edited in the note, one suggestion waiting
  fx.state.notes.filter((n) => n.id === done.id)[0].tags = ["Apollo"];
  fx.state.notes.filter((n) => n.id === done.id)[0].tag_suggestions = ["juridique"];
  timers.splice(0).forEach((fn) => fn());
  await settle();
  check(page.innerHTML.indexOf("#Apollo") !== -1 && page.innerHTML.indexOf("+#juridique") !== -1 && page.innerHTML.indexOf('data-a="tagFilter"') !== -1, "the list shows the tags, the suggestion and a filter");
  click({ "data-a": "row", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('data-a="tagAccept"') !== -1 && page.innerHTML.indexOf('data-a="tagRemove"') !== -1 && page.innerHTML.indexOf('data-a="tagToggle"') !== -1, "the note shows its tags and its suggestion");
  click({ "data-a": "tagAccept", "data-v": "juridique" });
  await settle();
  check(calls.some((c) => c === "POST /api/note/" + done.id + "/tags"), "accepting a suggestion is saved on the note");
  click({ "data-a": "tagToggle", "data-id": done.id });
  await settle();
  check(page.innerHTML.indexOf('id="tagInput"') !== -1, "the tag field opens");
  (listeners.input || []).forEach((fn) => fn({ target: { id: "tagInput", value: "famille" } }));
  click({ "data-a": "tagAdd" });
  await settle();
  click({ "data-a": "tagFilter", "data-v": "Apollo" });
  await settle();
  check(page.innerHTML.indexOf('data-id="' + waiting.id + '"') === -1 && page.innerHTML.indexOf('data-id="' + done.id + '"') !== -1, "the filter keeps only the notes with that tag");
  click({ "data-a": "tagFilter", "data-v": "Apollo" });
  await settle();
  check(page.innerHTML.indexOf('data-id="' + waiting.id + '"') !== -1, "the filter is lifted by a second tap");
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="tagsSuggest"') !== -1, "the settings offer the tag suggestions");
  click({ "data-a": "pickStart" });
  await settle();
  check(page.innerHTML.indexOf('id="pickTagInput"') !== -1, "choosing notes offers to tag them");
  click({ "data-a": "pickCancel" });
  await settle();

  // the Pocket vault: the ring tells the state, the panel asks for what is needed
  const typeInto = (id, value) => (listeners.input || []).forEach((fn) => fn({ target: { id, value } }));
  const setVault = async (state, connected) => {
    fx.state.pocket = Object.assign({}, fx.state.pocket, { connected, vault: Object.assign({ available: true, plain: 0, sealed: 0, locked: 0, trusted: false }, { state }) });
    timers.splice(0).forEach((fn) => fn());
    await settle();
  };
  await setVault("none", true);
  check(page.innerHTML.indexOf('class="secbtn risk') !== -1, "an unprotected Pocket shows an orange shield");
  check(page.innerHTML.indexOf('id="vPass"') === -1, "the vault panel is closed at first");
  click({ "data-a": "vault" });
  await settle();
  check(page.innerHTML.indexOf('id="vPass"') !== -1 && page.innerHTML.indexOf('id="vPass2"') !== -1 && page.innerHTML.indexOf('data-a="vaultCreate"') !== -1, "the panel asks for a password and its confirmation");
  typeInto("vPass", "a long passphrase"); typeInto("vPass2", "something else");
  const before = calls.length;
  click({ "data-a": "vaultCreate" });
  await settle();
  check(calls.slice(before).every((c) => c.indexOf("/api/vault/create") === -1), "two different passwords are never sent");
  typeInto("vPass2", "a long passphrase");
  click({ "data-a": "vaultCreate" });
  await settle();
  check(calls.indexOf("POST /api/vault/create") !== -1, "matching passwords create the vault");
  check(page.innerHTML.indexOf('id="vPass"') === -1, "the panel closes once the vault is created");
  await setVault("partial", true);
  check(page.innerHTML.indexOf('class="secbtn risk') !== -1, "a Pocket with plain recordings keeps the orange shield");
  await setVault("locked", true);
  check(page.innerHTML.indexOf('class="secbtn lock') !== -1, "a locked Pocket shows an orange shield");
  click({ "data-a": "vault" });
  await settle();
  check(page.innerHTML.indexOf('data-a="vaultUnlock"') !== -1 && page.innerHTML.indexOf('id="vPass2"') === -1, "a locked Pocket asks for the password only");
  click({ "data-a": "vault" });
  await settle();
  await setVault("secured", true);
  check(page.innerHTML.indexOf('class="secbtn ok') !== -1, "a secured Pocket shows a green shield");
  await setVault("secured", false);
  check(page.innerHTML.indexOf('class="secbtn idle') !== -1, "without the Pocket the shield is neutral");
  fx.state.pocket.vault.available = false;
  timers.splice(0).forEach((fn) => fn());
  await settle();
  check(page.innerHTML.indexOf('class="secbtn idle') !== -1, "without the encryption library the shield stays, grey, and says so");

  // the header: the vault, then search, language, tasks, settings, about; the language is one button that switches
  await setVault("none", true);
  const order = ['class="secbtn', 'data-a="find"', 'data-a="ui"', 'data-a="tasksToggle"', 'data-a="settings"', 'data-a="about"'].map((n) => page.innerHTML.indexOf(n));
  check(order.every((at, i) => at !== -1 && (i === 0 || at > order[i - 1])), "the header icons come in the agreed order: " + order.join(","));
  check((page.innerHTML.match(/data-a="ui"/g) || []).length === 1, "the language is a single button, not a pair");
  check(page.innerHTML.indexOf('class="seg s34"') === -1, "no language toggle left");

  // names to check: the list opens in the settings, the right spelling is typed, saved
  fx.state.totals = Object.assign({}, fx.state.totals, { vocab_check: 1 });
  timers.splice(0).forEach((fn) => fn());
  await settle();
  click({ "data-a": "settings" });
  await settle();
  check(page.innerHTML.indexOf('data-a="vcToggle"') !== -1 && page.innerHTML.indexOf('class="cnt">1<') !== -1, "the settings show the names to check with a badge");
  const rowOrder = ['data-a="autoimport"', 'data-a="autoprocess"', 'data-a="tagsSuggest"', 'data-a="autocheck"', 'data-a="vocabAsk"'].map((n) => page.innerHTML.indexOf(n));
  check(rowOrder.every((at, i) => at !== -1 && (i === 0 || at > rowOrder[i - 1])), "the settings come in the agreed order: " + rowOrder.join(","));
  click({ "data-a": "vcToggle" });
  await settle();
  check(calls.indexOf("GET /api/vocabulary/check") !== -1, "opening the list asks for the names");
  check(page.innerHTML.indexOf('id="vcR:brandt"') !== -1 && page.innerHTML.indexOf("<mark>Brant</mark>") !== -1, "each name shows its spellings, an example and a field for the right one");
  typeInto("vcR:brandt", "BRANDT");
  typeInto("vcC:brandt", "awards");
  click({ "data-a": "vcApply", "data-id": "brandt" });
  await settle();
  check(calls.indexOf("POST /api/vocabulary/check/apply") !== -1, "the typed spelling is saved");
  check(page.innerHTML.indexOf('id="vcR:brandt"') === -1, "a saved name leaves the list");
  click({ "data-a": "settings" });
  await settle();

  // search by meaning: a pause in typing adds related passages below the usual results, whatever order the answers come in
  fx.state.search = { model: "qwen3-embedding:0.6b", indexed: 3, total: 3 };
  timers.splice(0).forEach((fn) => fn());
  await settle();
  click({ "data-a": "find" });
  await settle();
  typeInto("findInput", "why did it slip");
  for (let round = 0; round < 3; round += 1) { timers.splice(0).forEach((fn) => fn()); await settle(); }
  check(calls.some((c) => c.indexOf("GET /api/search/meaning?q=why") === 0), "a question is also asked by meaning");
  check(page.innerHTML.indexOf('data-id="n9"') !== -1, "the related passages are listed below the results");
  typeInto("findInput", "another question");
  check(page.innerHTML.indexOf('data-id="n9"') === -1, "related passages of an older question are not shown for a new one");
  click({ "data-a": "find" });
  await settle();

  // correcting a passage of the transcript by hand
  click({ "data-a": "viewText", "data-id": done.id });
  await settle();
  check(modal && modal.innerHTML.indexOf('data-tx="editSeg"') !== -1, "each line of the transcript can be corrected");
  const inModal = (attrs) => modal.handlers.click({ target: { closest: (sel) => (sel === "[data-tx]" ? { getAttribute: (n) => (attrs[n] === undefined ? null : attrs[n]) } : null) } });
  inModal({ "data-tx": "editSeg", "data-i": "0" });
  await settle();
  check(modal.innerHTML.indexOf('id="segInput"') !== -1 && modal.innerHTML.indexOf('data-tx="segAlways"') !== -1 && modal.innerHTML.indexOf('data-tx="segHere"') !== -1, "editing a line offers 'only here' and 'always'");
  typeInto("segInput", "A corrected line");
  inModal({ "data-tx": "segHere" });
  await settle();
  check(calls.some((c) => /^POST \/api\/note\/.*\/segment$/.test(c)), "the correction is sent");
  inModal({ "data-tx": "editSeg", "data-i": "0" });
  await settle();
  inModal({ "data-tx": "segCancel" });
  await settle();
  check(modal.innerHTML.indexOf('id="segInput"') === -1, "cancelling closes the editor");
  inModal({ "data-tx": "close" });
  await settle();

  // people: renamed and merged everywhere, voices erased
  click({ "data-a": "settings" });
  await settle();
  click({ "data-a": "pplToggle" });
  await settle();
  check(calls.indexOf("GET /api/people") !== -1 && page.innerHTML.indexOf("Anna B") !== -1 && page.innerHTML.indexOf('data-a="pplForgetAll"') !== -1, "the people of all the notes are listed");
  check(page.innerHTML.indexOf('data-a="pplOpenNote" data-id="n3"') !== -1, "the notes with unnamed speakers are listed");
  click({ "data-a": "pplEdit", "data-id": "Anna B" });
  await settle();
  typeInto("pplInput", "Anna");
  await settle();
  check(page.innerHTML.indexOf('data-a="pplSave"') !== -1 && /pplSave[^>]*data-tip="[^"]*(merged|fusionn)/.test(page.innerHTML), "naming a person like another one announces a merge");
  click({ "data-a": "pplSave" });
  await settle();
  check(calls.indexOf("POST /api/people/rename") !== -1, "the new name is sent");
  click({ "data-a": "pplForget", "data-id": "Anna" });
  await settle();
  check(calls.indexOf("POST /api/people/forget") !== -1, "a voiceprint can be erased");
  click({ "data-a": "pplToggle" });
  await settle();
  click({ "data-a": "settings" });
  await settle();

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
