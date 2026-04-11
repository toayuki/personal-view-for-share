import { openNotification } from "/static/js/modal.js";

let categoryModalEl = null;

async function loadCategoryModal() {
  if (categoryModalEl) return categoryModalEl;
  const res = await fetch("/categoryModal.html");
  const text = await res.text();
  const div = document.createElement("div");
  div.innerHTML = text;
  document.body.appendChild(div);
  categoryModalEl = document.getElementById("category-modal");
  document.getElementById("category-cancel").addEventListener("click", closeCategoryModal);
  document.getElementById("category-save").addEventListener("click", saveCategoryModal);
  document.getElementById("category-image").addEventListener("change", onImageSelected);

  let savedScrollY = 0;
  categoryModalEl.querySelectorAll("input").forEach(input => {
    input.addEventListener("focus", () => { savedScrollY = window.scrollY; });
    input.addEventListener("blur", () => { setTimeout(() => window.scrollTo(0, savedScrollY), 100); });
  });

  return categoryModalEl;
}

function onImageSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const preview = document.getElementById("category-img-preview");
  const placeholder = document.getElementById("category-img-placeholder");
  const reader = new FileReader();
  reader.onload = (ev) => {
    preview.src = ev.target.result;
    preview.style.display = "block";
    placeholder.style.display = "none";
  };
  reader.readAsDataURL(file);
}

function openCategoryModal() {
  loadCategoryModal().then(modal => {
    modal.classList.add("modal-open");
  });
}

function closeCategoryModal() {
  if (!categoryModalEl) return;
  categoryModalEl.classList.remove("modal-open");
  document.getElementById("category-name").value = "";
  document.getElementById("category-description").value = "";
  const imageInput = document.getElementById("category-image");
  imageInput.value = "";
  const preview = document.getElementById("category-img-preview");
  preview.src = "";
  preview.style.display = "none";
  document.getElementById("category-img-placeholder").style.display = "";
  const err = document.getElementById("category-error");
  err.style.display = "none";
  err.textContent = "";
}

async function saveCategoryModal() {
  const nameEl = document.getElementById("category-name");
  const descEl = document.getElementById("category-description");
  const imageEl = document.getElementById("category-image");
  const errEl = document.getElementById("category-error");
  const name = nameEl.value.trim();
  const description = descEl.value.trim();
  if (!name) {
    errEl.textContent = "カテゴリ名を入力してください";
    errEl.style.display = "block";
    return;
  }
  const formData = new FormData();
  formData.append("name", name);
  formData.append("description", description);
  if (imageEl.files[0]) {
    formData.append("image", imageEl.files[0]);
  }
  const res = await fetch("/categories", { method: "POST", body: formData });
  if (res.ok) {
    const data = await res.json();
    closeCategoryModal();
    addCategorySlide(data.id, name, description, data.image_file_name ?? null);
    openAddContentPrompt();
  } else {
    errEl.textContent = "登録に失敗しました";
    errEl.style.display = "block";
  }
}

function addCategorySlide(id, name, description, imageFileName) {
  const slidesEl = document.querySelector(".slideshow .slides");
  if (!slidesEl) {
    location.reload();
    return;
  }

  // テンプレートをクローンしてデータを流し込む
  const tpl = document.getElementById("category-slide-tpl");
  const slide = tpl.content.cloneNode(true).querySelector(".slide");
  slide.querySelector(".title").textContent = name;
  const descEl = slide.querySelector(".text");
  if (description) {
    descEl.textContent = description;
    descEl.style.display = "";
  }
  slide.querySelector(".btn").href = `${id}.html`;
  const deleteBtn = slide.querySelector(".category-delete-btn");
  deleteBtn.dataset.categoryId = id;
  const imageContainer = slide.querySelector(".image-container");
  if (imageFileName) {
    const img = slide.querySelector(".image");
    img.src = `/personal-web/categories/${id}/img/${imageFileName}`;
    img.style.display = "";
    imageContainer.classList.remove("default-category-bg");
  }

  // add-category スライドの直前に挿入
  const addSlide = slidesEl.querySelector(".slide-add-category");
  slidesEl.insertBefore(slide, addSlide);

  // ページネーション項目を追加（add-category 項目の直前）
  const pagination = document.querySelector(".slideshow .pagination");
  const newItem = document.createElement("div");
  newItem.className = "item";
  const icon = document.createElement("span");
  icon.className = "icon";
  newItem.appendChild(icon);
  pagination.insertBefore(newItem, pagination.lastElementChild);

  // 全項目の番号を振り直す
  [...pagination.children].forEach((item, i) => {
    item.querySelector(".icon").textContent = i + 1;
  });

  // クリックハンドラを登録
  newItem.addEventListener("click", function () {
    // eslint-disable-next-line no-undef
    slideshowSwitch($(this).closest(".slideshow"), $(this).index());
  });

  // 追加したスライドへ移動
  // eslint-disable-next-line no-undef
  slideshowSwitch($(".slideshow"), $(slide).index(), false);
}

function openAddContentPrompt() {
  openNotification({ message: "追加しました。", detail: "コンテンツを追加しましょう！" });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("add-category-btn");
  if (btn) btn.addEventListener("click", openCategoryModal);
});
