(function () {
  // mostrar/ocultar senha
  document.querySelectorAll("[data-toggle-pass]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = document.getElementById(btn.getAttribute("data-toggle-pass"));
      var mostrar = input.type === "password";
      input.type = mostrar ? "text" : "password";
      btn.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
      btn.innerHTML = '<i data-lucide="' + (mostrar ? "eye-off" : "eye") + '"></i>';
      if (window.lucide) window.lucide.createIcons();
    });
  });

  // confirmação em ações sensíveis
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // evita duplo envio
  document.querySelectorAll("form").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (e.defaultPrevented) return;
      var b = f.querySelector("button[type=submit]");
      if (b) setTimeout(function () { b.disabled = true; }, 0);
    });
  });

  if (window.lucide) window.lucide.createIcons();
})();
