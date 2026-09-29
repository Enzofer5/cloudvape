/* CloudVape - scripts del panel admin: gráfico de barras en <canvas> y formularios dinámicos */
(function () {
  "use strict";

  function formatMoney(v) {
    return "$ " + Math.round(v).toLocaleString("es-AR");
  }

  function drawBarChart(canvas) {
    let labels, values;
    try {
      labels = JSON.parse(canvas.dataset.labels || "[]");
      values = JSON.parse(canvas.dataset.values || "[]");
    } catch (e) { return; }

    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = parseInt(canvas.getAttribute("height"), 10) || 240;
    canvas.style.height = cssH + "px";
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);

    const pad = { top: 16, right: 10, bottom: 28, left: 70 };
    const w = cssW - pad.left - pad.right;
    const h = cssH - pad.top - pad.bottom;
    const max = Math.max(1, ...values);
    const styles = getComputedStyle(document.documentElement);
    const muted = styles.getPropertyValue("--muted").trim() || "#999";
    const border = styles.getPropertyValue("--border").trim() || "#333";

    // grilla y eje Y
    ctx.font = "11px Inter, sans-serif";
    ctx.fillStyle = muted;
    ctx.strokeStyle = border;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + h - (h * i) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + w, y);
      ctx.stroke();
      ctx.fillText(formatMoney((max * i) / 4), pad.left - 8, y);
    }

    if (!values.length) return;
    const slot = w / values.length;
    const barW = Math.max(2, slot * 0.7);
    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + h);
    grad.addColorStop(0, "#ffffff");
    grad.addColorStop(1, "#8a8a8a");

    const bars = [];
    values.forEach((v, i) => {
      const bh = (v / max) * h;
      const x = pad.left + i * slot + (slot - barW) / 2;
      const y = pad.top + h - bh;
      ctx.fillStyle = grad;
      ctx.fillRect(x, y, barW, bh);
      bars.push({ x, y, w: barW, h: bh, label: labels[i], value: v });
    });

    // etiquetas eje X (se saltean para no superponerse)
    ctx.fillStyle = muted;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const every = Math.ceil(labels.length / Math.max(1, Math.floor(w / 48)));
    labels.forEach((l, i) => {
      if (i % every === 0) ctx.fillText(l, pad.left + i * slot + slot / 2, pad.top + h + 8);
    });

    canvas._bars = bars;
  }

  function attachTooltip(canvas) {
    const tip = document.createElement("div");
    tip.className = "toast";
    tip.style.transition = "none";
    tip.style.pointerEvents = "none";
    document.body.appendChild(tip);
    canvas.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const bar = (canvas._bars || []).find((b) => mx >= b.x - 2 && mx <= b.x + b.w + 2);
      if (bar) {
        tip.textContent = bar.label + " · " + formatMoney(bar.value);
        tip.style.left = e.clientX + "px";
        tip.style.top = (e.clientY - 50) + "px";
        tip.style.bottom = "auto";
        tip.style.transform = "translateX(-50%)";
        tip.classList.add("show");
      } else {
        tip.classList.remove("show");
        tip.style.transform = "translateX(-50%) translateY(200vh)";
      }
    });
    canvas.addEventListener("mouseleave", () => {
      tip.classList.remove("show");
      tip.style.transform = "translateX(-50%) translateY(200vh)";
    });
  }

  const charts = Array.from(document.querySelectorAll("canvas.js-bar-chart"));
  charts.forEach((c) => { drawBarChart(c); attachTooltip(c); });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => charts.forEach(drawBarChart), 150);
  });

  /* Formulario de descuentos: mostrar selector de producto o de categoría */
  const target = document.querySelector(".js-discount-target select, select#target");
  if (target) {
    const sync = () => {
      document.querySelectorAll("[data-target-panel]").forEach((p) => {
        p.hidden = p.dataset.targetPanel !== target.value;
      });
    };
    target.addEventListener("change", sync);
    sync();
  }
})();
