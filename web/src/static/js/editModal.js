let initialized = false;

export async function onOpenEdit({ id, title, onSave }) {
  if (!initialized) {
    await initModal();
    initialized = true;
  }

  const modal = document.getElementById("edit-modal");
  const titleInput = modal.querySelector("#edit-title");
  titleInput.value = title ?? "";

  modal.classList.add("modal-open");

  modal.querySelector(".btn.save").onclick = async () => {
    await onSave({ title: titleInput.value });
    modal.classList.remove("modal-open");
  };

  modal.querySelector(".btn.cancel").onclick = () => {
    modal.classList.remove("modal-open");
  };
}

async function initModal() {
  const res = await fetch("/editModal.html");
  const html = await res.text();
  document.body.insertAdjacentHTML("beforeend", html);
}
