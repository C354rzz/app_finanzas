// Comportamiento global de la interfaz. Ver apps/core/htmx.py.
const modal = () => document.getElementById("modal");

// Abrir el modal cuando HTMX coloca contenido en él.
document.addEventListener("htmx:afterSwap", (evento) => {
  if (evento.detail.target.id === "modal-contenido" && !modal().open) {
    modal().showModal();
  }
});

// Tras guardar, el servidor responde 204 + "datosActualizados": cerrar y recargar.
document.addEventListener("datosActualizados", () => {
  if (modal().open) modal().close();
  window.location.reload();
});

document.addEventListener("click", (evento) => {
  if (evento.target.closest("[data-cerrar-modal]")) modal().close();
});

// Un <select data-extraordinarios="a b c"> marca la casilla es_extraordinario de su formulario.
document.addEventListener("change", (evento) => {
  const lista = evento.target.dataset?.extraordinarios;
  if (lista === undefined) return;
  const casilla = evento.target.form?.querySelector("[name=es_extraordinario]");
  if (casilla) casilla.checked = lista.split(" ").includes(evento.target.value);
});
