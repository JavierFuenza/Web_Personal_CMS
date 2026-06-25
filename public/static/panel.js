// Acciones masivas del panel: seleccion por checkboxes, barra de acciones y
// modal de confirmacion al eliminar. Todo via fetch a /entries/bulk, sin recargar.

const selected = new Set();
let pendingDelete = null; // ids en espera de confirmacion en el modal

const bar = document.getElementById("bulk-bar");
const count = document.getElementById("bulk-count");
const overlay = document.getElementById("modal-overlay");
const modalText = document.getElementById("modal-text");

function refreshBar() {
  count.textContent = selected.size + " seleccionadas";
  bar.classList.toggle("visible", selected.size > 0);
  document.querySelectorAll(".select-entry").forEach((cb) => {
    const card = document.querySelector(`[data-card="${cb.dataset.id}"]`);
    if (card) card.classList.toggle("selected", cb.checked);
  });
}

async function runBulk(action, ids) {
  if (!ids.length) return;
  let res;
  try {
    res = await fetch("/entries/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ids }),
    });
  } catch (e) {
    alert("Error de red");
    return;
  }
  if (!res.ok) {
    alert("La accion fallo");
    return;
  }
  if (action === "delete") {
    ids.forEach((id) => {
      const card = document.querySelector(`[data-card="${id}"]`);
      if (card) card.remove();
      selected.delete(String(id));
    });
  } else {
    const status = action === "publish" ? "published" : "draft";
    ids.forEach((id) => {
      const span = document.querySelector(`[data-status="${id}"]`);
      if (span) span.textContent = status;
    });
  }
  refreshBar();
}

function askDelete(ids) {
  pendingDelete = ids;
  modalText.textContent = "Eliminar " + ids.length + " entrada(s)";
  overlay.classList.add("visible");
}

// Checkboxes por tarjeta.
document.querySelectorAll(".select-entry").forEach((cb) => {
  cb.addEventListener("change", () => {
    if (cb.checked) selected.add(cb.dataset.id);
    else selected.delete(cb.dataset.id);
    refreshBar();
  });
});

// Seleccionar todo.
document.getElementById("select-all").addEventListener("change", (e) => {
  document.querySelectorAll(".select-entry").forEach((cb) => {
    cb.checked = e.target.checked;
    if (cb.checked) selected.add(cb.dataset.id);
    else selected.delete(cb.dataset.id);
  });
  refreshBar();
});

// Botones por tarjeta (action de 1 id).
document.querySelectorAll(".card button[data-action]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.id;
    if (btn.dataset.action === "delete") askDelete([id]);
    else runBulk(btn.dataset.action, [id]);
  });
});

// Barra de acciones masivas.
document.querySelectorAll("#bulk-bar button[data-bulk]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (btn.dataset.bulk === "delete") askDelete(ids);
    else runBulk(btn.dataset.bulk, ids);
  });
});

// Modal.
document.getElementById("modal-cancel").addEventListener("click", () => {
  pendingDelete = null;
  overlay.classList.remove("visible");
});
document.getElementById("modal-confirm").addEventListener("click", () => {
  const ids = pendingDelete || [];
  overlay.classList.remove("visible");
  pendingDelete = null;
  runBulk("delete", ids);
});
