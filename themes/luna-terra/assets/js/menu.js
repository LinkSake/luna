// Menú móvil: abre/cierra el panel de navegación.
(function () {
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.getElementById("site-nav");
  if (!toggle || !nav) return;

  // Con el panel abierto, el resto de la página queda inerte para que el foco no se escape.
  function setInert(on) {
    var others = document.querySelectorAll(".site-main, .site-footer, .skip-link, .site-header > :not(.site-nav):not(.menu-toggle)");
    Array.prototype.forEach.call(others, function (el) { el.inert = on; });
  }

  function setOpen(open) {
    setInert(open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.querySelector(".sr-only").textContent = open ? "Cerrar menú" : "Abrir menú";
    nav.classList.toggle("is-open", open);
    document.body.classList.toggle("menu-open", open);
  }

  // Si la ventana crece mientras el panel está abierto, se cierra.
  window.matchMedia("(min-width: 861px)").addEventListener("change", function (e) {
    if (e.matches) setOpen(false);
  });

  toggle.addEventListener("click", function () {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && nav.classList.contains("is-open")) {
      setOpen(false);
      toggle.focus();
    }
  });
  nav.addEventListener("click", function (e) {
    if (e.target.closest("a")) setOpen(false);
  });
})();
