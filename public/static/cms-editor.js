// Monta EasyMDE sobre el textarea #body si esta presente. Degrada al textarea
// plano si EasyMDE no cargo. EasyMDE sincroniza el <textarea> subyacente, asi
// que el form sigue enviando `body` como markdown plano (sin cambios de backend).
(function () {
  var el = document.getElementById("body");
  if (!el || typeof EasyMDE === "undefined") return;
  new EasyMDE({
    element: el,
    autoDownloadFontAwesome: false, // FontAwesome se sirve self-host (Task 1)
    spellChecker: false,            // evita corrector ingles sobre texto espanol
    status: ["lines", "words"],
    toolbar: [
      "bold", "italic", "heading", "|",
      "quote", "unordered-list", "ordered-list", "code", "|",
      "link", "preview", "side-by-side", "fullscreen", "|",
      "guide",
    ],
  });
})();
