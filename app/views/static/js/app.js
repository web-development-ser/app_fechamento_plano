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

  // flag "Estoque": bloqueia a seleção de outras localizações
  document.querySelectorAll("[data-bloqueia]").forEach(function (chk) {
    var alvo = document.querySelector(chk.getAttribute("data-bloqueia"));
    if (!alvo) return;
    var form = chk.form;
    var botao = form && form.querySelector("button[type=submit]");
    function aplicar() {
      var on = chk.checked;
      alvo.classList.toggle("bloqueado", on);
      alvo.setAttribute("aria-disabled", on ? "true" : "false");
      alvo.querySelectorAll("input[type=radio]").forEach(function (r) {
        r.disabled = on;
        if (on) r.checked = false;
      });
      if (botao && botao.getAttribute("data-sem-vaga") === "lotado") botao.disabled = !on;
    }
    chk.addEventListener("change", aplicar);
    aplicar();
  });

  // filtros que se atualizam sozinhos (dashboard)
  document.querySelectorAll("form[data-autosubmit]").forEach(function (f) {
    f.querySelectorAll("select, input[type=date]").forEach(function (el) {
      el.addEventListener("change", function () { f.requestSubmit ? f.requestSubmit() : f.submit(); });
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

  // ---------- PWA ----------
  var script = document.currentScript || document.querySelector("script[data-sw]");
  var swUrl = script && script.getAttribute("data-sw");
  if (swUrl && "serviceWorker" in navigator && window.isSecureContext) {
    var tinhaControle = !!navigator.serviceWorker.controller;
    var recarregando = false;
    var formAlterado = false;
    document.addEventListener("input", function (e) {
      if (e.target.closest && e.target.closest("form[method=post]")) formAlterado = true;
    }, true);

    navigator.serviceWorker.register(swUrl, { scope: "/", updateViaCache: "none" }).then(function (reg) {
      // procura versão nova ao voltar para o app e a cada 30 min
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") reg.update();
      });
      setInterval(function () { reg.update(); }, 30 * 60 * 1000);
    }).catch(function () {});

    // nova versão ativada: recarrega sozinho, a menos que haja formulário sendo preenchido
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (!tinhaControle || recarregando) { tinhaControle = true; return; }
      if (formAlterado) {
        var aviso = document.getElementById("aviso-versao");
        if (aviso) aviso.hidden = false;
      } else {
        recarregando = true;
        location.reload();
      }
    });

    // ao sair, apaga as páginas guardadas no aparelho
    document.querySelectorAll('form[action$="/logout"]').forEach(function (f) {
      f.addEventListener("submit", function () {
        if (navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage("limpar-paginas");
      });
    });
  }
})();
