// Fitnova · Pequeñas mejoras en el navegador. La web funciona igual sin JavaScript.

// Fechas relativas: "hace 3 h", "ayer"…
function haceCuanto(fechaISO) {
  const min = Math.round((Date.now() - new Date(fechaISO)) / 60000);
  if (min < 60) return `hace ${Math.max(min, 1)} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.round(h / 24);
  if (d === 1) return "ayer";
  if (d < 7) return `hace ${d} días`;
  return null;   // más de una semana: dejamos la fecha normal
}
document.querySelectorAll("time[data-relativo]").forEach(t => {
  const texto = haceCuanto(t.getAttribute("datetime"));
  if (texto) t.textContent = texto;
});

// Fecha de hoy en la cabecera
const fechaHoy = document.getElementById("fecha-hoy");
if (fechaHoy) {
  const hoy = new Date().toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
  const hora = new Date(fechaHoy.dataset.actualizado).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  fechaHoy.textContent = `${hoy.charAt(0).toUpperCase() + hoy.slice(1)}. Actualizado a las ${hora}`;
}

// Si una imagen no carga, quitamos su hueco y la noticia pasa a formato solo texto
document.querySelectorAll(".foto img").forEach(img => {
  const quitar = () => {
    const bloque = img.closest(".principal, .fila");
    const enlace = img.closest("a[aria-hidden]");
    (enlace || img.closest(".foto")).remove();
    if (bloque) bloque.classList.add("sin-foto");
  };
  if (img.complete && img.naturalWidth === 0) quitar(); else img.addEventListener("error", quitar);
});

// Listas largas: se muestran de 15 en 15 con un botón "Ver más"
document.querySelectorAll("[data-paginar]").forEach(lista => {
  const porPagina = Number(lista.dataset.paginar) || 15;
  const filas = [...lista.children];
  if (filas.length <= porPagina) return;
  let visibles = porPagina;
  const boton = document.createElement("button");
  boton.className = "boton-secundario ver-mas";
  const actualizar = () => {
    filas.forEach((f, i) => { f.hidden = i >= visibles; });
    const quedan = filas.length - visibles;
    boton.textContent = `Ver más noticias (${quedan})`;
    boton.hidden = quedan <= 0;
  };
  boton.addEventListener("click", () => { visibles += porPagina; actualizar(); });
  lista.after(boton);
  actualizar();
});

// Buscador (solo en buscar.html)
const resultados = document.getElementById("resultados");
if (resultados) {
  const consulta = new URLSearchParams(location.search).get("q") || "";
  const campo = document.getElementById("buscador");
  campo.value = consulta;
  const normalizar = t => (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const escapar = t => { const d = document.createElement("div"); d.textContent = t || ""; return d.innerHTML; };

  fetch(resultados.dataset.indice).then(r => r.json()).then(indice => {
    const palabras = normalizar(consulta).split(/\s+/).filter(Boolean);
    const titulo = document.getElementById("titulo-busqueda");
    if (!palabras.length) { titulo.textContent = "Busca en Fitnova"; return; }
    const encontrados = indice.filter(n => {
      const texto = normalizar(`${n.t} ${n.r} ${n.c} ${n.f}`);
      return palabras.every(p => texto.includes(p));
    });
    titulo.textContent = encontrados.length
      ? `${encontrados.length} resultado${encontrados.length === 1 ? "" : "s"} para «${consulta}»`
      : `Sin resultados para «${consulta}»`;
    resultados.innerHTML = encontrados.map(n => `
      <article class="fila sin-foto">
        <div>
          <div class="meta"><span class="cat">${escapar(n.c)}</span><span>${escapar(n.f)}, ${haceCuanto(n.d) || new Date(n.d).toLocaleDateString("es-ES")}</span></div>
          <a href="${escapar(n.u)}"><h2 class="titular">${escapar(n.t)}</h2></a>
          ${n.r ? `<p class="resumen">${escapar(n.r)}</p>` : ""}
        </div>
      </article>`).join("") || `<p class="vacio">Prueba con otra palabra, por ejemplo «proteína», «sueño» o «fuerza».</p>`;
  }).catch(() => {
    resultados.innerHTML = `<p class="vacio">No hemos podido cargar el buscador. Recarga la página para intentarlo de nuevo.</p>`;
  });
}
