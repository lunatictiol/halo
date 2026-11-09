// Typeset LaTeX in answers after each SSE swap. Unparseable math is left as plain text (throwOnError: false).
document.body.addEventListener("htmx:sseMessage", (e) => {
  setTimeout(() => renderMathInElement(e.target, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
      { left: "$", right: "$", display: false },
    ],
    throwOnError: false,
  }), 0);
});
