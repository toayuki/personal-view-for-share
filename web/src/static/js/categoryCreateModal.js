import { openNotificationModal } from '/static/js/modal.js';
import { buildFormModal } from '/static/js/modal.js';

let categoryModalEl = null;

/** モーダルを初回生成してイベントを登録する */
function initCategoryModal() {
  categoryModalEl = buildFormModal({
    id: 'category-modal',
    icon: '<i class="fa-solid fa-folder-plus"></i>',
    title: 'カテゴリを追加',
    bodyHTML: `
      <div class="edit-fields">
        <label class="edit-label">カテゴリ名</label>
        <input id="category-name" type="text" class="edit-input" placeholder="例: latte">
      </div>
      <div class="edit-fields">
        <label class="edit-label">説明（任意）</label>
        <input id="category-description" type="text" class="edit-input" placeholder="カテゴリの説明">
      </div>
      <div class="edit-fields">
        <label class="edit-label">写真（任意）</label>
        <label class="category-img-upload-label" for="category-image">
          <span id="category-img-placeholder"><i class="fa-solid fa-image"></i> ファイルを選択</span>
          <img id="category-img-preview" style="display:none;">
        </label>
        <input id="category-image" type="file" accept="image/*" style="display:none;">
      </div>
    `,
  });

  categoryModalEl.querySelector('.btn.cancel').addEventListener('click', closeCategoryModal);
  categoryModalEl.querySelector('.btn.save').addEventListener('click', saveCategoryModal);
  categoryModalEl.querySelector('#category-image').addEventListener('change', onImageSelected);

  // iOSはinputフォーカス時にソフトキーボードが開きスクロール位置がずれるため、
  // focus時に位置を保存し、blur時に元の位置へ復元する。
  // 100ms遅延はキーボード収納アニメーション完了前にscrollToを呼ぶと無効になるため。
  let savedScrollY = 0;
  categoryModalEl.querySelectorAll('input').forEach(input => {
    input.addEventListener('focus', () => { savedScrollY = window.scrollY; });
    input.addEventListener('blur', () => { setTimeout(() => window.scrollTo(0, savedScrollY), 100); });
  });
}

/**
 * 画像ファイル選択時にプレビューを表示する
 * @param {Event} e
 */
function onImageSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const preview = categoryModalEl.querySelector('#category-img-preview');
  const placeholder = categoryModalEl.querySelector('#category-img-placeholder');
  const reader = new FileReader();
  reader.onload = (ev) => {
    preview.src = ev.target.result;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
  };
  reader.readAsDataURL(file);
}

/** モーダルを開く。未初期化なら初期化してから表示する */
function openCategoryModal() {
  if (!categoryModalEl) initCategoryModal();
  categoryModalEl.classList.add('modal-open');
}

/** モーダルを閉じてフォームを初期状態にリセットする */
function closeCategoryModal() {
  if (!categoryModalEl) return;
  categoryModalEl.classList.remove('modal-open');
  categoryModalEl.querySelector('#category-name').value = '';
  categoryModalEl.querySelector('#category-description').value = '';
  const imageInput = categoryModalEl.querySelector('#category-image');
  imageInput.value = '';
  const preview = categoryModalEl.querySelector('#category-img-preview');
  preview.src = '';
  preview.style.display = 'none';
  categoryModalEl.querySelector('#category-img-placeholder').style.display = '';
  const err = categoryModalEl.querySelector('.modal-error');
  err.style.display = 'none';
  err.textContent = '';
}

/** 入力内容をサーバーに送信してカテゴリを作成する */
async function saveCategoryModal() {
  const nameEl = categoryModalEl.querySelector('#category-name');
  const descEl = categoryModalEl.querySelector('#category-description');
  const imageEl = categoryModalEl.querySelector('#category-image');
  const errEl = categoryModalEl.querySelector('.modal-error');
  const name = nameEl.value.trim();
  const description = descEl.value.trim();
  if (!name) {
    errEl.textContent = 'カテゴリ名を入力してください';
    errEl.style.display = 'block';
    return;
  }
  const formData = new FormData();
  formData.append('name', name);
  formData.append('description', description);
  if (imageEl.files[0]) {
    formData.append('image', imageEl.files[0]);
  }
  const res = await fetch('/categories', { method: 'POST', body: formData });
  if (res.ok) {
    const data = await res.json();
    closeCategoryModal();
    addCategorySlide(data.id, name, description, data.image_file_name ?? null);
    openAddContentPrompt();
  } else {
    errEl.textContent = '登録に失敗しました';
    errEl.style.display = 'block';
  }
}

/**
 * 作成したカテゴリをスライドショーにDOMとして追加する
 * @param {string}      id            - カテゴリID
 * @param {string}      name          - カテゴリ名
 * @param {string}      description   - 説明文
 * @param {string|null} imageFileName - サムネイル画像ファイル名。なければnull
 */
function addCategorySlide(id, name, description, imageFileName) {
  const slidesEl = document.querySelector('.slideshow .slides');
  if (!slidesEl) {
    location.reload();
    return;
  }

  const tpl = document.getElementById('category-slide-tpl');
  const slide = tpl.content.cloneNode(true).querySelector('.slide');
  slide.querySelector('.title').textContent = name;
  const descEl = slide.querySelector('.text');
  if (description) {
    descEl.textContent = description;
    descEl.style.display = '';
  }
  slide.querySelector('.btn').href = `${id}.html`;
  const deleteBtn = slide.querySelector('.category-delete-btn');
  deleteBtn.dataset.categoryId = id;
  const imageContainer = slide.querySelector('.image-container');
  if (imageFileName) {
    const img = slide.querySelector('.image');
    img.src = `/personal-web/categories/${id}/img/${imageFileName}`;
    img.style.display = '';
    imageContainer.classList.remove('default-category-bg');
  }

  const addSlide = slidesEl.querySelector('.slide-add-category');
  slidesEl.insertBefore(slide, addSlide);

  // ページネーションに項目を追加して番号を振り直す
  const pagination = document.querySelector('.slideshow .pagination');
  const newItem = document.createElement('div');
  newItem.className = 'item';
  const icon = document.createElement('span');
  icon.className = 'icon';
  newItem.appendChild(icon);
  pagination.insertBefore(newItem, pagination.lastElementChild);

  [...pagination.children].forEach((item, i) => {
    item.querySelector('.icon').textContent = i + 1;
  });

  newItem.addEventListener('click', function () {
    // eslint-disable-next-line no-undef
    slideshowSwitch($(this).closest('.slideshow'), $(this).index());
  });

  // 追加したスライドへ移動
  // eslint-disable-next-line no-undef
  slideshowSwitch($('.slideshow'), $(slide).index(), false);
}

/** カテゴリ追加後にコンテンツ追加を促す通知を表示する */
function openAddContentPrompt() {
  openNotificationModal({ message: '追加しました。', detail: 'コンテンツを追加しましょう！' });
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('add-category-btn');
  if (btn) btn.addEventListener('click', openCategoryModal);
});
