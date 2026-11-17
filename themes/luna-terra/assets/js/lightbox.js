// Lightbox sin dependencias para enlaces con [data-lightbox]; agrupa por el valor del atributo.
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll("a[data-lightbox]"));
  if (!links.length) return;

  var box = document.createElement("div");
  box.className = "lightbox";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", "Visor de imágenes");
  box.innerHTML =
    '<figure><img alt=""><figcaption></figcaption></figure>' +
    '<button class="lightbox__close" type="button" aria-label="Cerrar">×</button>' +
    '<button class="lightbox__prev" type="button" aria-label="Anterior">‹</button>' +
    '<button class="lightbox__next" type="button" aria-label="Siguiente">›</button>';
  document.body.appendChild(box);

  var img = box.querySelector("img");
  var caption = box.querySelector("figcaption");
  var prev = box.querySelector(".lightbox__prev");
  var next = box.querySelector(".lightbox__next");
  var group = [];
  var index = 0;
  var opener = null;

  function show(i) {
    index = (i + group.length) % group.length;
    var link = group[index];
    var thumb = link.querySelector("img");
    img.src = link.getAttribute("href");
    img.alt = thumb ? thumb.alt : "";
    caption.textContent = link.dataset.caption || "";
    caption.hidden = !link.dataset.caption;
  }

  // Todo lo que no es el visor queda inerte mientras está abierto (aria-modal real).
  function setInert(on) {
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el !== box) el.inert = on;
    });
  }

  function open(link) {
    opener = link;
    group = links.filter(function (l) { return l.dataset.lightbox === link.dataset.lightbox; });
    prev.hidden = next.hidden = group.length < 2;
    show(group.indexOf(link));
    setInert(true);
    box.classList.add("is-open");
    document.body.style.overflow = "hidden";
    box.querySelector(".lightbox__close").focus();
  }

  function close() {
    setInert(false);
    box.classList.remove("is-open");
    document.body.style.overflow = "";
    img.removeAttribute("src");
    if (opener) opener.focus();
  }

  links.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      open(link);
    });
  });
  box.querySelector(".lightbox__close").addEventListener("click", close);
  prev.addEventListener("click", function () { show(index - 1); });
  next.addEventListener("click", function () { show(index + 1); });
  box.addEventListener("click", function (e) { if (e.target === box) close(); });
  document.addEventListener("keydown", function (e) {
    if (!box.classList.contains("is-open")) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft" && group.length > 1) show(index - 1);
    else if (e.key === "ArrowRight" && group.length > 1) show(index + 1);
  });
})();
