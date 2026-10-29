(function () {
  "use strict";

  var D = {
    fr: {
      brand: "Cairn · Pocket AI souverain", components: "Composants",
      updAvail: "Mise à jour disponible : ", updFlash: "Relancez la commande d’installation",
      about: "À propos", aboutTagline: "Pocket AI souverain",
      aboutText: "Importez, transcrivez et résumez vos enregistrements Pocket, entièrement sur cet ordinateur. Aucun compte, aucun cloud, aucune télémétrie.",
      aboutLegal: "v{v} · © 2026 Yanick Imhof · Licence MIT · Non affilié à Pocket.", uiLang: "Langue de l’interface",
      off: "Non", on: "Oui",
      devGpuHint: "Identification des interlocuteurs sur la puce graphique (au moins 4 fois plus rapide, même résultat). Cliquer pour utiliser le processeur.", devCpuHint: "Identification des interlocuteurs sur le processeur. Cliquer pour utiliser la puce graphique.",
      taskWhat: "Action", taskWho: "Qui", taskWhen: "Quand", taskEditHint: "Modifier l'action", taskDelHint: "Supprimer l'action", taskDelAsk: "Supprimer cette action ?",
      tplMine: "Mes modèles de note", tplEditHint: "Créer ou modifier un modèle de note", tplName: "Nom du modèle", tplPrompt: "Ex. : compte rendu client : objectifs, décisions, risques, prochaines étapes", tplStar: "Utiliser pour toutes les nouvelles notes", tplDelAsk: "Supprimer ce modèle ?", tplNone: "Aucun modèle pour l'instant",
      tagHint: "Tags", tagPlaceholder: "Ajouter un tag", tagDismissHint: "Ignorer les suggestions", tagAcceptHint: "Ajouter ce tag", tagRemoveHint: "Retirer ce tag", tagFilterHint: "Filtrer par tag", tagsSuggest: "Suggérer des tags", tagsSuggestHint: "Après chaque note, Cairn propose jusqu'à 3 de vos tags existants, à valider. Un appel de plus au modèle par note.", tagApplied: "{n} notes taguées", pickTagPlaceholder: "#tag",
      find: "Rechercher", findPlaceholder: "Un mot, un nom, un chiffre", findNone: "Aucun résultat", tasks: "Toutes mes actions", tasksNone: "Aucune action pour l'instant", tasksCopy: "Copier les actions à faire", tasksUnassigned: "Sans responsable", tasksCopied: "Actions copiées",
      listenHint: "Écouter à partir d'ici", mailHint: "Écrire le mail de suivi", mailTitle: "Mail de suivi", mailWriting: "Rédaction du mail…", mailCopy: "Copier le mail", mailOpen: "Ouvrir dans l'app Mail", mailRedo: "Réécrire le mail",
      vocab: "Vocabulaire", vocabHint: "Noms de personnes, de lieux et termes rares, un par ligne. Cairn corrige dans la transcription les mots qui leur ressemblent et impose leur orthographe au résumé. « Sion, Cion, Scyon => Acme » remplace toujours chacun par Acme (=>, -> et : fonctionnent). « Science Day => ACME Day | awards, ceremony » ne remplace qu'à côté de ces mots.",
      vocabTodo: "{n} notes utilisent un ancien vocabulaire", vocabAll: "Mettre à jour les notes", vocabChoose: "Choisir des notes", vocabRange: "Mettre à jour une période", vocabStarted: "{n} notes en cours de mise à jour", vocabNothing: "Aucune note à mettre à jour",
      pickCount: "{n} sélectionnée(s)", pickAll: "Tout sélectionner", pickGo: "Mettre à jour les notes choisies", pickCancel: "Annuler", vocabPlaceholder: "Un nom ou un terme par ligne", vocabSaved: "Vocabulaire enregistré", vocabFixes: "Corrections du vocabulaire",
      processedIn: "traité en", notInstalled: "Non installé", getIt: "Installer", refText: "Acheter un Pocket : 10 % de réduction", refNote: "Lien de parrainage facultatif. L’offre dépend uniquement de Pocket et peut changer.",
      models: "Modèles", modelsHint: "Choisir ou ajouter des modèles", modelsSpeech: "Transcription", modelsLlm: "Résumés", modelsDiar: "Identification des interlocuteurs",
      hfToken: "Jeton Hugging Face", hfTokenHint: "Nécessaire une seule fois pour télécharger le modèle de diarisation (gratuit, compte Hugging Face requis ; il faut aussi accepter l'accès au modèle sur huggingface.co). Jamais utilisé ailleurs.",
      hfTokenNone: "Non configuré", hfTokenOn: "Configuré", hfTokenSaved: "Jeton enregistré", hfTokenCleared: "Jeton supprimé", hfTokenInvalid: "Jeton invalide",
      diarizeLabel: "Identifier les interlocuteurs", diarizeHint: "Ajoute qui parle dans le transcript et la note. Nécessite le modèle de diarisation (dans Modèles, ci-dessus). Tourne entièrement en local.",
      diarNeedsToken: "Configurez d'abord un jeton Hugging Face",
      rediarize: "Rediariser", rediarizeHint: "Réidentifier les interlocuteurs sur cette note, sans retoucher le résumé. Reprend l'audio déjà transcrit.",
      rediarizeConfirm: "Réidentifier les interlocuteurs ? Les noms déjà donnés seront perdus.", rediarizeGoing: "Identification des interlocuteurs relancée", rediarizeMissing: "Modèle de diarisation non installé",
      participants: "Interlocuteurs détectés", participantsHint: "Touchez le crayon pour nommer un interlocuteur",
      spkPlaceholder: "Nom de l'interlocuteur", spkSaved: "Nom enregistré", spkNone: "Aucun interlocuteur identifié dans cette transcription.", spkUseRediarize: "Utilisez Rediariser pour les ajouter.",
      tagline: "Votre Pocket. Votre ordinateur. Vos données.", mUse: "Utiliser", mRemove: "Supprimer ce modèle", mRemoveConfirm: "Supprimer {name} de cet ordinateur ? Vous pourrez le télécharger à nouveau.", mInUse: "Utilisé", mInstall: "Installer", mTier: { light: "Léger", standard: "Standard", high: "Élevé" },
      mRam: "{n} Go de mémoire conseillés", mConfirm: "Télécharger {name} ({size}) ? Une connexion internet est utilisée pour ce seul téléchargement.",
      mDownloading: "Téléchargement {pct} %", mFailed: "Échec du téléchargement : ", mDone: "Modèle installé", mDown: "Moteur local arrêté", mBusy: "Un traitement est en cours",
      settings: "Réglages", langHint: "Langue de la note", speechHint: "Langue de l’enregistrement (transcription). Auto : détectée au début du fichier. Appuyez, puis Refaire pour retranscrire", speechAuto: "Auto", mixedHint: "Deux langues repérées : la transcription suit une seule langue, les passages dans l’autre peuvent être imprécis. Choisissez la langue de l’enregistrement, puis Refaire", levelHint: "Niveau de détail",
      short: "Court", mid: "Normal", full: "Complet",
      shortHint: "Court : TL;DR et actions", midHint: "Normal : + contexte et points clés", fullHint: "Complet : + détail par sujet", 
      cancel: "Annuler", confirmLabel: "Confirmer",
      connected: "Pocket connecté", disconnected: "Pocket non détecté", local: "Local", localHint: "Tout reste sur cet ordinateur",
      folder: "Dossier des audios", folderHint: "Dossier de sauvegarde des audios", folderChange: "Changer", folderSaved: "Dossier enregistré", folderType: "Chemin du dossier",
      pocketKey: "Clé de session Pocket", pocketKeyHint: "Optionnel. Avec votre propre clé, Cairn lit aussi le firmware, l'état et le stockage du Pocket, en lecture uniquement.",
      pocketKeyNone: "Non configurée", pocketKeyOn: "Configurée", pocketKeyRejected: "Clé refusée par le Pocket", pocketKeyType: "16 caractères",
      pocketKeySaved: "Clé enregistrée", pocketKeyCleared: "Clé supprimée", pocketKeyInvalid: "La clé doit comporter exactement 16 caractères",
      pocketIdle: "Inactif",
      exportLabel: "Exporter", exportHint: "Copier ou exporter la fiche", copyRich: "Copier", copyRichHint: "Copier, prêt à coller dans un courriel",
      copiedRich: "Copié", expMdHint: "Markdown", expHtmlHint: "HTML", exported: "Exporté en ",
      importLabel: "Importer et transcrire", importHint: "Importer et traiter les enregistrements", count: "Enregistrements sur le Pocket",
      batTip: "Batterie du Pocket : {n} %", batCharging: " · en charge (branché)",
      eyeShow: "Afficher la liste", eyeHide: "Masquer la liste", hiddenNote: "Mode sécurisé",
      rowHint: "Ouvrir", actionsHint: "Afficher les actions", durHint: "Durée", dateDur: "Date · durée · langue", scoreNoteHint: "Fidélité de la note : part des chiffres et des noms de la note retrouvés dans le transcript", scoreNaLang: "Fidélité non mesurable : la note n’est pas dans la langue de l’enregistrement et contient peu de chiffres et de noms. Refaites la note dans la langue de l’enregistrement pour la mesurer", scoreNaFew: "Fidélité non mesurable : la note contient trop peu de chiffres, de noms ou de termes à vérifier", scoreTermsHint: "Fidélité de la note : elle contient peu de chiffres et de noms, la mesure porte sur ses termes clés retrouvés dans le transcript", scoreRawHint: "Confiance de la transcription brute : estimation du moteur vocal, volontairement prudente sur la parole spontanée", rawLegend: "Confiance de la transcription brute",
      rename: "Renommer", saveName: "Enregistrer", viewText: "Voir le transcript", copyText: "Copier le transcript", closeLbl: "Fermer", noText: "Pas de transcript.", textLegend: "Les passages surlignés sont à vérifier.", redo: "Refaire", redoHint: "Refaire la note au niveau choisi. L'audio n'est retranscrit que si le modèle vocal a changé.",
      passages: " à vérifier", tplHint: "Type de note", tpl: { meeting: "Réunion", call: "Appel", presentation: "Présentation", idea: "Idée", other: "Note" },
      deleteLocal: "Supprimer de cet ordinateur", deleteHint: "Supprimer l'enregistrement",
      deleteConfirm: "Supprimer l'audio, le transcript et le résumé, sur le Pocket et sur cet ordinateur ? Irréversible.", deleteConfirmOff: "Supprimer l'audio, le transcript et le résumé sur cet ordinateur ? Le Pocket n'est pas branché : son fichier sera effacé au prochain branchement. Irréversible.", deletedLater: "Supprimé · fichier du Pocket effacé au prochain branchement",
      copied: "Copié", redoing: "Note refaite : ", renamed: "Nom enregistré", deleted: "Supprimé", 
      ready: "Prêt", waiting: "En attente", failed: "Échec : relancer le résumé", done: "Terminé", modelDown: "Moteur local arrêté : relancez Cairn",
      privAuto: "Contrôle automatique", privOk: "aucune connexion vers l’extérieur", privBad: "connexions détectées, voir docs/PRIVACY.md", privNone: "en attente", autoCheck: "Vérifier les mises à jour", autoHint: "Une requête à GitHub par jour", autoProcess: "Traiter automatiquement", autoProcessHint: "Transcrit et résume les enregistrements en attente sans attendre votre clic. Stop met en pause.", autoImport: "Importer au branchement", autoImportHint: "Copie les nouveaux enregistrements dès que le Pocket est branché, sans les traiter", queueTip: "{n} en attente de traitement",
      processNow: "Traiter maintenant", skipIt: "Ignorer", skipped: "Ignoré", putBack: "Remettre dans la file", stopJob: "Arrêter",
      steps: { copying: "Copie depuis le Pocket", transcribing: "Transcription", diarizing: "Identification des interlocuteurs", summarizing: "Rédaction de la note", privacy: "Vérification de la confidentialité" },
      none: "Aucun enregistrement.", tldr: "En bref", actions: "Actions", points: "Points clés", noSpeech: "Aucune parole détectée.",
      months: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."], error: "Erreur : "
    },
    en: {
      brand: "Cairn · Sovereign Pocket AI", components: "Components",
      updAvail: "Update available: ", updFlash: "Run the install command again",
      about: "About", aboutTagline: "Sovereign Pocket AI",
      aboutText: "Import, transcribe and summarize your Pocket recordings, entirely on this computer. No account, no cloud, no telemetry.",
      aboutLegal: "v{v} · © 2026 Yanick Imhof · MIT license · Not affiliated with Pocket.", uiLang: "Interface language",
      off: "Off", on: "On",
      devGpuHint: "Speaker identification runs on the graphics chip (at least 4 times faster, same result). Click to use the processor.", devCpuHint: "Speaker identification runs on the processor. Click to use the graphics chip.",
      taskWhat: "Action", taskWho: "Who", taskWhen: "When", taskEditHint: "Edit the action", taskDelHint: "Delete the action", taskDelAsk: "Delete this action?",
      tplMine: "My note templates", tplEditHint: "Create or edit a note template", tplName: "Template name", tplPrompt: "E.g. client report: goals, decisions, risks, next steps", tplStar: "Use for every new note", tplDelAsk: "Delete this template?", tplNone: "No template yet",
      tagHint: "Tags", tagPlaceholder: "Add a tag", tagDismissHint: "Ignore the suggestions", tagAcceptHint: "Add this tag", tagRemoveHint: "Remove this tag", tagFilterHint: "Filter by tag", tagsSuggest: "Suggest tags", tagsSuggestHint: "After each note, Cairn offers up to 3 of your existing tags, for you to confirm. One more model call per note.", tagApplied: "{n} notes tagged", pickTagPlaceholder: "#tag",
      find: "Search", findPlaceholder: "A word, a name, a number", findNone: "No result", tasks: "All my actions", tasksNone: "No action yet", tasksCopy: "Copy the open actions", tasksUnassigned: "Nobody yet", tasksCopied: "Actions copied",
      listenHint: "Listen from here", mailHint: "Write the follow-up email", mailTitle: "Follow-up email", mailWriting: "Writing the email…", mailCopy: "Copy the email", mailOpen: "Open in the Mail app", mailRedo: "Write it again",
      vocab: "Vocabulary", vocabHint: "Names of people and places and rare terms, one per line. Cairn corrects close variants in the transcript and imposes their spelling on the summary. \"Sion, Cion, Scyon => Acme\" always replaces each of them with Acme (=>, -> and : all work). \"Science Day => ACME Day | awards, ceremony\" replaces only near those words.",
      vocabTodo: "{n} notes use an older vocabulary", vocabAll: "Update the notes", vocabChoose: "Choose notes", vocabRange: "Update a period", vocabStarted: "{n} notes are being updated", vocabNothing: "No note to update",
      pickCount: "{n} selected", pickAll: "Select all", pickGo: "Update the chosen notes", pickCancel: "Cancel", vocabPlaceholder: "One name or term per line", vocabSaved: "Vocabulary saved", vocabFixes: "Vocabulary corrections",
      processedIn: "processed in", notInstalled: "Not installed", getIt: "Install", refText: "Get a Pocket: 10 % off", refNote: "Optional referral link. The offer is set by Pocket alone and may change.",
      models: "Models", modelsHint: "Choose or add models", modelsSpeech: "Transcription", modelsLlm: "Summaries", modelsDiar: "Speaker identification",
      hfToken: "Hugging Face token", hfTokenHint: "Needed once to download the diarization model (free, a Hugging Face account is required, and you must accept access to the model on huggingface.co). Never used anywhere else.",
      hfTokenNone: "Not configured", hfTokenOn: "Configured", hfTokenSaved: "Token saved", hfTokenCleared: "Token removed", hfTokenInvalid: "Invalid token",
      diarizeLabel: "Identify speakers", diarizeHint: "Adds who's speaking to the transcript and the note. Needs the diarization model, in Models above. Runs fully locally.",
      diarNeedsToken: "Set a Hugging Face token first",
      rediarize: "Rediarize", rediarizeHint: "Identify speakers again on this note, without touching the summary. Reuses the transcript already made.",
      rediarizeConfirm: "Identify speakers again? Any names already given will be lost.", rediarizeGoing: "Speaker identification started again", rediarizeMissing: "Diarization model not installed",
      participants: "Speakers detected", participantsHint: "Tap the pencil to name a speaker",
      spkPlaceholder: "Speaker's name", spkSaved: "Name saved", spkNone: "No speaker identified in this transcript.", spkUseRediarize: "Use Rediarize to add them.",
      tagline: "Your Pocket. Your computer. Your data.", mUse: "Use", mRemove: "Remove this model", mRemoveConfirm: "Remove {name} from this computer? You can download it again later.", mInUse: "In use", mInstall: "Install", mTier: { light: "Light", standard: "Standard", high: "High" },
      mRam: "{n} GB of memory advised", mConfirm: "Download {name} ({size})? An internet connection is used for this download only.",
      mDownloading: "Downloading {pct}%", mFailed: "Download failed: ", mDone: "Model installed", mDown: "Local engine stopped", mBusy: "A job is running",
      settings: "Settings", langHint: "Note language", speechHint: "Language of the recording (transcription). Auto: detected at the start of the file. Tap, then Redo to transcribe again", speechAuto: "Auto", mixedHint: "Two languages detected: the transcription follows one language, passages in the other may be inaccurate. Choose the language of the recording, then Redo", levelHint: "Level of detail",
      short: "Short", mid: "Standard", full: "Detailed",
      shortHint: "Short: TL;DR and actions", midHint: "Standard: + context, key points", fullHint: "Detailed: + detail per topic", 
      cancel: "Cancel", confirmLabel: "Confirm",
      connected: "Pocket connected", disconnected: "Pocket not detected", local: "Local", localHint: "Everything stays on this computer",
      folder: "Audio folder", folderHint: "Audio backup folder", folderChange: "Change", folderSaved: "Folder saved", folderType: "Folder path",
      pocketKey: "Pocket session key", pocketKeyHint: "Optional. With your own key, Cairn also reads the Pocket's firmware, state and storage, read only.",
      pocketKeyNone: "Not configured", pocketKeyOn: "Configured", pocketKeyRejected: "Key rejected by the Pocket", pocketKeyType: "16 characters",
      pocketKeySaved: "Key saved", pocketKeyCleared: "Key removed", pocketKeyInvalid: "The key must be exactly 16 characters",
      pocketIdle: "Idle",
      exportLabel: "Export", exportHint: "Copy or export the note", copyRich: "Copy", copyRichHint: "Copy, ready to paste in an email",
      copiedRich: "Copied", expMdHint: "Markdown", expHtmlHint: "HTML", exported: "Exported as ",
      importLabel: "Import and transcribe", importHint: "Import and process the recordings", count: "Recordings on the Pocket",
      batTip: "Pocket battery: {n} %", batCharging: " · charging (plugged in)",
      eyeShow: "Show the list", eyeHide: "Hide the list", hiddenNote: "Secure mode",
      rowHint: "Open", actionsHint: "Show actions", durHint: "Length", dateDur: "Date · length · language", scoreNoteHint: "Note fidelity: share of the note's numbers and names found in the transcript", scoreNaLang: "Fidelity cannot be measured: the note is not in the language of the recording and has few numbers and names. Redo the note in the recording's language to measure it", scoreNaFew: "Fidelity cannot be measured: the note has too few numbers, names or terms to check", scoreTermsHint: "Note fidelity: the note has few numbers and names, so it is measured on its key terms found in the transcript", scoreRawHint: "Raw transcript confidence: the speech engine's own estimate, deliberately cautious on spontaneous speech", rawLegend: "Raw transcript confidence",
      rename: "Rename", saveName: "Save", viewText: "View transcript", copyText: "Copy transcript", closeLbl: "Close", noText: "No transcript.", textLegend: "Highlighted passages are worth checking.", redo: "Redo", redoHint: "Redo the note at the chosen level. The audio is transcribed again only if the speech model has changed.",
      passages: " to check", tplHint: "Note type", tpl: { meeting: "Meeting", call: "Call", presentation: "Presentation", idea: "Idea", other: "Note" },
      deleteLocal: "Delete from this computer", deleteHint: "Delete the recording",
      deleteConfirm: "Delete the audio, transcript and summary, on the Pocket and on this computer? This cannot be undone.", deleteConfirmOff: "Delete the audio, transcript and summary on this computer? The Pocket is not connected: its file will be erased the next time it is connected. This cannot be undone.", deletedLater: "Deleted · the Pocket file will be erased at the next connection",
      copied: "Copied", redoing: "Note redone: ", renamed: "Name saved", deleted: "Deleted", 
      ready: "Ready", waiting: "Waiting", failed: "Failed: rerun the summary", done: "Done", modelDown: "Local engine stopped: restart Cairn",
      privAuto: "Automatic check", privOk: "no connection to the outside", privBad: "connections detected, see docs/PRIVACY.md", privNone: "pending", autoCheck: "Check for updates", autoHint: "One request to GitHub per day", autoProcess: "Process automatically", autoProcessHint: "Transcribes and summarizes waiting recordings without waiting for your click. Stop pauses it.", autoImport: "Import on connect", autoImportHint: "Copies new recordings as soon as the Pocket is connected, without processing them", queueTip: "{n} waiting to be processed",
      processNow: "Process now", skipIt: "Skip", skipped: "Skipped", putBack: "Put back in the queue", stopJob: "Stop",
      steps: { copying: "Copying from the Pocket", transcribing: "Transcribing", diarizing: "Identifying speakers", summarizing: "Writing the note", privacy: "Checking privacy" },
      none: "No recordings.", tldr: "TL;DR", actions: "Actions", points: "Key points", noSpeech: "No speech detected.",
      months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], error: "Error: "
    }
  };

  var I = {
    search: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4 4"></path></svg>',
    tasks: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 6h10"></path><path d="M10 12h10"></path><path d="M10 18h10"></path><path d="m3.5 6 1.5 1.5L7.5 5"></path><path d="m3.5 12 1.5 1.5 2.5-2.5"></path><path d="m3.5 18 1.5 1.5 2.5-2.5"></path></svg>',
    mail: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="13" rx="2.5"></rect><path d="m4.5 8 7.5 5.5L19.5 8"></path></svg>',
    calendar: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="5.5" width="16" height="14.5" rx="3"></rect><path d="M4 10h16"></path><path d="M8.5 3.5v4"></path><path d="M15.5 3.5v4"></path></svg>',
    star: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#B5B5BA" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="m12 3.8 2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.8 6.9 19.5l1-5.7-4.1-4 5.7-.8z"></path></svg>',
    starOn: '<svg width="20" height="20" viewBox="0 0 24 24" fill="#C86D51" stroke="#C86D51" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="m12 3.8 2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.8 6.9 19.5l1-5.7-4.1-4 5.7-.8z"></path></svg>',
    tag: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 12.2V4.5h7.7l9 9a1.8 1.8 0 0 1 0 2.5l-5.2 5.2a1.8 1.8 0 0 1-2.5 0z"></path><circle cx="8" cy="9" r="1.3"></circle></svg>',
    circle: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#B5B5BA" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="8.5"></circle></svg>',
    chip: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"></rect><rect x="9.5" y="9.5" width="5" height="5" rx="1"></rect><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"></path></svg>',
    bolt: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2L4 14h7l-1 8 9-12h-7z"></path></svg>',
    info: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5"></path><path d="M12 8h.01"></path></svg>',
    gear: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h10"></path><path d="M18 7h2"></path><circle cx="16" cy="7" r="2"></circle><path d="M4 17h2"></path><path d="M10 17h10"></path><circle cx="8" cy="17" r="2"></circle></svg>',
    doc: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 3h7l4 4v14H7z"></path><path d="M14 3v4h4"></path><path d="M10 12h5"></path><path d="M10 16h5"></path></svg>',
    folder: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>',
    pencil: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z"></path><path d="m13.5 6.5 4 4"></path></svg>',
    bluetooth: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 6.5l11 11L12 23V1l5.5 5.5L6.5 17.5"></path></svg>',
    hf: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6E6E73" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="13" height="10" rx="3"></rect><rect x="8" y="10" width="13" height="10" rx="3"></rect></svg>',
    okGreen: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="m8 12.5 2.8 2.8L16 9.5"></path></svg>',
    plus: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>',
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
    delConfirm: false, rr: "mid", rl: "en", sp: "auto", server: null, full: {}, about: null, upd: null,
    folderEdit: false, folderDraft: "", wasRunning: false, keyEdit: false, keyDraft: "", hfEdit: false, hfDraft: "", vocabEdit: false, vocabDraft: "", pickMode: false, pick: {}, vFrom: "", vTo: "", vRange: false, taskEdit: null, taskDel: null, tagEdit: null, tagDraft: "", tagFilter: "", pickTag: "", tplOpen: false, tplEdit: null, tplDel: null, findOpen: false, findQ: "", findRes: null, tasksOpen: false, tasks: null
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
  function findNote(id) { return S.server && S.server.notes ? S.server.notes.filter(function (x) { return x.id === id; })[0] : null; }
  function noteLevel(id) { var n = findNote(id); return (n && n.level) || "mid"; }
  function noteLang(id) { var n = findNote(id); return (n && n.lang) || ui(); }
  function noteSpeech(id) { var n = findNote(id); return (n && n.speech_lang) || "auto"; }
  // Language shown on a finished row: the one the engine heard, and the other when the recording mixes two.
  function langTag(n) {
    if (!n.heard) { return ""; }
    var h = String(n.heard).toUpperCase();
    return n.mixed ? h + "+" + (h === "FR" ? "EN" : "FR") : h;
  }
  function lvlIcon(k) { return '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" aria-hidden="true">' + I.lvl[k] + "</svg>"; }
  var LANG_NAME = { fr: "Français", en: "English" };
  function cycleBtn(key, icon, label, hint) {
    return '<button type="button" class="mbtn menu" data-a="cycle" data-v="' + key + '"' + tip(hint) + ">" + icon + (label ? "<span>" + esc(label) + "</span>" : "") + "</button>";
  }
  // One tap changes the choice and moves on to the next one: nothing opens, nothing moves.
  function optionBar(t) {
    return cycleBtn("lvl", lvlIcon(S.rr), "", t.levelHint + " : " + t[S.rr]) + cycleBtn("lang", "", String(S.rl).toUpperCase(), t.langHint + " : " + (LANG_NAME[S.rl] || S.rl)) +
      cycleBtn("sp", I_WAVE, S.sp === "auto" ? t.speechAuto : S.sp.toUpperCase(), t.speechHint + " : " + (S.sp === "auto" ? t.speechAuto : LANG_NAME[S.sp]));
  }
  function exportList(n, t) {
    if (S.exp !== n.id) { return ""; }
    return '<div class="pop-list"><button type="button" class="opt" data-a="expCopy"' + tip(t.copyRichHint) + ">" + I.copy.replace("#FFFFFF", "#1D1D1F") + '</button><button type="button" class="opt" data-a="expMd"' + tip(t.expMdHint) + '><span>MD</span></button><button type="button" class="opt" data-a="expHtml"' + tip(t.expHtmlHint) + "><span>HTML</span></button></div>";
  }
  function segLang(prefix, current, size, t, hint) {
    return '<div class="seg ' + size + '">' + ["fr", "en"].map(function (k) {
      return '<button type="button" class="' + (current === k ? "on" : "") + '" data-a="' + prefix + '" data-v="' + k + '"' + tip(hint) + ">" + k.toUpperCase() + "</button>";
    }).join("") + "</div>";
  }
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

  function confirmBox(text, yes, t) {
    return '<div class="confirm"><div>' + esc(text) + '</div><div class="row gap8">' +
      '<button type="button" class="ib grey2" data-a="cancel"' + tip(t.cancel) + ">" + I.x + "</button>" +
      (yes ? '<button type="button" class="ib red" data-a="' + yes + '"' + tip(t.confirmLabel) + ">" + I.checkW + "</button>" : "") + "</div></div>";
  }

  function gb(bytes) { return bytes < 1e9 ? Math.round(bytes / 1e6) + " MB" : (bytes / 1e9).toFixed(1) + " GB"; }

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
    h += "</div>";
    if (S.mAsk && S.mAsk.kind === kind && S.mAsk.id === m.id) { h += confirmBox(t.mConfirm.replace("{name}", m.label).replace("{size}", gb(m.bytes)), "mGo", t); }
    if (S.mDel && S.mDel.kind === kind && S.mDel.id === m.id) { h += confirmBox(t.mRemoveConfirm.replace("{name}", m.label), "mDelGo", t); }
    return h;
  }

  function batteryIcon(level, charging) {  // the fill follows the level: green from 50 %, orange from 20 %, red below; a bolt while the Pocket is plugged in
    var color = level >= 50 ? "var(--green)" : (level >= 20 ? "var(--orange)" : "var(--red)");
    var svg = '<svg width="28" height="14" viewBox="0 0 28 14" fill="none" aria-hidden="true"><rect x="0.75" y="0.75" width="23.5" height="12.5" rx="3.5" stroke="' + color + '" stroke-width="1.5"></rect>' +
      '<rect x="3" y="3" width="' + Math.max(1.5, 19 * level / 100).toFixed(1) + '" height="8" rx="1.8" fill="' + color + '"></rect><rect x="25.5" y="4.5" width="2" height="5" rx="1" fill="' + color + '"></rect>';
    if (charging) { svg += '<path d="M13.6 2.6 8.9 7.6h3l-1 3.8 4.8-5.2h-3.1z" fill="#fff" stroke="' + color + '" stroke-width="0.9" stroke-linejoin="round"></path>'; }
    return svg + "</svg>";
  }

  function pocketStatusDetails(t, st) {
    var ps = st.pocket_status || {}, d = ps.data || {};
    if (ps.state === "rejected") { return t.pocketKeyRejected; }
    var parts = [];
    if (d.firmware) { parts.push("FW " + d.firmware); }
    if (d.state != null) { parts.push(d.state === 0 ? t.pocketIdle : String(d.state)); }
    if (d.total_kb) { parts.push(Math.round(100 * d.used_kb / d.total_kb) + "%"); }
    return parts.join(" · ");
  }

  function diarRow(m, t, job) {
    var running = job && job.state === "running" && job.kind === "diar" && job.id === m.id;
    var h = '<div class="mrow"><div class="minfo"><div class="mname">' + esc(m.label) + "</div>";
    h += '<div class="small">' + esc(t.mTier[m.tier] + " · " + gb(m.bytes) + " · " + t.mRam.replace("{n}", m.ram)) + "</div></div>";
    if (running) { h += '<span class="small">' + esc(t.mDownloading.replace("{pct}", job.pct)) + "</span>"; }
    else if (m.installed) {
      h += '<button type="button" class="ib" data-a="mDel" data-v="diar" data-id="' + esc(m.id) + '"' + tip(t.mRemove) + ">" + I.trash + "</button>";
    } else {
      h += '<button type="button" class="mbtn" data-a="mAsk" data-v="diar" data-id="' + esc(m.id) + '"' + (job && job.state === "running" ? " disabled" : "") + ">" + esc(t.mInstall) + "</button>";
    }
    h += "</div>";
    if (S.mAsk && S.mAsk.kind === "diar" && S.mAsk.id === m.id) { h += confirmBox(t.mConfirm.replace("{name}", m.label).replace("{size}", gb(m.bytes)), "mGo", t); }
    if (S.mDel && S.mDel.kind === "diar" && S.mDel.id === m.id) { h += confirmBox(t.mRemoveConfirm.replace("{name}", m.label), "mDelGo", t); }
    return h;
  }

  function viewModels(t) {
    var M = S.models;
    if (!M) { return ""; }
    var h = '<div class="hr"></div><div class="mlist"><div class="mgroup">' + esc(t.modelsSpeech) + "</div>";
    M.speech.forEach(function (m) { h += modelRow("speech", m, t, M.job); });
    h += '<div class="mgroup">' + esc(t.modelsLlm) + "</div>";
    M.llm.forEach(function (m) { h += modelRow("llm", m, t, M.job); });
    if (M.diar) {
      h += '<div class="mgroup">' + esc(t.modelsDiar) + "</div>";
      M.diar.forEach(function (m) { h += diarRow(m, t, M.job); });
    }
    if (M.job && M.job.state === "error") { h += '<div class="small" style="color:#C0392B">' + esc(t.mFailed + M.job.error) + "</div>"; }
    return h + "</div>";
  }

  function viewSettings(t, st) {
    var h = '<div class="card panel">';
    h += '<div class="setrow"' + tip(t.autoHint) + '><span class="text" style="font-size:14px">' + esc(t.autoCheck) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="autocheck" data-v="' + o[0] + '" class="' + bg(st.settings.autocheck !== false === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.autoImportHint) + '><span class="text" style="font-size:14px">' + esc(t.autoImport) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="autoimport" data-v="' + o[0] + '" class="' + bg(st.settings.autoimport !== false === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.autoProcessHint) + '><span class="text" style="font-size:14px">' + esc(t.autoProcess) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="autoprocess" data-v="' + o[0] + '" class="' + bg((st.settings.autoprocess === true) === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    var terms = st.settings.vocabulary || [];
    h += '<div class="hr"></div><div class="setrow"' + tip(t.vocabHint) + '><span class="text" style="font-size:14px">' + esc(t.vocab) + (terms.length ? " · " + terms.length : "") +
      '</span><button type="button" class="ib" data-a="vocabAsk"' + tip(t.vocabHint) + ">" + (terms.length ? I.pencil : I.plus) + "</button></div>";
    if (S.vocabEdit) {
      h += '<div class="name" style="margin:0 0 6px;align-items:flex-start"><textarea id="vocabInput" rows="5" placeholder="' + esc(t.vocabPlaceholder) + '" aria-label="' + esc(t.vocab) + '">' + esc(S.vocabDraft) +
        '</textarea><button type="button" class="ib blue" data-a="vocabSave"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
    }
    if (!S.vocabEdit && terms.length) {
      var todo = (st.totals && st.totals.vocab_todo) || 0;
      h += '<div class="vtools"><span class="small">' + (todo > 0 ? esc(t.vocabTodo.replace("{n}", todo)) : "") + "</span>" +
        '<button type="button" class="ib sm' + (todo > 0 ? " blue" : "") + '" data-a="vocabAll"' + (todo > 0 ? "" : " disabled") + tip(t.vocabAll) + ">" + (todo > 0 ? I.refreshW : I.refresh) + "</button>" +
        '<button type="button" class="ib sm" data-a="pickStart"' + tip(t.vocabChoose) + ">" + I.tasks + "</button>" +
        '<button type="button" class="ib sm' + bg(S.vRange) + '" data-a="vocabRangeToggle"' + tip(t.vocabRange) + ">" + I.calendar + "</button></div>";
      if (S.vRange) {
        h += '<div class="vtools range"><input id="vFrom" type="date" class="dinput" value="' + esc(S.vFrom) + '" aria-label="' + esc(t.vocabRange) + '"><span class="small">\u2192</span><input id="vTo" type="date" class="dinput" value="' + esc(S.vTo) +
          '" aria-label="' + esc(t.vocabRange) + '"><button type="button" class="ib sm blue" data-a="vocabRange"' + tip(t.vocabRange) + ">" + I.checkW + "</button></div>";
      }
    }
    var tpls = st.settings.templates || [];
    h += '<div class="hr"></div><div class="setrow"' + tip(t.tplEditHint) + '><span class="text" style="font-size:14px">' + esc(t.tplMine) + (tpls.length ? " \u00b7 " + tpls.length : "") +
      '</span><button type="button" class="ib" data-a="tplAsk"' + tip(t.tplEditHint) + ">" + (S.tplOpen ? I.x : (tpls.length ? I.pencil : I.plus)) + "</button></div>";
    if (S.tplOpen) { h += viewTemplates(t, st); }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.tagsSuggestHint) + '><span class="text" style="font-size:14px">' + esc(t.tagsSuggest) + '</span><div class="seg s38">' +
      [["0", t.off, false], ["1", t.on, true]].map(function (o) {
        return '<button type="button" data-a="tagsSuggest" data-v="' + o[0] + '" class="' + bg((st.settings.tags_suggest === true) === o[2]).trim() + '">' + esc(o[1]) + "</button>";
      }).join("") + "</div></div>";
    h += '<div class="hr"></div><div class="setrow"' + tip(t.hfTokenHint) + ">" + I.hf;
    if (st.settings.hf_token) {
      var gpu = (st.settings.diarize_device || "auto") !== "cpu";
      var devBtn = st.settings.diarize && S.server && S.server.gpu && S.server.diar_installed
        ? '<button type="button" class="devbtn' + (gpu ? " gpu" : "") + '" data-a="diarizeDevice" data-v="' + (gpu ? "cpu" : "auto") + '"' + tip(gpu ? t.devGpuHint : t.devCpuHint) + ">" +
          (gpu ? I.bolt : I.chip) + (gpu ? "GPU" : "CPU") + "</button>" : "";
      h += '<span class="row gap8">' + devBtn + '<button type="button" class="ib" data-a="hfAsk"' + tip(t.hfTokenOn) + ">" + I.pencil + '</button><div class="seg s38"' + tip(t.diarizeHint) + ">" +
        [["0", t.off, false], ["1", t.on, true]].map(function (o) {
          return '<button type="button" data-a="diarize" data-v="' + o[0] + '" class="' + bg(!!st.settings.diarize === o[2]).trim() + '">' + esc(o[1]) + "</button>";
        }).join("") + "</div></span></div>";
    } else {
      h += '<button type="button" class="ib" data-a="hfAsk"' + tip(t.hfTokenNone) + ">" + I.plus + "</button></div>";
    }
    if (S.hfEdit) {
      h += '<div class="name" style="margin:0 0 6px"><input id="hfInput" type="text" value="' + esc(S.hfDraft) + '" placeholder="hf_…" aria-label="' + esc(t.hfToken) + '">' +
        '<button type="button" class="ib blue" data-a="hfSave"' + tip(t.saveName) + ">" + I.checkW + "</button>" +
        (st.settings.hf_token ? '<button type="button" class="ib" data-a="hfClear"' + tip(t.hfTokenCleared) + ">" + I.trash + "</button>" : "") + "</div>";
    }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.pocketKeyHint) + ">" + I.bluetooth;
    if (st.settings.pocket_key) {
      var keyWarn = (st.pocket_status || {}).state === "rejected";
      h += '<button type="button" class="ib" data-a="keyAsk"' + tip(keyWarn ? t.pocketKeyRejected : t.pocketKeyOn) + ">" + (keyWarn ? I.warnB : I.okGreen) + "</button></div>";
    } else {
      h += '<button type="button" class="ib" data-a="keyAsk"' + tip(t.pocketKeyNone) + '>' + I.plus + "</button></div>";
    }
    if (S.keyEdit) {
      h += '<div class="name" style="margin:0 0 6px"><input id="keyInput" type="text" value="' + esc(S.keyDraft) + '" placeholder="' + esc(t.pocketKeyType) + '" aria-label="' + esc(t.pocketKey) + '">' +
        '<button type="button" class="ib blue" data-a="keySave"' + tip(t.saveName) + ">" + I.checkW + "</button>" +
        (st.settings.pocket_key ? '<button type="button" class="ib" data-a="keyClear"' + tip(t.pocketKeyCleared) + ">" + I.trash + "</button>" : "") + "</div>";
    }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.folderHint) + ">" + I.folder;
    h += '<div class="row gap8" style="min-width:0"><span class="text" style="font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(shortPath(st.settings.audio_dir)) + "</span>";
    h += '<button type="button" class="ib" data-a="folder"' + tip(t.folderChange) + ">" + I.pencil + "</button></div></div>";
    if (S.folderEdit) {
      h += '<div class="name" style="margin:0 0 14px"><input id="folderInput" type="text" value="' + esc(S.folderDraft) + '" placeholder="' + esc(t.folderType) + '" aria-label="' + esc(t.folderType) + '">' +
        '<button type="button" class="ib blue" data-a="folderSave"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
    }
    h += '<div class="hr"></div><div class="setrow"' + tip(t.modelsHint) + "><span class=\"text\" style=\"font-size:14px\">" + esc(t.models) + '</span><button type="button" class="mbtn" data-a="models">' + esc(S.modelsOpen ? "−" : "+") + "</button></div>";
    if (S.modelsOpen) { h += viewModels(t); }
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

  // Closed row: fidelity of the finished note (colored), the speech engine's confidence in the raw
  // transcript (neutral), and the passages worth checking (only when there are some).
  var I_NOTE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  var I_WAVE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></svg>';
  var I_WARN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4 3 20h18z"/><path d="M12 10v4"/><path d="M12 17h.01"/></svg>';

  function scorePills(n, t) {
    var h = "";
    if (n.fidelity != null) {
      var tone = n.fidelity >= 90 ? "g" : n.fidelity >= 75 ? "a" : "r";
      h += '<span class="pl ' + tone + '"' + tip((n.fidelity_basis === "terms" ? t.scoreTermsHint : t.scoreNoteHint) + " : " + n.fidelity + " %") + ">" + I_NOTE + n.fidelity + "</span>";
    }
    else if (n.done && n.fidelity_basis) {
      h += '<span class="pl n"' + tip(n.fidelity_basis === "language" ? t.scoreNaLang : t.scoreNaFew) + ">" + I_NOTE + "–</span>";
    }
    if (n.quality != null) { h += '<span class="pl n"' + tip(t.scoreRawHint + " : " + n.quality + " %") + ">" + I_WAVE + n.quality + "</span>"; }
    if (n.passages) { h += '<span class="pl a"' + tip(n.passages + t.passages) + ">" + I_WARN + n.passages + "</span>"; }
    return h ? '<span class="pls">' + h + "</span>" : "";
  }

  var TPL = ["meeting", "call", "presentation", "idea", "other"];
  var TPL_ICON = {
    meeting: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M17 14c2.5 0 4.5 2 4.5 5"/>',
    call: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    presentation: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M12 16v4M8 20h8"/>',
    idea: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    other: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>'
  };
  TPL_ICON.custom = '<path d="m12 3.5 2.3 5.4 5.7.9-4.2 4 1 5.7-4.8-2.8-4.8 2.8 1-5.7-4.2-4 5.7-.9z"/>';
  function myTemplates() { return (S.server && S.server.settings && S.server.settings.templates) || []; }
  function noteTpl(full) { var k = full && full.summary && full.summary.template; return TPL.indexOf(k) >= 0 ? k : "other"; }
  function noteTplKey(full) {  // a built-in type, or the id of one of the person's own templates
    var c = full && full.summary && full.summary.custom;
    return c && myTemplates().some(function (x) { return x.id === c; }) ? c : noteTpl(full);
  }
  function tplButton(full, t) {
    if (!full || !full.summary) { return ""; }
    var k = noteTplKey(full), mine = myTemplates().filter(function (x) { return x.id === k; })[0];
    return '<button type="button" class="ib" data-a="cycleTpl"' + tip(t.tplHint + " : " + (mine ? mine.name : t.tpl[k])) + '><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1D1D1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (mine ? TPL_ICON.custom : TPL_ICON[k]) + "</svg></button>";
  }

  function viewDetail(n, t) {
    var full = S.full[n.id];
    var h = '<div class="detail">';
    if (S.edit === n.id) {
      h += '<div class="name"><input id="nameInput" type="text" value="' + esc(S.draft) + '" aria-label="' + esc(t.rename) + '"><button type="button" class="ib blue" data-a="saveName"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
    }
    var jobBusy = S.server && S.server.job && S.server.job.running;
    var canRediarize = n.status === "done" && S.server && S.server.diar_installed;
    h += '<div class="bar"><div class="row gap8" style="flex-wrap:wrap">' + optionBar(t);
    if (canRediarize) {
      h += '<button type="button" class="ib outline" data-a="askRediarize" data-id="' + esc(n.id) + '"' + (jobBusy ? " disabled" : "") + tip(t.rediarizeHint) + '><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3368A0" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="9" cy="8" r="2.6"></circle><path d="M3.5 19c0-2.9 2.4-5.2 5.5-5.2"></path><circle cx="17" cy="8" r="2.2"></circle><path d="M12.8 13.6c2.7.1 4.7 2.3 4.7 5.2"></path><path d="M19.5 10.5a3.2 3.2 0 1 0-.9 2.3"></path><path d="M19.5 7.3v3h-3"></path></svg></button>';
    }
    h += '<button type="button" class="ib blue" data-a="rerun"' + (jobBusy ? " disabled" : "") + tip(t.redoHint) + ">" + I.refreshW + "</button></div>";
    h += '<div class="row" style="gap:4px">' + tplButton(full, t);
    h += '<button type="button" class="ib" data-a="viewText" data-id="' + esc(n.id) + '"' + tip(t.viewText) + ">" + I.doc.replace("#6E6E73", "#1D1D1F") + "</button>";
    h += '<button type="button" class="ib' + (S.tagEdit === n.id ? " on" : "") + '" data-a="tagToggle" data-id="' + esc(n.id) + '"' + tip(t.tagHint) + ">" + I.tag + "</button>";
    h += '<button type="button" class="ib" data-a="mailOpen" data-id="' + esc(n.id) + '"' + tip(t.mailHint) + ">" + I.mail + "</button>";
    h += '<button type="button" class="ib" data-a="startRename"' + tip(t.rename) + ">" + I.pencil + "</button>";
    h += '<span class="pop"><button type="button" class="ib' + (S.exp === n.id ? " on" : "") + '" data-a="toggleExport"' + tip(t.exportHint) + ">" + I.down + "</button>" + exportList(n, t) + "</span>";
    h += '<button type="button" class="ib" data-a="askDelete"' + tip(t.deleteHint) + ">" + I.trash + "</button></div></div>";
    h += tagPanel(n, t);
    if (S.rediarConfirm === n.id) { h += confirmBox(t.rediarizeConfirm, "rediarizeGo", t); }
    if (S.delConfirm) { h += confirmBox(S.server && S.server.pocket && S.server.pocket.connected ? t.deleteConfirm : t.deleteConfirmOff, "confirmDelete", t); }
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
      (s.sections || []).forEach(function (x) {
        h += "<div><b>" + esc(x.heading) + "</b><div>" + esc(x.text) + "</div></div>";
      });
      var info = [];
      if (full.models && full.models.speech) { info.push(full.models.speech); }
      if (full.models && full.models.llm) { info.push(full.models.llm); }
      if (full.elapsed) { info.push(t.processedIn + " " + fmtDur(full.elapsed)); }
      if (info.length) { h += '<div class="small" style="margin-top:10px">' + esc(info.join(" · ")) + "</div>"; }
      var vf = full.vocab_fixes || [];
      if (vf.length) {
        h += '<div class="small" style="margin-top:6px">' + esc(t.vocabFixes + " : " + vf.map(function (f) { return f.from + " \u2192 " + f.to + (f.count > 1 ? " \u00d7" + f.count : ""); }).join(", ")) + "</div>";
      }
      h += "</div>";
    }
    return h + "</div>";
  }

  function queueActions(n, job, t) {
    var h = '<div class="detail"><div class="row gap8" style="flex-wrap:wrap">' + optionBar(t);
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
    var notes = (st.notes || []).filter(function (n) {
      return !S.tagFilter || tagsOf(n).some(function (x) { return x.toLowerCase() === S.tagFilter.toLowerCase(); });
    });
    if (!notes.length) { return '<div class="card" style="padding:22px;text-align:center"><span class="small">' + esc(t.none) + "</span></div>"; }
    return '<div class="list">' + notes.map(function (n) {
      var done = n.status === "done", running = st.job.running && st.job.id === n.id;
      var main = done ? n.title : fmtDate(n.date) || n.id;
      var sub = done ? [fmtDate(n.date), fmtDur(n.duration), langTag(n)].filter(Boolean).join(" · ") : (running ? stepText(st.job, t) : (n.status === "skipped" ? t.skipped + " · " : "") + fmtDur(n.duration));
      var open = S.open === n.id;
      var rowTip = running ? stepText(st.job, t) : (done || n.status === "error" ? t.rowHint : t.actionsHint);
      var subTip = done ? (n.mixed ? t.mixedHint : t.dateDur) : (running ? "" : t.durHint);
      var bar = running ? (st.job.pct != null ? '<span class="pbar"><span style="width:' + st.job.pct + '%"></span></span>' : (st.job.step ? '<span class="pbar ind"><span></span></span>' : "")) : "";
      var picking = S.pickMode;
      return '<div class="item"><button type="button" class="rowbtn" data-a="' + (picking ? "pickTog" : "row") + '" data-id="' + esc(n.id) + '" aria-expanded="' + open + '"' + tip(rowTip) + '><span class="st">' + (picking && done ? (S.pick[n.id] ? I.done : I.circle) : statusIcon(n, st.job)) +
        '</span><span class="mid"><span class="main">' + esc(main) + '</span><span class="sub"' + tip(subTip) + ">" + esc(sub) + "</span>" +
        (tagsOf(n).length || (n.tag_suggestions || []).length ? '<span class="tagline">' + tagsOf(n).map(function (x) { return "#" + esc(x); }).join(" ") +
          ((n.tag_suggestions || []).length ? ' <span class="sug">' + (n.tag_suggestions || []).map(function (x) { return "+#" + esc(x); }).join(" ") + "</span>" : "") + "</span>" : "") + bar + "</span>" + (done ? scorePills(n, t) : "") + "</button>" +
        (open && !picking && (done || n.status === "error") ? viewDetail(n, t) : "") +
        (open && !picking && !done ? queueActions(n, st.job, t) : "") + "</div>";
    }).join("") + "</div>";
  }

  function fmtStamp(sec) {
    sec = Math.max(0, Math.round(sec));
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), r = sec % 60, pad = function (n) { return (n < 10 ? "0" : "") + n; };
    return (h ? h + ":" + pad(m) : m) + ":" + pad(r);
  }
  function stampSeconds(stamp) {
    var p = String(stamp).split(":").map(Number), n = 0;
    p.forEach(function (x) { n = n * 60 + x; });
    return n;
  }
  function markedHtml(parts) {
    return (parts || []).map(function (p) { return p.m ? "<mark>" + esc(p.t) + "</mark>" : esc(p.t); }).join("");
  }
  function runFind() {
    var q = S.findQ.trim();
    if (!q) { S.findRes = null; render(); return; }
    api("GET", "/api/search?q=" + encodeURIComponent(q)).then(function (r) {
      if (q === S.findQ.trim()) { S.findRes = r.results || []; render(); }
    }).catch(function () { /* the next keystroke searches again */ });
  }
  function loadTasks() {
    return api("GET", "/api/actions").then(function (r) { S.tasks = r.actions || []; render(); }).catch(function () { /* keep what is shown */ });
  }
  function viewFind(t) {
    if (S.hidden) { return veil(t); }
    var h = '<div class="card panel"><div class="name" style="margin:14px 0 8px"><input id="findInput" type="search" autocomplete="off" placeholder="' + esc(t.findPlaceholder) + '" aria-label="' + esc(t.find) + '" value="' + esc(S.findQ) + '"></div>';
    var res = S.findRes;
    if (res && !res.length) { h += '<div class="small" style="padding:6px 2px 16px">' + esc(t.findNone) + "</div>"; }
    (res || []).forEach(function (r) {
      h += '<div class="fres"><button type="button" class="fhead" data-a="findGo" data-id="' + esc(r.id) + '"><span class="main">' + esc(r.title) + '</span><span class="sub">' + esc(fmtDate(r.date)) + "</span></button>";
      r.hits.forEach(function (x) {
        h += '<button type="button" class="fhit" data-a="findGo" data-id="' + esc(r.id) + '" data-v="' + (x.where === "transcript" && x.start != null ? x.start : "") + '">' +
          (x.where === "transcript" && x.start != null ? '<span class="ts">' + fmtStamp(x.start) + "</span>" : "") + markedHtml(x.parts) + "</button>";
      });
      h += "</div>";
    });
    return h + "</div>";
  }
  function viewTemplates(t, st) {
    var list = st.settings.templates || [], dflt = st.settings.template_default || "", ed = S.tplEdit, h = '<div class="tpls">';
    list.forEach(function (x, i) {
      if (ed && ed.idx === i) { return; }
      h += '<div class="trow"><button type="button" class="tick" data-a="tplStar" data-v="' + i + '"' + tip(t.tplStar) + ' aria-pressed="' + (x.id === dflt) + '">' + (x.id === dflt ? I.starOn : I.star) + '</button><button type="button" class="tmid tbtn" data-a="tplEdit" data-v="' + i + '"' +
        tip(x.prompt) + '><span class="text">' + esc(x.name) + '</span></button><button type="button" class="ib sm plain" data-a="tplDelAsk" data-v="' + i + '"' + tip(t.taskDelHint) + ">" + I.trash + "</button></div>";
      if (S.tplDel === i) {
        h += '<div class="row gap8 tconfirm"><span class="small" style="margin-right:auto">' + esc(t.tplDelAsk) + '</span><button type="button" class="ib sm" data-a="tplDelNo"' + tip(t.pickCancel) + ">" + I.x + '</button><button type="button" class="ib sm red" data-a="tplDelGo"' + tip(t.taskDelHint) + ">" + I.checkW + "</button></div>";
      }
    });
    if (ed) {
      h += '<div class="tedit"><input id="tplName" type="text" maxlength="40" value="' + esc(ed.name) + '" placeholder="' + esc(t.tplName) + '" aria-label="' + esc(t.tplName) + '"><textarea id="tplPrompt" rows="4" maxlength="800" placeholder="' + esc(t.tplPrompt) + '" aria-label="' + esc(t.tplPrompt) + '">' + esc(ed.prompt) +
        '</textarea><div class="row gap8" style="justify-content:flex-end"><button type="button" class="ib sm" data-a="tplCancel"' + tip(t.pickCancel) + ">" + I.x + '</button><button type="button" class="ib sm blue" data-a="tplSave"' + tip(t.saveName) + ">" + I.checkW + "</button></div></div>";
    } else {
      h += '<div class="row" style="justify-content:flex-end;padding:4px 0 10px"><span class="small" style="margin-right:auto">' + (list.length ? "" : esc(t.tplNone)) + '</span><button type="button" class="ib sm" data-a="tplNew"' + tip(t.tplEditHint) + ">" + I.plus + "</button></div>";
    }
    return h + "</div>";
  }

  function tagsOf(n) { return (n && n.tags) || []; }
  function allTags() {
    var count = {}, shown = {};
    ((S.server && S.server.notes) || []).forEach(function (n) {
      tagsOf(n).forEach(function (x) { var k = x.toLowerCase(); count[k] = (count[k] || 0) + 1; shown[k] = shown[k] || x; });
    });
    return Object.keys(count).sort(function (a, b) { return count[b] - count[a] || a.localeCompare(b); }).map(function (k) { return { tag: shown[k], count: count[k] }; });
  }
  function viewTagFilter(t) {
    var list = allTags();
    if (!list.length) { return ""; }
    return '<div class="tagbar">' + list.slice(0, 14).map(function (x) {
      return '<button type="button" class="tg' + (S.tagFilter.toLowerCase() === x.tag.toLowerCase() ? " on" : "") + '" data-a="tagFilter" data-v="' + esc(x.tag) + '"' + tip(t.tagFilterHint) + ">#" + esc(x.tag) + "</button>";
    }).join("") + "</div>";
  }
  function tagPanel(n, t) {
    var mine = tagsOf(n), sugg = n.tag_suggestions || [], editing = S.tagEdit === n.id;
    if (!mine.length && !sugg.length && !editing) { return ""; }
    var h = '<div class="tagpanel"><div class="tagbar">';
    mine.forEach(function (x) { h += '<span class="tg on">#' + esc(x) + '<button type="button" class="tgx" data-a="tagRemove" data-v="' + esc(x) + '"' + tip(t.tagRemoveHint) + ">\u00d7</button></span>"; });
    sugg.forEach(function (x) { h += '<button type="button" class="tg dash" data-a="tagAccept" data-v="' + esc(x) + '"' + tip(t.tagAcceptHint) + ">+ #" + esc(x) + "</button>"; });
    if (sugg.length) { h += '<button type="button" class="tgx" data-a="tagDismiss"' + tip(t.tagDismissHint) + ">" + I.x.replace('width="20" height="20"', 'width="14" height="14"') + "</button>"; }
    h += "</div>";
    if (editing) {
      var have = mine.map(function (x) { return x.toLowerCase(); });
      var quick = allTags().filter(function (x) { return have.indexOf(x.tag.toLowerCase()) < 0 && (!S.tagDraft || x.tag.toLowerCase().indexOf(S.tagDraft.toLowerCase()) >= 0); }).slice(0, 8);
      h += '<div class="name" style="margin-top:8px"><input id="tagInput" type="text" maxlength="30" autocomplete="off" placeholder="' + esc(t.tagPlaceholder) + '" aria-label="' + esc(t.tagPlaceholder) + '" value="' + esc(S.tagDraft) +
        '"><button type="button" class="ib blue" data-a="tagAdd"' + tip(t.tagAcceptHint) + ">" + I.checkW + "</button></div>";
      if (quick.length) {
        h += '<div class="tagbar" style="margin-top:8px">' + quick.map(function (x) { return '<button type="button" class="tg" data-a="tagPick" data-v="' + esc(x.tag) + '">#' + esc(x.tag) + "</button>"; }).join("") + "</div>";
      }
    }
    return h + "</div>";
  }
  function veil(t) { return '<div class="list veil">' + I.eyeOff + "<span>" + esc(t.hiddenNote) + "</span></div>"; }
  function viewTasks(t) {
    if (S.hidden) { return veil(t); }
    var list = S.tasks || [];
    if (!list.length) { return '<div class="card panel"><div class="small" style="padding:18px 0">' + esc(S.tasks ? t.tasksNone : "…") + "</div></div>"; }
    var groups = {}, order = [];
    list.forEach(function (a, i) {
      var who = a.who || "";
      if (!groups[who]) { groups[who] = []; order.push(who); }
      groups[who].push({ a: a, i: i });
    });
    order.sort(function (x, y) { return x === "" ? 1 : y === "" ? -1 : x.localeCompare(y); });
    var h = '<div class="card panel"><div class="row between" style="padding:10px 0 2px"><span class="small">' + list.filter(function (a) { return !a.done; }).length + " / " + list.length +
      '</span><button type="button" class="ib" data-a="tasksCopy"' + tip(t.tasksCopy) + ">" + I.copy.replace("#FFFFFF", "#1D1D1F") + "</button></div>";
    order.forEach(function (who) {
      h += '<div class="tgroup">' + esc(who || t.tasksUnassigned) + "</div>";
      groups[who].sort(function (x, y) { return (x.a.done ? 1 : 0) - (y.a.done ? 1 : 0); }).forEach(function (e) {
        var a = e.a, ed = S.taskEdit && S.taskEdit.i === e.i ? S.taskEdit : null;
        if (ed) {
          h += '<div class="tedit"><input id="tkWhat" type="text" value="' + esc(ed.what) + '" placeholder="' + esc(t.taskWhat) + '" aria-label="' + esc(t.taskWhat) + '"><div class="row gap8"><input id="tkWho" type="text" value="' + esc(ed.who) + '" placeholder="' + esc(t.taskWho) +
            '" aria-label="' + esc(t.taskWho) + '"><input id="tkWhen" type="text" value="' + esc(ed.when) + '" placeholder="' + esc(t.taskWhen) + '" aria-label="' + esc(t.taskWhen) + '"></div><div class="row gap8" style="justify-content:flex-end"><button type="button" class="ib sm" data-a="taskCancel"' + tip(t.pickCancel) + ">" + I.x +
            '</button><button type="button" class="ib sm blue" data-a="taskSave"' + tip(t.saveName) + ">" + I.checkW + "</button></div></div>";
          return;
        }
        h += '<div class="trow"><button type="button" class="tick" data-a="tick" data-v="' + e.i + '" aria-pressed="' + a.done + '">' + (a.done ? I.done : I.circle) + '</button><button type="button" class="tmid tbtn" data-a="taskEdit" data-v="' + e.i + '"' + tip(t.taskEditHint) + '><span class="text' + (a.done ? " tdone" : "") + '">' +
          esc(a.what + (a.when ? " \u00b7 " + a.when : "")) + '</span><span class="small">' + esc((a.title || "") + " \u00b7 " + fmtDate(a.date)) + "</span></button>" +
          '<button type="button" class="ib sm plain" data-a="taskDel" data-v="' + e.i + '"' + tip(t.taskDelHint) + ">" + I.trash + "</button></div>";
        if (S.taskDel === e.i) {
          h += '<div class="row gap8 tconfirm"><span class="small" style="margin-right:auto">' + esc(t.taskDelAsk) + '</span><button type="button" class="ib sm" data-a="taskDelNo"' + tip(t.pickCancel) + ">" + I.x + '</button><button type="button" class="ib sm red" data-a="taskDelGo"' + tip(t.taskDelHint) + ">" + I.checkW + "</button></div>";
        }
      });
    });
    return h + "</div>";
  }

  function noteRow(id) { return ((S.server && S.server.notes) || []).filter(function (x) { return x.id === id; })[0]; }
  function setNoteTags(id, list) {
    api("POST", "/api/note/" + encodeURIComponent(id) + "/tags", { tags: list }).then(refresh).catch(function (e) { flash(T().error + e.message); });
  }
  function applyVocab(body) {
    api("POST", "/api/vocabulary/apply", body).then(function (r) {
      flash(r.count ? T().vocabStarted.replace("{n}", r.count) : T().vocabNothing);
      refresh();
    }).catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
  }

  function showMail(id, redo) {
    var t = T();
    closeText();
    var box = document.createElement("div");
    box.id = "txtview";
    var draw = function (inner, draft) {
      box.innerHTML = '<div class="mback" data-tx="close"></div><div class="mcard" role="dialog" aria-modal="true" aria-label="' + esc(t.mailTitle) + '"><div class="mhead"><div class="mtitle">' + esc(t.mailTitle) + '</div><div class="row gap8">' +
        (draft ? '<button type="button" class="ib" data-tx="mcopy"' + tip(t.mailCopy) + ">" + I.copy.replace("#FFFFFF", "#1D1D1F") + "</button>" +
          '<a class="ib" data-tx="mopen" href="mailto:?subject=' + encodeURIComponent(draft.subject) + "&body=" + encodeURIComponent(draft.body) + '"' + tip(t.mailOpen) + ">" + I.mail + "</a>" +
          '<button type="button" class="ib" data-tx="mredo"' + tip(t.mailRedo) + ">" + I.refresh + "</button>" : "") +
        '<button type="button" class="ib grey2" data-tx="close"' + tip(t.closeLbl) + ">" + I.x + '</button></div></div><div class="mbody">' + inner + "</div></div>";
    };
    draw('<p class="small">' + esc(t.mailWriting) + "</p>", null);
    box.addEventListener("click", function (ev) {
      var el = ev.target.closest("[data-tx]");
      if (!el) { return; }
      var tx = el.getAttribute("data-tx");
      if (tx === "close") { closeText(); }
      else if (tx === "mredo") { showMail(id, true); }
      else if (tx === "mcopy") { navigator.clipboard.writeText(box.getAttribute("data-copy") || "").then(function () { flash(T().copied); }); }
    });
    document.body.appendChild(box);
    document.body.style.overflow = "hidden";
    api("POST", "/api/note/" + encodeURIComponent(id) + "/followup", redo ? { redo: true } : {}).then(function (d) {
      box.setAttribute("data-copy", d.subject + "\n\n" + d.body);
      draw('<p><b>' + esc(d.subject) + '</b></p><div class="mail">' + esc(d.body) + "</div>", d);
    }).catch(function (e) { draw('<p class="small">' + esc(t.error + e.message) + "</p>", null); });
  }

  function view() {
    var st = S.server;
    if (!st) { return ""; }
    var t = T(), job = st.job, ring = 0;
    if (job.running && job.total) {
      var part = job.pct != null ? job.pct / 100 : 0.5;  // transcription fills the first part of a recording, diarizing a thin slice, the note the rest
      if (job.step === "transcribing") { part = (job.pct || 0) / 100 * 0.55; } else if (job.step === "diarizing") { part = 0.6; } else if (job.step === "summarizing") { part = 0.65 + 0.35 * part; }
      ring = Math.min(1, (job.done + part) / job.total);
    }
    else if (st.totals.notes) { ring = st.totals.done / st.totals.notes; }
    var connected = st.pocket.connected;
    var canImport = !job.running && (connected || st.totals.waiting > 0);
    var h = '<main class="wrap"><div class="head"><div class="row gap12"><div class="bw"><h1 class="brand"' + tip(t.brand) + '>Cairn</h1><div class="sub">' + esc(t.aboutTagline) + "</div></div>";
    var dotTip = connected ? t.connected : t.disconnected;
    if (st.settings.pocket_key) {
      var pd = pocketStatusDetails(t, st);
      if (pd) { dotTip += " · " + pd; }
    }
    h += '<button type="button" class="dotbtn"' + tip(dotTip) + '><span class="dot" style="background:' + (connected ? "var(--green)" : "var(--orange)") + ";box-shadow:0 0 0 4px " + (connected ? "rgba(31,157,85,.18)" : "rgba(200,109,81,.24)") + '"></span></button>';
    var pv = st.privacy, sc = !pv ? "#86868B" : (pv.ok ? "#1E8E3E" : "#A4452A");
    var pt = t.localHint + ". " + t.privAuto + ": " + (!pv ? t.privNone : (pv.ok ? t.privOk + " · " + fmtDate(pv.when) : t.privBad));
    h += '<span class="pill"' + tip(pt) + ">" + I.shield(sc, 18) + esc(t.local) + "</span>";
    var charging = connected && st.battery && st.battery.level != null && st.battery.level < 100;  // plugged in and not full: the Pocket does not publish its charging state
    if (st.battery && st.battery.level != null) { h += '<span class="bat"' + tip(t.batTip.replace("{n}", st.battery.level) + (charging ? t.batCharging : "")) + ">" + batteryIcon(st.battery.level, charging) + "</span>"; }
    h += "</div>";
    h += '<div class="row" style="gap:2px"><div style="margin-right:6px"' + tip(t.uiLang) + ">" + segLang("ui", ui(), "s34", t, "") + "</div>";
    h += '<button type="button" class="ib plain' + bg(S.findOpen) + '" data-a="find"' + tip(t.find) + ">" + I.search + "</button>";
    h += '<button type="button" class="ib plain' + bg(S.tasksOpen) + '" data-a="tasksToggle"' + tip(t.tasks) + ">" + I.tasks + "</button>";
    h += '<button type="button" class="ib plain' + (S.hidden ? " hiddenon" : "") + '" data-a="eye" aria-pressed="' + S.hidden + '"' + tip(S.hidden ? t.eyeShow : t.eyeHide) + ">" + (S.hidden ? I.eyeOff : I.eye) + "</button>";
    h += '<button type="button" class="ib plain' + bg(S.aboutOpen) + (st.update && st.update.available ? " upd" : "") + '" data-a="about"' + tip(t.about) + ">" + I.info + "</button>";
    h += '<button type="button" class="ib plain' + bg(S.settingsOpen) + '" data-a="settings"' + tip(t.settings) + ">" + I.gear + "</button></div></div>";
    if (S.settingsOpen) { h += viewSettings(t, st); }
    if (S.findOpen) { h += viewFind(t); }
    if (S.tasksOpen) { h += viewTasks(t); }
    if (S.aboutOpen) { h += viewAbout(t); }
    h += '<div class="side"><div class="hero"><div class="ring"' + (job.running ? tip(stepText(job, t)) : "") + '><svg class="arc" width="156" height="156" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="46" fill="none" stroke="#E5E5EA" stroke-width="3"></circle>' +
      '<circle cx="50" cy="50" r="46" fill="none" stroke="#3368A0" stroke-width="3" stroke-linecap="round" stroke-dasharray="' + (ring * 289).toFixed(1) + ' 289" transform="rotate(-90 50 50)"></circle></svg>';
    h += '<button type="button" class="import' + (job.running ? " busy" : "") + '" data-a="import"' + (canImport ? "" : " disabled") + tip(t.importHint) + ">" + I.downBig + "</button>";
    var todo = (st.pocket.new || 0) + (st.totals.waiting || 0);
    if (todo > 0) { h += '<span class="badge"' + tip(t.queueTip.replace("{n}", todo)) + ">" + todo + "</span>"; }
    h += "</div></div>";
    if (!st.ollama) { h += '<div class="err">' + esc(t.modelDown) + "</div>"; }
    h += "</div>";
    if (S.pickMode && !S.hidden) {
      var chosen = Object.keys(S.pick).filter(function (k) { return S.pick[k]; }).length;
      h += '<div class="card pickbar"><span class="text">' + esc(t.pickCount.replace("{n}", chosen)) + '</span><div class="row gap8"><input id="pickTagInput" type="text" class="dinput" maxlength="30" style="width:96px" placeholder="' + esc(t.pickTagPlaceholder) + '" aria-label="' + esc(t.tagHint) + '" value="' + esc(S.pickTag) + '"><button type="button" class="ib sm" data-a="pickTagGo"' + (chosen && S.pickTag.trim() ? "" : " disabled") + tip(t.tagHint) + ">" + I.tag + "</button>" + '<button type="button" class="ib sm" data-a="pickAll"' + tip(t.pickAll) + ">" + I.tasks +
        '</button><button type="button" class="ib sm" data-a="pickCancel"' + tip(t.pickCancel) + ">" + I.x + '</button><button type="button" class="ib sm blue" data-a="pickGo"' + (chosen ? "" : " disabled") + tip(t.pickGo) + ">" + I.checkW + "</button></div></div>";
    }
    h += S.hidden ? veil(t) : (S.pickMode ? "" : viewTagFilter(t)) + viewList(t, st);
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
    var caret = null;
    try {  // the page is drawn again when the state changes: the caret and the scroll of the field being typed in stay where they were
      if (focus && document.activeElement.setSelectionRange) { caret = [document.activeElement.selectionStart, document.activeElement.selectionEnd, document.activeElement.scrollTop]; }
    } catch (e) { caret = null; }
    app.innerHTML = html;
    document.documentElement.lang = ui();
    if (focus && document.getElementById(focus)) {
      var el = document.getElementById(focus);
      el.focus();
      if (typeof value === "string") { el.value = value; }
      try {
        if (caret && el.setSelectionRange) { el.setSelectionRange(caret[0], caret[1]); el.scrollTop = caret[2]; }
        else if (el.setSelectionRange && typeof value === "string") { el.setSelectionRange(value.length, value.length); }
      } catch (e) { /* a field without a caret, such as a date */ }
    } else if (S.edit && document.getElementById("nameInput")) {
      var inp = document.getElementById("nameInput"); inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length);
    }
  }

  // The transcript opens in a window of its own, outside the polled page, so it keeps its scroll position.
  function closeText() {
    var box = document.getElementById("txtview");
    if (box) { box.parentNode.removeChild(box); document.body.style.overflow = ""; }
  }

  function speakersOf(full) {
    var names = full.speaker_names || {};
    var seen = [], out = [];
    (full.segments || []).forEach(function (s) {
      if (s.speaker && seen.indexOf(s.speaker) === -1) {
        seen.push(s.speaker);
        out.push({ raw: s.speaker, disp: names[s.speaker] || s.speaker });
      }
    });
    return out;
  }

  function saveSpeaker(id, raw) {
    var name = (S.spkDraft || "").trim();
    api("POST", "/api/note/" + encodeURIComponent(id) + "/speaker", { from: raw, name: name }).then(function () {
      S.spkEdit = null; delete S.full[id]; flash(T().spkSaved); showText(id);
    }).catch(function (e) { flash(T().error + e.message); });
  }

  function speakerPanel(id, full, t) {
    var speakers = speakersOf(full);
    if (!speakers.length) {
      return S.server && S.server.diar_installed
        ? '<div class="spk"><div class="small">' + esc(t.spkNone) + " " + esc(t.spkUseRediarize) + "</div></div>"
        : "";
    }
    var rows = speakers.map(function (sp) {
      if (S.spkEdit && S.spkEdit.id === id && S.spkEdit.raw === sp.raw) {
        return '<div class="spkrow"><input id="spkInput" type="text" value="' + esc(S.spkDraft) + '" placeholder="' + esc(t.spkPlaceholder) + '" aria-label="' + esc(t.spkPlaceholder) + '">' +
          '<button type="button" class="sv" data-tx="saveSpk" data-raw="' + esc(sp.raw) + '"' + tip(t.saveName) + ">" + I.checkW + "</button></div>";
      }
      return '<span class="chip"><span class="nm">' + esc(sp.disp) + '</span><button type="button" class="pen" data-tx="editSpk" data-raw="' + esc(sp.raw) + '"' + tip(t.rename + " : " + sp.disp) + ">" + I.pencil.replace("20", "14").replace("20", "14") + "</button></span>";
    }).join("");
    return '<div class="spk"><div class="lbl">' + esc(t.participants) + '</div><div class="rows">' + rows + "</div></div>";
  }

  function showText(id, start) {
    var t = T();
    api("GET", "/api/note/" + encodeURIComponent(id)).then(function (full) {
      var text = full.clean || "";
      var weak = (full.doubtful || []).map(function (p) { return String(p.text || "").trim(); }).filter(Boolean);
      var speakers = speakersOf(full);
      var names = speakers.map(function (sp) { return sp.disp; }).sort(function (a, b) { return b.length - a.length; });
      var reNames = names.length ? new RegExp("^(" + names.map(function (n) { return n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + "): ") : null;
      var body = text.split(/\n+/).filter(function (x) { return x.trim(); }).map(function (line) {
        var hit = weak.some(function (w) { return line.indexOf(w) !== -1; });
        var m = line.match(/^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*/);
        var secs = m ? stampSeconds(m[1]) : null;
        var stamp = m ? '<span class="ts"' + (full.has_audio ? ' data-tx="seek" data-s="' + secs + '"' + tip(t.listenHint) : "") + ">" + esc(m[1]) + "</span>" : "";
        var rest = m ? line.slice(m[0].length) : line;
        var sm = reNames && rest.match(reNames);
        var who = sm ? "<b>" + esc(sm[1]) + ": </b>" : "";
        return "<p" + (hit ? ' class="dbt"' : "") + (secs != null ? ' data-s="' + secs + '"' : "") + ">" + stamp + who + esc(sm ? rest.slice(sm[0].length) : rest) + "</p>";
      }).join("") || '<p class="small">' + esc(t.noText) + "</p>";
      closeText();
      var box = document.createElement("div");
      box.id = "txtview";
      box.innerHTML = '<div class="mback" data-tx="close"></div><div class="mcard" role="dialog" aria-modal="true" aria-label="' + esc(t.viewText) + '">' +
        '<div class="mhead"><div class="mtitle">' + esc(full.title || id) + '</div><div class="row gap8">' +
        '<button type="button" class="ib" data-tx="copy"' + tip(t.copyText) + ">" + I.copy.replace("#FFFFFF", "#1D1D1F") + "</button>" +
        '<button type="button" class="ib grey2" data-tx="close"' + tip(t.closeLbl) + ">" + I.x + "</button></div></div>" +
        (full.has_audio ? '<div class="mleg"><audio id="txtaudio" controls preload="metadata" src="/api/note/' + encodeURIComponent(id) + '/audio"></audio></div>' : "") +
        speakerPanel(id, full, t) +
        (full.quality != null ? '<div class="mleg">' + esc(t.rawLegend) + " : " + full.quality + " %</div>" : "") + (weak.length ? '<div class="mleg">' + esc(t.textLegend) + "</div>" : "") + '<div class="mbody">' + body + "</div></div>";
      box.addEventListener("click", function (ev) {
        var el = ev.target.closest("[data-tx]");
        if (!el) { return; }
        var tx = el.getAttribute("data-tx");
        if (tx === "close") { closeText(); return; }
        if (tx === "copy") { navigator.clipboard.writeText(text).then(function () { flash(T().copied); }); return; }
        if (tx === "editSpk") {
          var raw = el.getAttribute("data-raw");
          S.spkEdit = { id: id, raw: raw };
          S.spkDraft = (full.speaker_names && full.speaker_names[raw]) || "";
          showText(id);
          return;
        }
        if (tx === "saveSpk") { saveSpeaker(id, el.getAttribute("data-raw")); return; }
        if (tx === "seek") {
          var player = document.getElementById("txtaudio");
          if (player) { player.currentTime = parseFloat(el.getAttribute("data-s")) || 0; player.play().catch(function () { /* the browser asked for a click first */ }); }
          return;
        }
      });
      document.body.appendChild(box);
      document.body.style.overflow = "hidden";
      if (start != null) {  // coming from a search: the line spoken at that moment is shown and marked
        var lines = box.querySelectorAll(".mbody p[data-s]"), at = null;
        for (var k = 0; k < lines.length; k += 1) { if (parseFloat(lines[k].getAttribute("data-s")) <= start + 0.5) { at = lines[k]; } }
        if (at) { at.className += " sel"; at.scrollIntoView({ block: "center" }); }
        var pl = document.getElementById("txtaudio");
        if (pl) { pl.currentTime = start; }
      }
      if (S.spkEdit && S.spkEdit.id === id) {
        var inp = document.getElementById("spkInput");
        if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
      }
    }).catch(function (e) { flash(t.error + e.message); });
  }

  function noteAction(id, action) {
    api("POST", "/api/note/" + encodeURIComponent(id) + "/" + action).then(refresh)
      .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
  }

  function loadModels() {
    return api("GET", "/api/models").then(function (m) {
      var was = S.models && S.models.job && S.models.job.state === "running";
      S.models = m;
      if (was && m.job && m.job.state === "done") {
        flash(T().mDone);
        if (S.aboutOpen) { api("GET", "/api/about").then(function (a) { S.about = a; render(); }); }
      }
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
    autoprocess: function (v) { api("POST", "/api/settings", { autoprocess: v === "1" }).then(refresh); },
    autoimport: function (v) { api("POST", "/api/settings", { autoimport: v === "1" }).then(refresh); },
    diarizeDevice: function (v) { api("POST", "/api/settings", { diarize_device: v }).then(refresh); },
    autocheck: function (v) { api("POST", "/api/settings", { autocheck: v === "1" }).then(refresh); },
    settings: function () { S.settingsOpen = !S.settingsOpen; if (S.settingsOpen) { S.findOpen = false; S.tasksOpen = false; } },
    find: function () {
      S.findOpen = !S.findOpen;
      if (S.findOpen) { S.settingsOpen = false; S.aboutOpen = false; S.tasksOpen = false; setTimeout(function () { var el = document.getElementById("findInput"); if (el) { el.focus(); } }, 50); }
    },
    findGo: function (v, id) {
      if (v !== "" && v != null) { showText(id, parseFloat(v)); return; }
      S.findOpen = false; S.open = id; S.hidden = false; S.edit = null; S.exp = null; S.delConfirm = false;
      refresh().then(function () { loadFull(id); });
    },
    tasksToggle: function () {
      S.tasksOpen = !S.tasksOpen;
      if (S.tasksOpen) { S.settingsOpen = false; S.aboutOpen = false; S.findOpen = false; loadTasks(); }
    },
    tplAsk: function () { S.tplOpen = !S.tplOpen; S.tplEdit = null; S.tplDel = null; },
    tplNew: function () { S.tplEdit = { idx: -1, name: "", prompt: "" }; },
    tplEdit: function (v) { var x = myTemplates()[parseInt(v, 10)]; if (x) { S.tplEdit = { idx: parseInt(v, 10), name: x.name, prompt: x.prompt }; S.tplDel = null; } },
    tplCancel: function () { S.tplEdit = null; },
    tplSave: function () {
      var ed = S.tplEdit;
      if (!ed || !ed.name.trim() || !ed.prompt.trim()) { return; }
      var list = myTemplates().map(function (x) { return { id: x.id, name: x.name, prompt: x.prompt }; });
      if (ed.idx >= 0 && list[ed.idx]) { list[ed.idx].name = ed.name; list[ed.idx].prompt = ed.prompt; } else { list.push({ name: ed.name, prompt: ed.prompt }); }
      S.tplEdit = null;
      api("POST", "/api/settings", { templates: list }).then(refresh).catch(function (e) { flash(T().error + e.message); });
    },
    tplDelAsk: function (v) { S.tplDel = parseInt(v, 10); S.tplEdit = null; },
    tplDelNo: function () { S.tplDel = null; },
    tplDelGo: function () {
      var i = S.tplDel; S.tplDel = null;
      var list = myTemplates().filter(function (x, k) { return k !== i; });
      api("POST", "/api/settings", { templates: list }).then(refresh).catch(function (e) { flash(T().error + e.message); });
    },
    tplStar: function (v) {
      var x = myTemplates()[parseInt(v, 10)];
      if (x) { api("POST", "/api/settings", { template_default: (S.server.settings.template_default === x.id) ? "" : x.id }).then(refresh).catch(function (e) { flash(T().error + e.message); }); }
    },
    tagsSuggest: function (v) { api("POST", "/api/settings", { tags_suggest: v === "1" }).then(refresh); },
    tagToggle: function (v, id) { S.tagEdit = S.tagEdit === id ? null : id; S.tagDraft = ""; },
    tagFilter: function (v) { S.tagFilter = S.tagFilter.toLowerCase() === String(v).toLowerCase() ? "" : v; },
    tagRemove: function (v) { setNoteTags(S.open, tagsOf(noteRow(S.open)).filter(function (x) { return x !== v; })); },
    tagAccept: function (v) { setNoteTags(S.open, tagsOf(noteRow(S.open)).concat([v])); },
    tagPick: function (v) { setNoteTags(S.open, tagsOf(noteRow(S.open)).concat([v])); S.tagDraft = ""; },
    tagAdd: function () {
      var draft = S.tagDraft.trim();
      if (draft) { setNoteTags(S.open, tagsOf(noteRow(S.open)).concat([draft])); }
      S.tagDraft = "";
    },
    tagDismiss: function () {
      api("POST", "/api/note/" + encodeURIComponent(S.open) + "/tags", { dismiss: true }).then(refresh).catch(function (e) { flash(T().error + e.message); });
    },
    pickTagGo: function () {
      var ids = Object.keys(S.pick).filter(function (k) { return S.pick[k]; }), tag = S.pickTag.trim();
      if (!ids.length || !tag) { return; }
      S.pickMode = false; S.pick = {}; S.pickTag = "";
      api("POST", "/api/tags/add", { ids: ids, tag: tag }).then(function (r) { flash(T().tagApplied.replace("{n}", r.count)); refresh(); })
        .catch(function (e) { flash(T().error + e.message); });
    },
    taskEdit: function (v) { var a = S.tasks && S.tasks[parseInt(v, 10)]; if (a) { S.taskEdit = { i: parseInt(v, 10), what: a.what, who: a.who || "", when: a.when || "" }; S.taskDel = null; } },
    taskCancel: function () { S.taskEdit = null; },
    taskSave: function () {
      var ed = S.taskEdit, a = ed && S.tasks && S.tasks[ed.i];
      if (!a || !ed.what.trim()) { return; }
      S.taskEdit = null;
      api("POST", "/api/note/" + encodeURIComponent(a.note) + "/actionedit", { index: a.index, was: a.what, what: ed.what, who: ed.who, when: ed.when }).then(loadTasks)
        .catch(function (e) { flash(T().error + e.message); loadTasks(); });
    },
    taskDel: function (v) { S.taskDel = parseInt(v, 10); S.taskEdit = null; },
    taskDelNo: function () { S.taskDel = null; },
    taskDelGo: function () {
      var a = S.tasks && S.tasks[S.taskDel];
      S.taskDel = null;
      if (!a) { return; }
      api("POST", "/api/note/" + encodeURIComponent(a.note) + "/actionedit", { index: a.index, was: a.what, delete: true }).then(loadTasks)
        .catch(function (e) { flash(T().error + e.message); loadTasks(); });
    },
    tick: function (v) {
      var a = S.tasks && S.tasks[parseInt(v, 10)];
      if (!a) { return; }
      a.done = !a.done;
      api("POST", "/api/note/" + encodeURIComponent(a.note) + "/action", { what: a.what, done: a.done }).then(loadTasks).catch(function () { a.done = !a.done; });
    },
    tasksCopy: function () {
      var lines = (S.tasks || []).filter(function (a) { return !a.done; }).map(function (a) {
        return "- " + a.what + (a.who || a.when ? " (" + [a.who, a.when].filter(Boolean).join(", ") + ")" : "") + " · " + a.title;
      });
      navigator.clipboard.writeText(lines.join("\n")).then(function () { flash(T().tasksCopied); });
    },
    mailOpen: function (v, id) { showMail(id); },
    vocabAll: function () { applyVocab({ all: true }); },
    vocabRangeToggle: function () { S.vRange = !S.vRange; },
    vocabRange: function () { if (S.vFrom || S.vTo) { applyVocab({ from: S.vFrom, to: S.vTo }); } },
    pickStart: function () { S.pickMode = true; S.pick = {}; S.settingsOpen = false; S.hidden = false; S.open = null; refresh(); },
    pickTog: function (v, id) {
      var n = ((S.server && S.server.notes) || []).filter(function (x) { return x.id === id; })[0];
      if (n && n.status === "done") { S.pick[id] = !S.pick[id]; }
    },
    pickAll: function () {
      var done = ((S.server && S.server.notes) || []).filter(function (x) { return x.status === "done"; });
      var every = done.length && done.every(function (x) { return S.pick[x.id]; });
      S.pick = {};
      if (!every) { done.forEach(function (x) { S.pick[x.id] = true; }); }
    },
    pickCancel: function () { S.pickMode = false; S.pick = {}; },
    pickGo: function () {
      var ids = Object.keys(S.pick).filter(function (k) { return S.pick[k]; });
      S.pickMode = false; S.pick = {};
      if (ids.length) { applyVocab({ ids: ids }); }
    },
    about: function () {
      S.aboutOpen = !S.aboutOpen;
      if (S.aboutOpen) { S.findOpen = false; S.tasksOpen = false; }
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
    row: function (v, id) { S.open = S.open === id ? null : id; S.delConfirm = false; S.edit = null; S.exp = null; S.rr = noteLevel(id); S.rl = noteLang(id); S.sp = noteSpeech(id); if (S.open) { loadFull(id); } },
    cycleTpl: function () {
      var id = S.open, full = S.full[id];
      if (!full) { return; }
      var order = TPL.concat(myTemplates().map(function (x) { return x.id; })), next = order[(order.indexOf(noteTplKey(full)) + 1) % order.length];
      api("POST", "/api/note/" + encodeURIComponent(id) + "/template", { template: next }).then(function () {
        delete S.full[id];
        if (TPL.indexOf(next) < 0) { return A.rerun(); }  // one of the person's templates is an instruction: the note is written again with it
        return refresh();
      }).catch(function (e) { flash(T().error + e.message); });
    },
    cycle: function (v) {
      var order = v === "lvl" ? ["short", "mid", "full"] : v === "sp" ? ["auto", "fr", "en"] : ["fr", "en"], cur = v === "lvl" ? S.rr : v === "sp" ? S.sp : S.rl;
      (v === "lvl" ? A.rr : v === "sp" ? A.sp : A.rl)(order[(order.indexOf(cur) + 1) % order.length]);
    },
    rr: function (v) {
      S.rr = v;
      var id = S.open, n = findNote(id);
      if (n && n.status !== "done") { api("POST", "/api/note/" + encodeURIComponent(id) + "/options", { level: v }).then(refresh); }
    },
    rl: function (v) {
      S.rl = v;
      var id = S.open, n = findNote(id);
      if (n && n.status !== "done") { api("POST", "/api/note/" + encodeURIComponent(id) + "/options", { lang: v }).then(refresh); }
    },
    sp: function (v) {
      S.sp = v;
      var id = S.open, n = findNote(id);
      if (n && n.status !== "done") { api("POST", "/api/note/" + encodeURIComponent(id) + "/options", { speech_lang: v }).then(refresh); }
    },
    rerun: function () {
      var t = T(), id = S.open;
      api("POST", "/api/note/" + encodeURIComponent(id) + "/rerun", { level: S.rr, lang: S.rl, speech_lang: S.sp }).then(function () { delete S.full[id]; flash(t.redoing + t[S.rr].toLowerCase()); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
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
    expMd: function () { S.exp = null; download(S.open, "md"); },
    expHtml: function () { S.exp = null; download(S.open, "html"); },
    expCopy: function () { S.exp = null; copyRich(S.open).catch(function () { flash(T().error + "clipboard"); }); },
    viewText: function (v, id) { showText(id); },
    askDelete: function () { S.delConfirm = true; },
    confirmDelete: function () {
      var id = S.open;
      api("POST", "/api/note/" + encodeURIComponent(id) + "/delete").then(function (r) { S.open = null; S.delConfirm = false; flash(r.pocket ? T().deleted : T().deletedLater); refresh(); })
        .catch(function (e) { S.delConfirm = false; flash(T().error + e.message); });
    },
    askRediarize: function (v, id) { S.rediarConfirm = id; },
    rediarizeGo: function () {
      var t = T(), id = S.rediarConfirm; S.rediarConfirm = null;
      api("POST", "/api/note/" + encodeURIComponent(id) + "/rediarize").then(function () { delete S.full[id]; flash(t.rediarizeGoing); refresh(); })
        .catch(function (e) { flash(t.error + (e.message === "busy" ? t.mBusy : e.message === "diar_unavailable" ? t.rediarizeMissing : e.message)); });
    },
    cancel: function () { S.delConfirm = false; S.rediarConfirm = null; S.mAsk = null; S.mDel = null; },
    folder: function () {
      api("POST", "/api/pick-folder").then(function (r) { return api("POST", "/api/settings", { audio_dir: r.path }); })
        .then(function () { flash(T().folderSaved); refresh(); })
        .catch(function (e) { if (e.status === 501) { S.folderEdit = true; S.folderDraft = S.server.settings.audio_dir; render(); } });
    },
    folderSave: function () {
      api("POST", "/api/settings", { audio_dir: S.folderDraft }).then(function () { S.folderEdit = false; flash(T().folderSaved); refresh(); })
        .catch(function (e) { flash(T().error + e.message); });
    },
    keyAsk: function () {
      S.keyEdit = !S.keyEdit;
      S.keyDraft = S.keyEdit ? (S.server.settings.pocket_key || "") : "";
    },
    keySave: function () {
      var t = T(), key = S.keyDraft.trim();
      if (key.length !== 16) { flash(t.pocketKeyInvalid); return; }
      api("POST", "/api/settings", { pocket_key: key }).then(function () { S.keyEdit = false; flash(t.pocketKeySaved); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
    },
    keyClear: function () {
      var t = T();
      api("POST", "/api/settings", { pocket_key: "" }).then(function () { S.keyEdit = false; flash(t.pocketKeyCleared); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
    },
    diarize: function (v) {
      api("POST", "/api/settings", { diarize: v === "1" }).then(refresh).catch(function (e) { flash(T().error + e.message); });
    },
    vocabAsk: function () {
      S.vocabEdit = !S.vocabEdit;
      S.vocabDraft = S.vocabEdit ? (S.server.settings.vocabulary || []).join("\n") : "";
    },
    vocabSave: function () {
      var t = T();
      api("POST", "/api/settings", { vocabulary: S.vocabDraft }).then(function () { S.vocabEdit = false; flash(t.vocabSaved); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
    },
    hfAsk: function () {
      S.hfEdit = !S.hfEdit;
      S.hfDraft = S.hfEdit ? (S.server.settings.hf_token || "") : "";
    },
    hfSave: function () {
      var t = T(), token = S.hfDraft.trim();
      if (!token) { flash(t.hfTokenInvalid); return; }
      api("POST", "/api/settings", { hf_token: token }).then(function () { S.hfEdit = false; flash(t.hfTokenSaved); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
    },
    hfClear: function () {
      var t = T();
      api("POST", "/api/settings", { hf_token: "" }).then(function () { S.hfEdit = false; flash(t.hfTokenCleared); refresh(); })
        .catch(function (e) { flash(t.error + e.message); });
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
        .catch(function (e) { var t = T(); flash(t.error + (e.message === "busy" ? t.mBusy : e.message === "in_use" && a.kind === "diar" ? t.diarizeLabel : e.message)); });
    },
    mGo: function () {
      var a = S.mAsk; S.mAsk = null;
      api("POST", "/api/models/install", { kind: a.kind, id: a.id, confirm: true }).then(loadModels)
        .catch(function (e) { var t = T(); flash(t.error + (e.message === "busy" ? t.mBusy : e.message === "token_required" ? t.diarNeedsToken : e.message)); });
    },
    mUse: function (kind, id) {
      api("POST", "/api/models/select", { kind: kind, id: id }).then(function () { return loadModels(); }).then(refresh)
        .catch(function (e) { flash(T().error + (e.message === "busy" ? T().mBusy : e.message)); });
    }
  };

  document.addEventListener("click", function (ev) {
    if (S.exp && !ev.target.closest(".pop")) { S.exp = null; render(); }
    var el = ev.target.closest("[data-a]");
    if (!el || el.disabled) { return; }
    var fn = A[el.getAttribute("data-a")];
    if (fn) { fn(el.getAttribute("data-v"), el.getAttribute("data-id")); render(); }
  });
  document.addEventListener("input", function (ev) {
    if (ev.target.id === "nameInput") { S.draft = ev.target.value; }
    if (ev.target.id === "folderInput") { S.folderDraft = ev.target.value; }
    if (ev.target.id === "keyInput") { S.keyDraft = ev.target.value; }
    if (ev.target.id === "hfInput") { S.hfDraft = ev.target.value; }
    if (ev.target.id === "vocabInput") { S.vocabDraft = ev.target.value; }
    if (S.tplEdit && ev.target.id === "tplName") { S.tplEdit.name = ev.target.value; }
    if (S.tplEdit && ev.target.id === "tplPrompt") { S.tplEdit.prompt = ev.target.value; }
    if (ev.target.id === "tagInput") { S.tagDraft = ev.target.value; render(); }
    if (ev.target.id === "pickTagInput") { S.pickTag = ev.target.value; render(); }
    if (S.taskEdit && ev.target.id === "tkWhat") { S.taskEdit.what = ev.target.value; }
    if (S.taskEdit && ev.target.id === "tkWho") { S.taskEdit.who = ev.target.value; }
    if (S.taskEdit && ev.target.id === "tkWhen") { S.taskEdit.when = ev.target.value; }
    if (ev.target.id === "vFrom") { S.vFrom = ev.target.value; }
    if (ev.target.id === "vTo") { S.vTo = ev.target.value; }
    if (ev.target.id === "findInput") { S.findQ = ev.target.value; clearTimeout(S.findTimer); S.findTimer = setTimeout(runFind, 250); }
    if (ev.target.id === "spkInput") { S.spkDraft = ev.target.value; }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { closeText(); if (S.exp) { S.exp = null; render(); } if (S.taskEdit) { S.taskEdit = null; render(); } if (S.tplEdit) { S.tplEdit = null; render(); } }
    if (ev.key === "Enter" && ev.target.id === "tkWhat") { A.taskSave(); render(); }
    if (ev.key === "Enter" && ev.target.id === "tagInput") { A.tagAdd(); render(); }
    if (ev.key === "Enter" && ev.target.id === "nameInput") { A.saveName(); }
    if (ev.key === "Enter" && ev.target.id === "folderInput") { A.folderSave(); }
    if (ev.key === "Enter" && ev.target.id === "keyInput") { A.keySave(); }
    if (ev.key === "Enter" && ev.target.id === "hfInput") { A.hfSave(); }
    if (ev.key === "Enter" && ev.target.id === "spkInput" && S.spkEdit) { saveSpeaker(S.spkEdit.id, S.spkEdit.raw); }
  });

  function fitWindow() {  // the installed web app opens at a size that fits its content, once; the person's own resizing is kept after that
    try {
      if (!window.matchMedia("(display-mode: standalone)").matches || localStorage.getItem("cairn.fitted")) { return; }
      localStorage.setItem("cairn.fitted", "1");
      var w = Math.min(window.innerWidth, 980), h = Math.max(520, Math.min(window.innerHeight, document.documentElement.scrollHeight + 24, 760));
      window.resizeTo(w + (window.outerWidth - window.innerWidth), h + (window.outerHeight - window.innerHeight));
    } catch (e) { /* not allowed here: the window keeps its size */ }
  }

  function loop() {
    refresh().then(function () {
      if (S.server && !S.fitted) { S.fitted = true; setTimeout(fitWindow, 300); }
      if (!S.uiSaved && S.server) {  // the note language defaults to the interface language, so the server must know it
        S.uiSaved = true;
        if (!S.server.settings.ui) { api("POST", "/api/settings", { ui: ui() }); }
      }
      var busy = S.server && (S.server.job.running || (S.server.download && S.server.download.state === "running"));
      setTimeout(loop, busy ? 1000 : 2500);
    });
  }
  loop();
})();
