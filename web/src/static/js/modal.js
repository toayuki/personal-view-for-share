// /common/modal.js

let initialized = false;

export async function onOpenConfirm({ message, onOk, }) {
  console.log("xxxini", initialized)
  if (!initialized) {
    await initModal();
    initialized = true;
  }

  const modal = document.getElementById("confirm-modal");
  console.log("xxxmodal", modal)
  modal.querySelector("#confirm-modal-message").textContent = message;

  modal.classList.add("modal-open");

  modal.querySelector(".btn.delete").onclick = () => {
    modal.classList.remove("modal-open");
    onOk?.();
  };

  modal.querySelector(".btn.cancel").onclick = () => {
    modal.classList.remove("modal-open");
  };
}

async function initModal() {
  const res = await fetch("/confirmModal.html");
  const html = await res.text();
  document.body.insertAdjacentHTML("beforeend", html);
}