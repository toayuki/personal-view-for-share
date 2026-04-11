// /common/modal.js

export function openNotification({ message, detail = "" }) {
  const overlay = document.createElement("div");
  overlay.className = "overlay modal-open";
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-icon"><i class="fa-solid fa-circle-check"></i></div>
      <h2>${message}</h2>
      ${detail ? `<p>${detail}</p>` : ""}
      <div class="actions">
        <button class="btn cancel">閉じる</button>
      </div>
    </div>
  `;
  overlay.querySelector("button").addEventListener("click", () => overlay.remove());
  document.body.appendChild(overlay);
}

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