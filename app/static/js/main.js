/* CloudVape - interacciones del frontend (sin dependencias, compatible con CSP estricta) */
(function () {
  "use strict";

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  /* ---------- Toast ---------- */
  let toastTimer;
  function toast(message, isError = false) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message; // textContent: nunca se interpreta HTML (anti-XSS)
    el.classList.toggle("error", isError);
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
  }

  function updateCartCount(count) {
    const badge = $("#cartCount");
    if (!badge) return;
    badge.textContent = count;
    badge.hidden = !count;
    badge.classList.remove("bump");
    void badge.offsetWidth;
    badge.classList.add("bump");
  }

  async function postForm(form) {
    const resp = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
      credentials: "same-origin",
    });
    let data = {};
    try { data = await resp.json(); } catch (e) { /* respuesta no JSON */ }
    if (!resp.ok || data.ok === false) {
      throw new Error(data.message || "No se pudo completar la acción.");
    }
    return data;
  }

  /* ---------- Toggles (menú móvil, dropdowns, filtros) ---------- */
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-toggle]");
    if (trigger) {
      const target = $(trigger.dataset.toggle);
      if (target) {
        target.classList.toggle("open");
        e.stopPropagation();
      }
      return;
    }
    $$(".dropdown-menu.open").forEach((m) => { if (!m.contains(e.target)) m.classList.remove("open"); });
    if (e.target.closest(".alert-close")) e.target.closest(".alert").remove();
  });

  /* ---------- Confirmación de acciones destructivas ---------- */
  document.addEventListener("submit", (e) => {
    const form = e.target;
    const msg = form.dataset.confirm;
    if (!msg) return;
    const onlyIf = form.dataset.confirmIfValue;
    if (onlyIf) {
      const select = form.querySelector("select");
      if (!select || select.value !== onlyIf) return;
    }
    if (!window.confirm(msg)) e.preventDefault();
  });

  /* ---------- Autosubmit de filtros ---------- */
  $$(".js-autosubmit").forEach((el) => el.addEventListener("change", () => el.form && el.form.submit()));

  /* ---------- Controles de cantidad ---------- */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".qty-btn");
    if (!btn) return;
    const input = btn.parentElement.querySelector("input[type=number]");
    const min = parseInt(input.min || "1", 10);
    const max = parseInt(input.max || "99", 10);
    const next = Math.min(max, Math.max(min, (parseInt(input.value, 10) || min) + parseInt(btn.dataset.step, 10)));
    if (next !== parseInt(input.value, 10)) {
      input.value = next;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });

  /* ---------- Agregar al carrito (AJAX con fallback a POST normal) ---------- */
  $$(".js-add-to-cart").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      try {
        const data = await postForm(form);
        updateCartCount(data.count);
        toast(data.message || "Agregado al carrito");
      } catch (err) {
        toast(err.message, true);
      } finally {
        btn.disabled = false;
      }
    });
  });

  /* ---------- Actualizar cantidades en el carrito ---------- */
  let qtyTimer;
  $$(".js-cart-qty").forEach((form) => {
    const input = form.querySelector("input[name=quantity]");
    input.addEventListener("change", () => {
      clearTimeout(qtyTimer);
      qtyTimer = setTimeout(async () => {
        try {
          const d = await postForm(form);
          const line = form.closest(".cart-line");
          if (d.line_total && line) $(".js-line-total", line).textContent = d.line_total;
          $("#sumSubtotal").textContent = d.subtotal;
          $("#sumDiscount").textContent = d.discount;
          $("#sumShipping").textContent = d.shipping;
          $("#sumTotal").textContent = d.total;
          updateCartCount(d.count);
        } catch (err) {
          toast(err.message, true);
          setTimeout(() => window.location.reload(), 1200);
        }
      }, 350);
    });
  });

  /* ---------- Galería de producto ---------- */
  $$(".gallery-thumbs .thumb").forEach((thumb) => {
    thumb.addEventListener("click", () => {
      $("#galleryMain").src = thumb.dataset.src;
      $$(".gallery-thumbs .thumb").forEach((t) => t.classList.remove("active"));
      thumb.classList.add("active");
    });
  });

  /* ---------- Checkout: completar con dirección guardada ---------- */
  $$(".js-fill-address").forEach((btn) => {
    btn.addEventListener("click", () => {
      const map = { street: "street", number: "street_number", apartment: "apartment",
                    city: "city", province: "province", postal: "postal_code" };
      Object.entries(map).forEach(([key, id]) => {
        const field = document.getElementById(id);
        if (field) field.value = btn.dataset[key] || "";
      });
      toast("Dirección cargada");
    });
  });

  /* ---------- Verificación de edad ---------- */
  const gate = $("#ageGate");
  if (gate) {
    let ok = false;
    try { ok = window.localStorage.getItem("cv_age_ok") === "1"; } catch (e) { ok = false; }
    if (!ok) {
      gate.hidden = false;
      document.body.style.overflow = "hidden";
    }
    $("#ageYes").addEventListener("click", () => {
      try { window.localStorage.setItem("cv_age_ok", "1"); } catch (e) { /* modo privado */ }
      gate.hidden = true;
      document.body.style.overflow = "";
    });
  }
})();
