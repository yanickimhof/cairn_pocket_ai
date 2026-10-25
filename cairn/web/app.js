(function () {
  "use strict";

  var D = {
    fr: {
      brand: "Cairn · Pocket AI souverain", components: "Composants",
      updAvail: "Mise à jour disponible : ", updFlash: "Relancez la commande d’installation",
      about: "À propos", aboutTagline: "Pocket AI souverain",
      aboutText: "Importez, transcrivez et résumez vos enregistrements Pocket, entièrement sur cet ordinateur. Aucun compte, aucun cloud, aucune télémétrie.",
      aboutLegal: "v{v} · © 2026 Yanick Imhof · Licence MIT · Non affilié à Pocket.", uiLang: "Langue de l’interface",
      polish: "Réécrire le transcript", polishHint: "Plus lisible, mais nettement plus lent", off: "Non", on: "Oui",
      processedIn: "traité en", notInstalled: "Non installé", getIt: "Installer", refText: "Acheter un Pocket : 10 % de réduction", refNote: "Lien de parrainage facultatif. L’offre dépend uniquement de Pocket et peut changer.",
      models: "Modèles", modelsHint: "Choisir ou ajouter des modèles", modelsSpeech: "Transcription", modelsLlm: "Résumés",
      tagline: "Votre Pocket. Votre ordinateur. Vos données.", mUse: "Utiliser", mRemove: "Supprimer ce modèle", mRemoveConfirm: "Supprimer {name} de cet ordinateur ? Vous pourrez le télécharger à nouveau.", mInUse: "Utilisé", mInstall: "Installer", mTier: { light: "Léger", standard: "Standard", high: "Élevé" },
      mRam: "{n} Go de mémoire conseillés", mConfirm: "Télécharger {name} ({size}) ? Une connexion internet est utilisée pour ce seul téléchargement.",
      mDownloading: "Téléchargement {pct} %", mFailed: "Échec du téléchargement : ", mDone: "Modèle installé", mDown: "Moteur local arrêté", mBusy: "Un traitement est en cours",
      settings: "Réglages", transcriptLang: "Langue du transcript", transcriptLangHint: "Langue des résumés",
      detail: "Niveau de détail par défaut", short: "Court", mid: "Normal", full: "Complet",
      shortHint: "Court : TL;DR et actions", midHint: "Normal : + contexte et points clés", fullHint: "Complet : + détail par sujet",
      emptyPocket: "Vider le Pocket", emptyHint: "Vider le Pocket (copies vérifiées)",
      emptyConfirm: "Vider le Pocket ? {n} copies vérifiées sur {m}.", emptyNone: "Le Pocket est vide.",
      emptyNot: "{n} copies vérifiées sur {m}. Importez d’abord.", emptyAbsent: "Pocket non détecté.",
      cancel: "Annuler", confirmLabel: "Confirmer",
      connected: "Pocket connecté", disconnected: "Pocket non détecté", local: "Local", localHint: "Tout reste sur cet ordinateur",
      folder: "Dossier des audios", folderHint: "Dossier de sauvegarde des audios", folderChange: "Changer", folderSaved: "Dossier enregistré", folderType: "Chemin du dossier",
      exportLabel: "Exporter", exportHint: "Copier ou exporter la fiche", copyRich: "Copier", copyRichHint: "Copier, prêt à coller dans un courriel",
      copiedRich: "Copié", expMdHint: "Markdown", expHtmlHint: "HTML", exported: "Exporté en ",
      importLabel: "Importer et transcrire", importHint: "Importer et traiter les enregistrements", count: "Enregistrements sur le Pocket",
      eyeShow: "Afficher la liste", eyeHide: "Masquer la liste", hiddenNote: "Mode sécurisé",
      rowHint: "Ouvrir", actionsHint: "Afficher les actions", durHint: "Durée", dateDur: "Date · durée", qualityHint: "Fiabilité estimée",
      rename: "Renommer", saveName: "Enregistrer", rerun: "Relancer le résumé", rerunHint: "Relancer au niveau choisi",
      copilot: "Copier les passages douteux", passages: " à vérifier", copilotHint: "clic pour copier",
      deleteLocal: "Supprimer de cet ordinateur", deleteHint: "Supprimer audio et textes",
      deleteConfirm: "Supprimer audio et textes ? Si le Pocket est vidé, plus aucune copie.",
      copied: "Copié", rerunning: "Résumé relancé : ", renamed: "Nom enregistré", deleted: "Supprimé", pocketEmptied: "Pocket vidé",
      ready: "Prêt", waiting: "En attente", failed: "Échec : relancer le résumé", done: "Terminé", modelDown: "Moteur local arrêté : relancez Cairn",
      privAuto: "Contrôle automatique", privOk: "aucune connexion vers l’extérieur", privBad: "connexions détectées, voir docs/PRIVACY.md", privNone: "en attente", autoCheck: "Vérifier les mises à jour", autoHint: "Une requête à GitHub par jour",
      processNow: "Traiter maintenant", skipIt: "Ignorer", skipped: "Ignoré", putBack: "Remettre dans la file", stopJob: "Arrêter",
      steps: { copying: "Copie depuis le Pocket", transcribing: "Transcription", cleaning: "Nettoyage du texte", summarizing: "Rédaction de la note", privacy: "Vérification de la confidentialité" },
      none: "Aucun enregistrement.", tldr: "En bref", actions: "Actions", points: "Points clés", noSpeech: "Aucune parole détectée.",
      months: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."], error: "Erreur : "
    },
    en: {
      brand: "Cairn · Sovereign Pocket AI", components: "Components",
      updAvail: "Update available: ", updFlash: "Run the install command again",
      about: "About", aboutTagline: "Sovereign Pocket AI",
      aboutText: "Import, transcribe and summarize your Pocket recordings, entirely on this computer. No account, no cloud, no telemetry.",
      aboutLegal: "v{v} · © 2026 Yanick Imhof · MIT license · Not affiliated with Pocket.", uiLang: "Interface language",
      polish: "Polish the transcript", polishHint: "More readable, but much slower", off: "Off", on: "On",
      processedIn: "processed in", notInstalled: "Not installed", getIt: "Install", refText: "Get a Pocket: 10 % off", refNote: "Optional referral link. The offer is set by Pocket alone and may change.",
      models: "Models", modelsHint: "Choose or add models", modelsSpeech: "Transcription", modelsLlm: "Summaries",
      tagline: "Your Pocket. Your computer. Your data.", mUse: "Use", mRemove: "Remove this model", mRemoveConfirm: "Remove {name} from this computer? You can download it again later.", mInUse: "In use", mInstall: "Install", mTier: { light: "Light", standard: "Standard", high: "High" },
      mRam: "{n} GB of memory advised", mConfirm: "Download {name} ({size})? An internet connection is used for this download only.",
      mDownloading: "Downloading {pct}%", mFailed: "Download failed: ", mDone: "Model installed", mDown: "Local engine stopped", mBusy: "A job is running",
      settings: "Settings", transcriptLang: "Transcript language", transcriptLangHint: "Summary language",
      detail: "Default level of detail", short: "Short", mid: "Standard", full: "Detailed",
      shortHint: "Short: TL;DR and actions", midHint: "Standard: + context, key points", fullHint: "Detailed: + detail per topic",
      emptyPocket: "Empty the Pocket", emptyHint: "Empty the Pocket (copies verified)",
      emptyConfirm: "Empty the Pocket? {n} of {m} copies verified.", emptyNone: "The Pocket is empty.",
      emptyNot: "{n} of {m} copies verified. Import first.", emptyAbsent: "Pocket not detected.",
      cancel: "Cancel", confirmLabel: "Confirm",
      connected: "Pocket connected", disconnected: "Pocket not detected", local: "Local", localHint: "Everything stays on this computer",
      folder: "Audio folder", folderHint: "Audio backup folder", folderChange: "Change", folderSaved: "Folder saved", folderType: "Folder path",
      exportLabel: "Export", exportHint: "Copy or export the note", copyRich: "Copy", copyRichHint: "Copy, ready to paste in an email",
      copiedRich: "Copied", expMdHint: "Markdown", expHtmlHint: "HTML", exported: "Exported as ",
      importLabel: "Import and transcribe", importHint: "Import and process the recordings", count: "Recordings on the Pocket",
      eyeShow: "Show the list", eyeHide: "Hide the list", hiddenNote: "Secure mode",
      rowHint: "Open", actionsHint: "Show actions", durHint: "Length", dateDur: "Date · length", qualityHint: "Estimated reliability",
      rename: "Rename", saveName: "Save", rerun: "Rerun the summary", rerunHint: "Rerun at the chosen level",
      copilot: "Copy doubtful passages", passages: " to check", copilotHint: "click to copy",
      deleteLocal: "Delete from this computer", deleteHint: "Delete audio and texts",
      deleteConfirm: "Delete audio and texts? If the Pocket is emptied, no copy remains.",
      copied: "Copied", rerunning: "Summary rerun: ", renamed: "Name saved", deleted: "Deleted", pocketEmptied: "Pocket emptied",
      ready: "Ready", waiting: "Waiting", failed: "Failed: rerun the summary", done: "Done", modelDown: "Local engine stopped: restart Cairn",
      privAuto: "Automatic check", privOk: "no connection to the outside", privBad: "connections detected, see docs/PRIVACY.md", privNone: "pending", autoCheck: "Check for updates", autoHint: "One request to GitHub per day",
      processNow: "Process now", skipIt: "Skip", skipped: "Skipped", putBack: "Put back in the queue", stopJob: "Stop",
      steps: { copying: "Copying from the Pocket", transcribing: "Transcribing", cleaning: "Cleaning the text", summarizing: "Writing the note", privacy: "Checking privacy" },
      none: "No recordings.", tldr: "TL;DR", actions: "Actions", points: "Key points", noSpeech: "No speech detected.",
      months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], error: "Error: "
    }
  };

  var I = {
    info: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5"></path><path d="M12 8h.01"></path></svg>',
    gear: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h10"></path><path d="M18 7h2"></path><circle cx="16" cy="7" r="2"></circle><path d="M4 17h2"></path><path d="M10 17h10"></path><circle cx="8" cy="17" r="2"></circle></svg>',
    doc: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 3h7l4 4v14H7z"></path><path d="M14 3v4h4"></path><path d="M10 12h5"></path><path d="M10 16h5"></path></svg>',
    lines: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16"></path><path d="M4 12h12"></path><path d="M4 17h8"></path></svg>',
    folder: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>',
    mic: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0"></path><path d="M12 18v3"></path></svg>',
    pencil: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"></path><path d="m13.5 6.5 4 4"></path></svg>',
    trash: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C4271B" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16"></path><path d="M9 7V4h6v3"></path><path d="M6 7l1 13h10l1-13"></path><path d="M10 11v6"></path><path d="M14 11v6"></path></svg>',
    x: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12"></path><path d="M18 6 6 18"></path></svg>',
    checkW: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>',
    shield: function (c, n) { n = n || 20; return '<svg width="' + n + '" height="' + n + '" viewBox="0 0 24 24" fill="none" stroke="' + c + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 5 6v5c0 4.5 2.9 8.2 7 9.5 4.1-1.3 7-5 7-9.5V6l-7-3Z"></path><path d="m9 12 2 2 4-4"></path></svg>'; },
    checkB: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3368A0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>',
    warnB: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C86D51" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4 3 20h18z"></path><path d="M12 10v4"></path><path d="M12 17h.01"></path></svg>',
    refresh: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"></path><path d="M20 4v7h-7"></path></svg>',
    refreshW: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"></path><path d="M20 4v7h-7"></path></svg>',
    down: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"></path><path d="m7 11 5 5 5-5"></path><path d="M5 20h14"></path></svg>',
    downBig: '<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"></path><path d="m7 11 5 5 5-5"></path><path d="M5 20h14"></path></svg>',
    copy: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="3"></rect><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path></svg>',
    eye: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
    eyeOff: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#C86D51" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"></path><circle cx="12" cy="12" r="3"></circle><path d="M3 3l18 18"></path></svg>',
    done: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3368A0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="m8 12.5 2.8 2.8L16 9.5"></path></svg>',
    wait: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#B8B8BE" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>',
    busy: '<svg class="spin" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#3368A0" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9"></path></svg>',
    skip: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#B8B8BE" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M8 12h8"></path></svg>',
    play: '<svg width="20" height="20" viewBox="0 0 24 24" fill="#3368A0" aria-hidden="true"><path d="M8 5l11 7-11 7z"></path></svg>',
    stop: '<svg width="18" height="18" viewBox="0 0 24 24" fill="#C4271B" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>',
    fail: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#C86D51" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v5"></path><path d="M12 16h.01"></path></svg>',
    lvl: {
      short: '<path d="M7 12h10"></path>',
      mid: '<path d="M7 9h10"></path><path d="M7 15h7"></path>',
      full: '<path d="M7 7h10"></path><path d="M7 12h10"></path><path d="M7 17h6"></path>'
    }
  };

  var S = {
    ui: null, hidden: true, settingsOpen: false, aboutOpen: false, open: null, edit: null, draft: "", exp: null,
    delConfirm: false, emptyConfirm: false, verify: null, rr: "mid", server: null, full: {}, about: null, upd: null,
    folderEdit: false, folderDraft: "", wasRunning: false
  };
  var lastView = "";
  var toastTimer = null;

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function ui() { return S.ui || (S.server && S.server.settings.ui) || ((navigator.language || "en").slice(0, 2) === "fr" ? "fr" : "en"); }
  function T() { return D[ui()]; }
  function tr() { return (S.server && S.server.settings.tr) || ui(); }
  function level() { return (S.server && S.server.settings.level) || "mid"; }

  function api(method, path, body) {
    var opt = { method: method, headers: {} };
    if (method === "POST") { opt.headers["Content-Type"] = "application/json"; opt.headers["X-Cairn"] = "1"; opt.body = JSON.stringify(body || {}); }
    return fetch(path, opt).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) { var e = new Error(data.error || "error"); e.status = r.status; e.data = data; throw e; }
        return data;
      });
    });
  }
  function fetchText(path) {
    return fetch(path).then(function (r) { if (!r.ok) { throw new Error("error"); } return r.text(); });
  }

  function flash(msg) {
    var el = document.getElementById("toast");
    el.innerHTML = "<span>" + I.checkW.replace('width="20" height="20"', 'width="18" height="18"') + esc(msg) + "</span>";
    el.className = "show";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.className = ""; }, 2600);
  }

  function fmtDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
    if (!m) { return ""; }
    var mon = T().months[parseInt(m[2], 10) - 1], day = parseInt(m[3], 10), hm = m[4] + ":" + m[5];
    return ui() === "fr" ? day + " " + mon + ", " + hm : mon + " " + day + ", " + hm;
  }
  function fmtDur(sec) {
    if (!sec) { return ""; }
    sec = Math.round(sec);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return h ? h + ":" + pad(m) + ":" + pad(s) : m + ":" + pad(s);
  }
  function shortPath(p) { return String(p || "").replace(/^\/(Users|home)\/[^/]+/, "~").replace(/^[A-Za-z]:\\Users\\[^\\]+/, "~"); }
  function bg(on) { return on ? " on" : ""; }
  function tip(text) { return text ? ' data-tip="' + esc(text) + '" aria-label="' + esc(text) + '"' : ""; }

  function seg3(prefix, current, size, t) {
    return '<div class="seg ' + size + '">' + ["short", "mid", "full"].map(function (k) {
      return '<button type="button" class="' + (current === k ? "on" : "") + '" data-a="' + prefix + '" data-v="' + k + '"' + tip(t[k + "Hint"]) + '><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" aria-hidden="true">' + I.lvl[k] + "</svg></button>";
    }).join("") + "</div>";
  }
  function segLang(prefix, current, size, t, hint) {
    return '<div class="seg ' + size + '">' + ["fr", "en"].map(function (k) {
      return '<button type="button" class="' + (current === k ? "on" : "") + '" data-a="' + prefix + '" data-v="' + k + '"' + tip(hint) + ">" + k.toUpperCase() + "</button>";
    }).join("") + "</div>";
  }
  function confirmBox(text, yes, t) {
    return '<div class="confirm"><div>' + esc(text) + '</div><div class="row gap8">' +
      '<button type="button" class="ib grey2" data-a="cancel"' + tip(t.cancel) + ">" + I.x + "</button>" +
      (yes ? '<button type="button" class="ib red" data-a="' + yes + '"' + tip(t.confirmLabel) + ">" + I.checkW + "</button>" : "") + "</div></div>";
  }

  function gb(bytes) { return (bytes / 1e9).toFixed(1) + " GB"; }

  function modelRow(kind, m, t, job) {
    var running = job && job.state === "running" && job.kind === kind && job.id === m.id;
    var h = '<div class="mrow"><div class="minfo"><div class="mname">' + esc(m.label) + "</div>";
    h += '<div class="small">' + esc(t.mTier[m.tier] + " · " + gb(m.bytes) + " · " + t.mRam.replace("{n}", m.ram)) + "</div></div>";
    if (running) { h += '<span class="small">' + esc(t.mDownloading.replace("{pct}", job.pct)) + "</span>"; }
    else if (m.selected) { h += '<span class="mtag">' + esc(t.mInUse) + "</span>"; }
    else if (m.installed) {
      h += '<span class="row gap8"><button type="button" class="mbtn" data-a="mUse" data-v="' + kind + '" data-id="' + esc(m.id) + '">' + esc(t.mUse) + "</button>" +
        '<button type="button" class="ib" data-a="mDel" data-v="' + kind + '" data-id="' + esc(m.id) + '"' + tip(t.mRemove) + ">" + I.trash + "</button></span>";
    }
    else { h += '<button type="button" class="mbtn" data-a="mAsk" data-v="' + kind + '" data-id="' + esc(m.id) + '"' + (job && job.state === "running" ? " disabled" : "") + ">" + esc(t.mInstall) + "</button>"; }
    return h + "</div>";
  }

  function viewModels(t) {
    var M = S.models;
    if (!M) { return ""; }
    var h = '<div class="hr"></div><div class="mlist"><div class="mgroup">' + esc(t.modelsSpeech) + "</div>";
    M.speech.forEach(function (m) { h += modelRow("speech", m, t, M.job); });
    h += '<div class="mgroup">' + esc(t.modelsLlm) + "</div>";
    M.llm.forEach(function (m) { h += modelRow("llm", m, t, M.job); });
    if (S.mAsk) {
      var list = S.mAsk.kind === "llm" ? M.llm : M.speech;
      var m = list.filter(function (x) { return x.id === S.mAsk.id; })[0];
      if (m) { h += confirmBox(t.mConfirm.replace("{name}", m.label).replace("{size}", gb(m.bytes)), "mGo", t); }
    }
    if (S.mDel) {
      var dl = S.mDel.kind === "llm" ? M.llm : M.speech;
      var dm = dl.filter(function (x) { return x.id === S.mDel.id; })[0];
      if (dm) { h += confirmBox(t.mRemoveConfirm.replace("{name}", dm.label), "mDelGo", t); }
    }
    if (M.job && M.job.state === "error") { h += '<div class="small" style="color:#C0392B">' + esc(t.mFailed + M.job.error) + "</div>"; }
    return h + "</div>";
  }

  function viewSettings(t, st) {
    var h = '<div class="card panel">';
    h += '<div class="setrow"' + tip(t.transcriptLangHint) + ">" + I.doc + segLang("tr", tr(), "s38", t, t.transcriptLangHint) + "</div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.detail) + ">" + I.lines + seg3("lvl", level(), "s38", t) + "</div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.polishHint) + '><span class="text" style="font-size:14px">' + esc(t.polish) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="polish" data-v="' + o[0] + '" class="' + bg(!!st.settings.polish === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.autoHint) + '><span class="text" style="font-size:14px">' + esc(t.autoCheck) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="autocheck" data-v="' + o[0] + '" class="' + bg(st.settings.autocheck !== false === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.folderHint) + ">" + I.folder;
    h += '<div class="row gap8" style="min-width:0"><span class="text" style="font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(shortPath(st.settings.audio_dir)) + "</span>";
    h += '<button type="button" class="ib" data-a="folder"' + tip(t.folderChange) + ">" + I.pencil + "</button></div></div>";
    if (S.folderEdit) {
      h += '<div class="name" style="margin:0 0 14px"><input id="folderInput" type="text" value="' + esc(S.folderDraft) + '" placeholder="' + esc(t.folderType) + '" aria-label="' + esc(t.folderType) + '">' +
        '<button type="button" class="ib blue" data-a="folderSave"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
    }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.modelsHint) + "><span class=\"text\" style=\"font-size:14px\">" + esc(t.models) + '</span><button type="button" class="mbtn" data-a="models">' + esc(S.modelsOpen ? "−" : "+") + "</button></div>";
    if (S.modelsOpen) { h += viewModels(t); }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.emptyHint) + ">" + I.mic + '<button type="button" class="ib" data-a="askEmpty"' + tip(t.emptyPocket) + ">" + I.trash + "</button></div>";
    if (S.emptyConfirm) {
      var v = S.verify, text, yes = null;
      if (!st.pocket.connected) { text = t.emptyAbsent; }
      else if (!v) { text = "…"; }
      else if (!v.total) { text = t.emptyNone; }
      else if (v.verified < v.total) { text = t.emptyNot.replace("{n}", v.verified).replace("{m}", v.total); }
      else { text = t.emptyConfirm.replace("{n}", v.verified).replace("{m}", v.total); yes = "confirmEmpty"; }
      h += confirmBox(text, yes, t);
    }
    return h + "</div>";
  }

  function fmtSize(bytes) {
    if (!bytes) { return "-"; }
    if (bytes < 1e6) { return "< 1 MB"; }
    return bytes < 1e9 ? Math.round(bytes / 1e6) + " MB" : (bytes / 1e9).toFixed(1) + " GB";
  }

  function viewAbout(t) {
    var h = '<div class="card about"><div><div class="t">Cairn</div><div class="small">' + esc(t.aboutTagline) + "</div></div>";
    h += '<div class="text">' + esc(t.aboutText) + "</div>";
    h += '<div style="display:flex;flex-direction:column;gap:8px"><div class="text" style="font-size:14px;font-weight:600">' + esc(t.components) + "</div>";
    ((S.about && S.about.components) || []).forEach(function (c) {
      var fix = !c.ok && c.fix ? '<button type="button" class="mbtn" data-a="fixModel">' + esc(t.getIt) + "</button>" : "";
      h += '<div class="comp"><span class="cn">' + esc(c.name) + '</span><span class="cv">' + esc(c.ok ? c.ver : t.notInstalled) + '</span><span class="cs">' + esc(c.ok ? fmtSize(c.size) : "") + "</span>" + (c.ok ? I.checkB : (fix || I.warnB)) + "</div>";
    });
    h += "</div>";
    var upd = S.server && S.server.update;
    if (upd && upd.available) {
      h += '<div><div class="text" style="font-size:14px;font-weight:600;color:var(--warn)">' + esc(t.updAvail + upd.latest) + '</div><div class="small">' + esc(t.updFlash) + "</div></div>";
    }
    var ref = S.about && S.about.referral;
    if (ref) {
      h += '<div class="ref"><a href="' + esc(ref) + '" target="_blank" rel="noopener noreferrer"' + tip(t.refNote) + ">" + esc(t.refText) + " ↗</a></div>";
    }
    h += '<div class="hr"></div><div class="legal">' + esc(t.aboutLegal.replace("{v}", (S.server && S.server.version) || "")) + "</div></div>";
    return h;
  }

  function stepText(job, t) {
    var base = (job && job.step && t.steps[job.step]) || "";
    return base && job.pct != null ? base + " · " + job.pct + " %" : base;
  }

  function statusIcon(n, job) {
    if (n.status === "done") { return I.done; }
    if (n.status === "error") { return I.fail; }
    if (job.running && job.id === n.id) { return I.busy; }
    return n.status === "skipped" ? I.skip : I.wait;
  }

  function viewDetail(n, t) {
    var full = S.full[n.id];
    var h = '<div class="detail">';
    if (S.edit === n.id) {
      h += '<div class="name"><input id="nameInput" type="text" value="' + esc(S.draft) + '" aria-label="' + esc(t.rename) + '"><button type="button" class="ib blue" data-a="saveName"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
    }
    var passInk = n.quality != null && n.quality < 85 ? "var(--warn)" : "var(--mute)";
    h += '<div class="bar"><div class="row gap8">' + seg3("rr", S.rr, "s36", t) +
      '<button type="button" class="ib blue" data-a="rerun"' + tip(t.rerunHint) + ">" + I.refreshW + "</button></div>";
    h += '<div class="row" style="gap:4px">';
    h += '<button type="button" class="warn" data-a="copyDoubtful" style="color:' + passInk + '"' + tip(n.passages + t.passages + " · " + t.copilotHint) + ">" + (passInk === "var(--orange)" ? I.warnB.replace('width="16" height="16"', 'width="18" height="18"') : I.warnB.replace("#C86D51", "#6E6E73").replace('width="16" height="16"', 'width="18" height="18"')) + (n.passages || 0) + "</button>";
    h += '<button type="button" class="ib" data-a="startRename"' + tip(t.rename) + ">" + I.pencil + "</button>";
    h += '<button type="button" class="ib" data-a="toggleExport"' + tip(t.exportHint) + ">" + I.down + "</button>";
    h += '<button type="button" class="ib" data-a="askDelete"' + tip(t.deleteHint) + ">" + I.trash + "</button></div></div>";
    if (S.exp === n.id) {
      h += '<div class="exp"><button type="button" class="main" data-a="expCopy"' + tip(t.copyRichHint) + ">" + I.copy + '</button><button type="button" data-a="expMd"' + tip(t.expMdHint) + '>MD</button><button type="button" data-a="expHtml"' + tip(t.expHtmlHint) + ">HTML</button></div>";
    }
    if (S.delConfirm) { h += confirmBox(t.deleteConfirm, "confirmDelete", t); }
    if (n.error) { h += '<div class="err">' + esc(t.error + n.error) + "</div>"; }
    if (full && full.summary) {
      var s = full.summary;
      h += '<div class="read">';
      if (s.empty) { h += "<div>" + esc(t.noSpeech) + "</div>"; }
      if (s.tldr) { h += "<div><b>" + esc(t.tldr) + ".</b> " + esc(s.tldr) + "</div>"; }
      if (s.actions && s.actions.length) {
        h += "<div><b>" + esc(t.actions) + "</b><ul>" + s.actions.map(function (a) {
          var extra = [a.who, a.when].filter(Boolean).join(" ");
          return "<li>" + esc(a.what) + (extra ? " (" + esc(extra) + ")" : "") + "</li>";
        }).join("") + "</ul></div>";
      }
      if (s.key_points && s.key_points.length) {
        h += "<div><b>" + esc(t.points) + "</b><ul>" + s.key_points.map(function (p) { return "<li>" + esc(p) + "</li>"; }).join("") + "</ul></div>";
      }
      var info = [];
      if (full.models && full.models.speech) { info.push(full.models.speech); }
      if (full.models && full.models.llm) { info.push(full.models.llm); }
      if (full.elapsed) { info.push(t.processedIn + " " + fmtDur(full.elapsed)); }
      if (info.length) { h += '<div class="small" style="margin-top:10px">' + esc(info.join(" · ")) + "</div>"; }
      h += "</div>";
    }
    return h + "</div>";
  }

  function queueActions(n, job, t) {
    var h = '<div class="detail"><div class="row gap8">';
    if (job.running && job.id === n.id) {
      h += '<button type="button" class="ib" data-a="stopJob"' + tip(t.stopJob) + ">" + I.stop + "</button>";
    } else {
      h += '<button type="button" class="ib" data-a="procOne" data-id="' + esc(n.id) + '"' + (job.running ? " disabled" : "") + tip(t.processNow) + ">" + I.play + "</button>";
      h += n.status === "skipped"
        ? '<button type="button" class="mbtn" data-a="restoreOne" data-id="' + esc(n.id) + '">' + esc(t.putBack) + "</button>"
        : '<button type="button" class="mbtn" data-a="skipOne" data-id="' + esc(n.id) + '">' + esc(t.skipIt) + "</button>";
    }
    return h + "</div></div>";
  }

  function viewList(t, st) {
    var notes = st.notes || [];
    if (!notes.length) { return '<div class="card" style="padding:22px;text-align:center"><span class="small">' + esc(t.none) + "</span></div>"; }
    return '<div class="list">' + notes.map(function (n) {
      var done = n.status === "done", running = st.job.running && st.job.id === n.id;
      var main = done ? n.title : fmtDate(n.date) || n.id;
      var sub = done ? [fmtDate(n.date), fmtDur(n.duration)].filter(Boolean).join(" · ") : (running ? stepText(st.job, t) : (n.status === "skipped" ? t.skipped + " · " : "") + fmtDur(n.duration));
      var open = S.open === n.id;
      var rowTip = running ? stepText(st.job, t) : (done || n.status === "error" ? t.rowHint : t.actionsHint);
      var subTip = done ? t.dateDur : (running ? "" : t.durHint);
      var bar = running && st.job.pct != null ? '<span class="pbar"><span style="width:' + st.job.pct + '%"></span></span>' : "";
      var q = done && n.quality != null ? '<span class="q" style="color:' + (n.quality < 85 ? "var(--warn)" : "var(--mute)") + '"' + tip(t.qualityHint) + ">" + n.quality + " %</span>" : "";
      return '<div class="item"><button type="button" class="rowbtn" data-a="row" data-id="' + esc(n.id) + '" aria-expanded="' + open + '"' + tip(rowTip) + '><span class="st">' + statusIcon(n, st.job) +
        '</span><span class="mid"><span class="main">' + esc(main) + '</span><span class="sub"' + tip(subTip) + ">" + esc(sub) + "</span>" + bar + '</span><span style="min-width:54px;display:inline-flex;justify-content:flex-end">' + q + "</span></button>" +
        (open && (done || n.status === "error") ? viewDetail(n, t) : "") +
        (open && !done ? queueActions(n, st.job, t) : "") + "</div>";
    }).join("") + "</div>";
  }

  function view() {
    var st = S.server;
    if (!st) { return ""; }
    var t = T(), job = st.job, ring = 0;
    if (job.running && job.total) { ring = Math.min(1, (job.done + (job.pct != null ? job.pct / 100 : 0.5)) / job.total); }
    else if (st.totals.notes) { ring = st.totals.done / st.totals.notes; }
    var connected = st.pocket.connected;
    var canImport = !job.running && (connected || st.totals.waiting > 0);
    var h = '<main class="wrap"><div class="head"><div class="row gap12"><div class="bw"><h1 class="brand"' + tip(t.brand) + '>Cairn</h1><div class="sub">' + esc(t.aboutTagline) + "</div></div>";
    h += '<button type="button" class="dotbtn"' + tip(connected ? t.connected : t.disconnected) + '><span class="dot" style="background:' + (connected ? "var(--green)" : "var(--orange)") + ";box-shadow:0 0 0 4px " + (connected ? "rgba(31,157,85,.18)" : "rgba(200,109,81,.24)") + '"></span></button>';
    var pv = st.privacy, sc = !pv ? "#86868B" : (pv.ok ? "#1E8E3E" : "#A4452A");
    var pt = t.localHint + ". " + t.privAuto + ": " + (!pv ? t.privNone : (pv.ok ? t.privOk + " · " + fmtDate(pv.when) : t.privBad));
    h += '<span class="pill"' + tip(pt) + ">" + I.shield(sc, 18) + esc(t.local) + "</span></div>";
    h += '<div class="row" style="gap:2px"><div style="margin-right:6px"' + tip(t.uiLang) + ">" + segLang("ui", ui(), "s34", t, "") + "</div>";
    h += '<button type="button" class="ib plain' + bg(S.aboutOpen) + (st.update && st.update.available ? " upd" : "") + '" data-a="about"' + tip(t.about) + ">" + I.info + "</button>";
    h += '<button type="button" class="ib plain' + bg(S.settingsOpen) + '" data-a="settings"' + tip(t.settings) + ">" + I.gear + "</button></div></div>";
    if (S.settingsOpen) { h += viewSettings(t, st); }
    if (S.aboutOpen) { h += viewAbout(t); }
    h += '<div class="hero"><div class="ring"' + (job.running ? tip(stepText(job, t)) : "") + '><svg class="arc" width="156" height="156" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" fill="none" stroke="#E5E5EA" stroke-width="3"></circle>' +
      '<circle cx="50" cy="50" r="46" fill="none" stroke="#3368A0" stroke-width="3" stroke-linecap="round" stroke-dasharray="' + (ring * 289).toFixed(1) + ' 289" transform="rotate(-90 50 50)"></circle></svg>';
    h += '<button type="button" class="import' + (job.running ? " busy" : "") + '" data-a="import"' + (canImport ? "" : " disabled") + tip(t.importHint) + ">" + I.downBig + "</button>";
    if (connected) { h += '<span class="badge"' + tip(t.count) + ">" + st.pocket.count + "</span>"; }
    h += "</div></div>";
    h += '<div class="eye"><button type="button" class="ib' + (S.hidden ? " hiddenon" : "") + '" data-a="eye" aria-pressed="' + S.hidden + '"' + tip(S.hidden ? t.eyeShow : t.eyeHide) + ">" + (S.hidden ? I.eyeOff : I.eye) + "</button>";
    if (S.hidden) { h += '<div class="note">' + esc(t.hiddenNote) + "</div>"; }
    if (!st.ollama) { h += '<div class="err">' + esc(t.modelDown) + "</div>"; }
    h += "</div>";
    if (!S.hidden) { h += viewList(t, st); }
    h += '<footer class="foot"><b>Cairn</b> · ' + esc(t.tagline) + "</footer>";
    return h + "</main>";
  }

  function render() {
    var html = view();
    var key = html + "|" + ui();
    if (key === lastView) { return; }
    lastView = key;
    var app = document.getElementById("app");
    var focus = document.activeElement && document.activeElement.id;
    var value = focus && document.activeElement.value;
    app.innerHTML = html;
    document.documentElement.lang = ui();
    if (focus && document.getElementById(focus)) {
      var el = document.getElementById(focus);
      el.focus();
      if (el.setSelectionRange && typeof value === "string") { el.value = value; el.setSelectionRange(value.length, value.length); }
    } else if (S.edit && document.getElementById("nameInput")) {
      var inp = document.getElementById("nameInput"); inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
    }
  }

  function noteAction(id, action) {
    api("POST", "/api/note/" + encodeURIComponent(id) + "/" + action).then(refresh)
      .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
  }

  function loadModels() {
    return api("GET", "/api/models").then(function (m) {
      var was = S.models && S.models.job && S.models.job.state === "running";
      S.models = m;
      if (was && m.job && m.job.state === "done") { flash(T().mDone); }
      render();
    }).catch(function () { /* keep what is shown */ });
  }

  function refresh() {
    return api("GET", "/api/state?list=" + (S.hidden ? "0" : "1")).then(function (st) {
      var was = S.wasRunning;
      S.server = st;
      S.wasRunning = st.job.running;
      if (was && !st.job.running) {
        if (st.job.errors.length) { flash(T().error + st.job.errors[0]); } else { flash(T().done); }
        S.full = {};
      }
      if (S.open && !S.hidden) { loadFull(S.open); }
      if (S.modelsOpen && (!S.models || (st.download && st.download.state === "running") || (S.models.job && S.models.job.state === "running"))) { loadModels(); }
      render();
    }).catch(function () { /* the server is gone or busy: keep what is shown */ });
  }

  function loadFull(id) {
    var n = ((S.server && S.server.notes) || []).filter(function (x) { return x.id === id; })[0];
    if (!n || (n.status !== "done" && n.status !== "error") || S.full[id]) { return; }
    S.full[id] = { loading: true };
    api("GET", "/api/note/" + encodeURIComponent(id)).then(function (note) { S.full[id] = note; render(); }).catch(function () { delete S.full[id]; });
  }

  function download(id, fmt) {
    var path = "/api/note/" + encodeURIComponent(id) + "/export?fmt=" + fmt + "&save=1";
    return fetch(path).then(function (r) { if (!r.ok) { throw new Error("error"); } return r.blob(); }).then(function (blob) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = ((S.server.notes.filter(function (n) { return n.id === id; })[0] || {}).title || id).replace(/[^\w.-]+/g, "_") + (fmt === "md" ? ".md" : ".html");
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
      flash(T().exported + (fmt === "md" ? ".md" : ".html"));
    });
  }

  function copyRich(id) {
    var base = "/api/note/" + encodeURIComponent(id) + "/export?";
    return Promise.all([fetchText(base + "fmt=html&fragment=1&transcript=0"), fetchText(base + "fmt=text")]).then(function (parts) {
      if (navigator.clipboard && window.ClipboardItem) {
        return navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([parts[0]], { type: "text/html" }), "text/plain": new Blob([parts[1]], { type: "text/plain" }) })]);
      }
      return navigator.clipboard.writeText(parts[1]);
    }).then(function () { flash(T().copiedRich); });
  }

  var A = {
    ui: function (v) { S.ui = v; api("POST", "/api/settings", { ui: v }).then(refresh); },
    tr: function (v) { api("POST", "/api/settings", { tr: v }).then(refresh); },
    polish: function (v) { api("POST", "/api/settings", { polish: v === "1" }).then(refresh); },
    autocheck: function (v) { api("POST", "/api/settings", { autocheck: v === "1" }).then(refresh); },
    lvl: function (v) { api("POST", "/api/settings", { level: v }).then(refresh); },
    settings: function () { S.settingsOpen = !S.settingsOpen; S.emptyConfirm = false; },
    about: function () {
      S.aboutOpen = !S.aboutOpen;
      if (S.aboutOpen) { api("GET", "/api/about").then(function (a) { S.about = a; render(); }); }
    },
    eye: function () {
      S.hidden = !S.hidden;
      if (S.hidden) { S.open = null; S.full = {}; if (S.server) { S.server.notes = []; } }
      refresh();
    },
    import: function () {
      api("POST", "/api/import").then(refresh).catch(function (e) { flash(T().error + e.message); });
    },
    row: function (v, id) { S.open = S.open === id ? null : id; S.delConfirm = false; S.edit = null; S.exp = null; S.rr = level(); if (S.open) { loadFull(id); } },
    rr: function (v) { S.rr = v; },
    rerun: function () {
      var t = T(), id = S.open;
      api("POST", "/api/note/" + encodeURIComponent(id) + "/rerun", { level: S.rr }).then(function () { delete S.full[id]; flash(t.rerunning + t[S.rr].toLowerCase()); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
    },
    copyDoubtful: function () {
      var id = S.open;
      fetchText("/api/note/" + encodeURIComponent(id) + "/export?fmt=doubtful").then(function (txt) { return navigator.clipboard.writeText(txt); }).then(function () { flash(T().copied); });
    },
    startRename: function () {
      var n = S.server.notes.filter(function (x) { return x.id === S.open; })[0];
      S.edit = S.open; S.draft = n ? n.title : "";
    },
    saveName: function () {
      var id = S.edit, title = S.draft.trim();
      if (!title) { return; }
      api("POST", "/api/note/" + encodeURIComponent(id) + "/rename", { title: title }).then(function () { S.edit = null; flash(T().renamed); delete S.full[id]; refresh(); });
    },
    toggleExport: function () { S.exp = S.exp === S.open ? null : S.open; },
    expMd: function () { download(S.open, "md"); },
    expHtml: function () { download(S.open, "html"); },
    expCopy: function () { copyRich(S.open).catch(function () { flash(T().error + "clipboard"); }); },
    askDelete: function () { S.delConfirm = true; },
    confirmDelete: function () {
      var id = S.open;
      api("POST", "/api/note/" + encodeURIComponent(id) + "/delete").then(function () { S.open = null; S.delConfirm = false; flash(T().deleted); refresh(); });
    },
    cancel: function () { S.delConfirm = false; S.emptyConfirm = false; S.mAsk = null; S.mDel = null; },
    askEmpty: function () {
      S.emptyConfirm = true; S.verify = null;
      api("GET", "/api/pocket/verify").then(function (v) { S.verify = v; render(); }).catch(function () { S.verify = { total: 0, verified: 0 }; render(); });
    },
    confirmEmpty: function () {
      api("POST", "/api/pocket/empty", { confirm: true }).then(function () { S.emptyConfirm = false; flash(T().pocketEmptied); refresh(); })
        .catch(function (e) { S.emptyConfirm = false; flash(T().error + e.message); });
    },
    folder: function () {
      api("POST", "/api/pick-folder").then(function (r) { return api("POST", "/api/settings", { audio_dir: r.path }); })
        .then(function () { flash(T().folderSaved); refresh(); })
        .catch(function (e) { if (e.status === 501) { S.folderEdit = true; S.folderDraft = S.server.settings.audio_dir; render(); } });
    },
    folderSave: function () {
      api("POST", "/api/settings", { audio_dir: S.folderDraft }).then(function () { S.folderEdit = false; flash(T().folderSaved); refresh(); })
        .catch(function (e) { flash(T().error + e.message); });
    },
    models: function () {
      S.modelsOpen = !S.modelsOpen; S.mAsk = null;
      if (S.modelsOpen) { loadModels(); }
    },
    fixModel: function () { S.aboutOpen = false; S.settingsOpen = true; S.modelsOpen = true; loadModels(); },
    procOne: function (v, id) { noteAction(id, "process"); },
    skipOne: function (v, id) { noteAction(id, "skip"); },
    restoreOne: function (v, id) { noteAction(id, "restore"); },
    stopJob: function () { api("POST", "/api/cancel").then(refresh); },
    mAsk: function (kind, id) { S.mAsk = { kind: kind, id: id }; S.mDel = null; },
    mDel: function (kind, id) { S.mDel = { kind: kind, id: id }; S.mAsk = null; },
    mDelGo: function () {
      var a = S.mDel; S.mDel = null;
      api("POST", "/api/models/remove", { kind: a.kind, id: a.id, confirm: true }).then(function () { return loadModels(); }).then(refresh)
        .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
    },
    mGo: function () {
      var a = S.mAsk; S.mAsk = null;
      api("POST", "/api/models/install", { kind: a.kind, id: a.id, confirm: true }).then(loadModels)
        .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
    },
    mUse: function (kind, id) {
      api("POST", "/api/models/select", { kind: kind, id: id }).then(function () { return loadModels(); }).then(refresh)
        .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
    }
  };

  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-a]");
    if (!el || el.disabled) { return; }
    var fn = A[el.getAttribute("data-a")];
    if (fn) { fn(el.getAttribute("data-v"), el.getAttribute("data-id")); render(); }
  });
  document.addEventListener("input", function (ev) {
    if (ev.target.id === "nameInput") { S.draft = ev.target.value; }
    if (ev.target.id === "folderInput") { S.folderDraft = ev.target.value; }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && ev.target.id === "nameInput") { A.saveName(); }
    if (ev.key === "Enter" && ev.target.id === "folderInput") { A.folderSave(); }
  });

  function loop() {
    refresh().then(function () {
      var busy = S.server && (S.server.job.running || (S.server.download && S.server.download.state === "running"));
      setTimeout(loop, busy ? 1000 : 2500);
    });
  }
  loop();
})();
