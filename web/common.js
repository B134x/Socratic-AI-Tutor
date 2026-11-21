"use strict";

// Helpers shared by the learner and teacher pages.
window.TuntasCommon = {
  fill(text, vars = {}) {
    return text.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
  },

  // Indonesian schools write decimals with a comma.
  decimal(lang, value) {
    const text = value.toFixed(2);
    return lang === "id" ? text.replace(".", ",") : text;
  },

  readStorage(store, key) {
    try { return store.getItem(key); } catch { return null; }
  },

  writeStorage(store, key, value) {
    try { value === null ? store.removeItem(key) : store.setItem(key, value); } catch { /* storage blocked: still works for this tab */ }
  },

  applyStaticText(strings, lang) {
    document.documentElement.lang = lang;
    document.title = strings.pageTitle;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const value = strings[node.dataset.i18n];
      if (typeof value === "string") node.textContent = value;
    });
    document.querySelectorAll("button.lang").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  },
};
