import { buildFormModal, openNotificationModal, openConfirmModal } from '/static/js/modal.js';

let editModalEl = null;
let currentCategoryId = null;

function initEditModal() {
  editModalEl = buildFormModal({
    id: 'category-edit-modal',
    icon: '<i class="fa-solid fa-pen"></i>',
    title: 'カテゴリを編集',
    bodyHTML: `
      <div class="edit-fields">
        <label class="edit-label">カテゴリ名</label>
        <input id="edit-category-name" type="text" class="edit-input" placeholder="例: latte">
      </div>
      <div class="edit-fields">
        <label class="edit-label">説明（任意）</label>
        <input id="edit-category-description" type="text" class="edit-input" placeholder="カテゴリの説明">
      </div>
      <div class="edit-fields">
        <label class="edit-label">写真（任意）</label>
        <label class="category-img-upload-label" for="edit-category-image">
          <span id="edit-category-img-placeholder"><i class="fa-solid fa-image"></i> ファイルを選択</span>
          <img id="edit-category-img-preview" style="display:none;">
        </label>
        <input id="edit-category-image" type="file" accept="image/*" style="display:none;">
      </div>
      <div class="edit-fields">
        <label class="edit-label">背景動画（任意）</label>
        <label class="category-img-upload-label" for="edit-category-bg-video">
          <span id="edit-category-video-placeholder"><i class="fa-solid fa-film"></i> 動画を選択</span>
          <video id="edit-category-video-preview" style="display:none;width:100%;height:100%;object-fit:cover;" muted playsinline></video>
        </label>
        <input id="edit-category-bg-video" type="file" accept="video/*" style="display:none;">
      </div>
    `,
  });

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn delete-action';
  deleteBtn.innerHTML = '<span class="btn-inner">削除</span>';
  editModalEl.querySelector('.actions').append(deleteBtn);

  editModalEl.querySelector('.btn.cancel').addEventListener('click', closeEditModal);
  editModalEl.querySelector('.btn.save').addEventListener('click', saveEditModal);
  editModalEl.querySelector('.btn.delete-action').addEventListener('click', onDeleteClick);
  editModalEl.querySelector('#edit-category-image').addEventListener('change', onImageSelected);
  editModalEl.querySelector('#edit-category-bg-video').addEventListener('change', onVideoSelected);

  let savedScrollY = 0;
  editModalEl.querySelectorAll('input').forEach(input => {
    input.addEventListener('focus', () => { savedScrollY = window.scrollY; });
    input.addEventListener('blur', () => { setTimeout(() => window.scrollTo(0, savedScrollY), 100); });
  });
}

function onImageSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const preview = editModalEl.querySelector('#edit-category-img-preview');
  const placeholder = editModalEl.querySelector('#edit-category-img-placeholder');
  const reader = new FileReader();
  reader.onload = (ev) => {
    preview.src = ev.target.result;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
  };
  reader.readAsDataURL(file);
}

function onVideoSelected(e) {
  const file = e.target.files[0];
  if (!file) return;
  const preview = editModalEl.querySelector('#edit-category-video-preview');
  const placeholder = editModalEl.querySelector('#edit-category-video-placeholder');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  placeholder.style.display = 'none';
}

function openEditModal({ categoryId, name, description, imageFileName }) {
  if (!editModalEl) initEditModal();
  currentCategoryId = categoryId;

  editModalEl.querySelector('#edit-category-name').value = name || '';
  editModalEl.querySelector('#edit-category-description').value = description || '';

  const preview = editModalEl.querySelector('#edit-category-img-preview');
  const placeholder = editModalEl.querySelector('#edit-category-img-placeholder');
  if (imageFileName) {
    preview.src = `/personal-web/categories/${categoryId}/bg/${imageFileName}`;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
  } else {
    preview.src = '';
    preview.style.display = 'none';
    placeholder.style.display = '';
  }

  const err = editModalEl.querySelector('.modal-error');
  err.style.display = 'none';
  err.textContent = '';

  editModalEl.classList.add('modal-open');
}

function closeEditModal() {
  if (!editModalEl) return;
  editModalEl.classList.remove('modal-open');
  currentCategoryId = null;
  editModalEl.querySelector('#edit-category-image').value = '';
  const videoPreview = editModalEl.querySelector('#edit-category-video-preview');
  videoPreview.src = '';
  videoPreview.style.display = 'none';
  editModalEl.querySelector('#edit-category-video-placeholder').style.display = '';
  editModalEl.querySelector('#edit-category-bg-video').value = '';
}

async function saveEditModal() {
  const nameEl = editModalEl.querySelector('#edit-category-name');
  const descEl = editModalEl.querySelector('#edit-category-description');
  const imageEl = editModalEl.querySelector('#edit-category-image');
  const videoEl = editModalEl.querySelector('#edit-category-bg-video');
  const errEl = editModalEl.querySelector('.modal-error');

  const name = nameEl.value.trim();
  const description = descEl.value.trim();
  if (!name) {
    errEl.textContent = 'カテゴリ名を入力してください';
    errEl.style.display = 'block';
    return;
  }

  // TODO: Cloudflare Tunnelの100MB上限を回避するためチャンク分割アップロードに変更する
  const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
  if (videoEl.files[0] && videoEl.files[0].size > MAX_VIDEO_BYTES) {
    errEl.textContent = '動画ファイルが大きすぎます（上限100MB）。短い動画を選択してください。※今後この制限は撤廃予定です。';
    errEl.style.display = 'block';
    return;
  }

  const formData = new FormData();
  formData.append('name', name);
  formData.append('description', description);
  // files[0] はメタ情報＋ファイルシステム参照のみ。バイナリはまだメモリに載らない
  if (imageEl.files[0]) formData.append('image', imageEl.files[0]);
  if (videoEl.files[0]) formData.append('video', videoEl.files[0]);

  const res = await fetch(`/categories/${currentCategoryId}`, { method: 'PATCH', body: formData });
  if (!res.ok) {
    errEl.textContent = '更新に失敗しました';
    errEl.style.display = 'block';
    return;
  }

  const data = await res.json();
  const slide = document.querySelector(`.category-edit-btn[data-category-id="${currentCategoryId}"]`)?.closest('.slide');
  if (slide) {
    slide.querySelector('.title').textContent = name;
    const descDom = slide.querySelector('.text');
    descDom.textContent = description;
    descDom.style.display = description ? '' : 'none';

    if (data.image_file_name) {
      const img = slide.querySelector('.image');
      img.src = `/personal-web/categories/${currentCategoryId}/bg/${data.image_file_name}`;
      img.style.display = '';
      slide.querySelector('.image-container').classList.remove('default-category-bg');
    }

    const editBtn = slide.querySelector('.category-edit-btn');
    editBtn.dataset.name = name;
    editBtn.dataset.description = description;
    if (data.image_file_name) editBtn.dataset.imageFileName = data.image_file_name;
  }

  closeEditModal();
  openNotificationModal({ message: '更新しました。' });
}

function waitForSlideshow(el) {
  return new Promise(resolve => {
    if (!el.data('wait')) { resolve(); return; }
    const id = setInterval(() => { if (!el.data('wait')) { clearInterval(id); resolve(); } }, 50);
  });
}

async function onDeleteClick() {
  const categoryId = currentCategoryId;
  closeEditModal();
  await openConfirmModal({
    message: 'このカテゴリを削除しますか？',
    onOk: async () => {
      const slide = document.querySelector(`.category-edit-btn[data-category-id="${categoryId}"]`)?.closest('.slide');
      const slideIndex = slide ? [...document.querySelectorAll('.slides .slide')].indexOf(slide) : -1;
      const res = await fetch(`/categories/${categoryId}`, { method: 'DELETE' });
      if (!res.ok) return;
      openNotificationModal({ message: '削除しました。' });
      document.querySelector(`#g_navi a[href="${categoryId}.html"]`)?.closest('li')?.remove();
      document.querySelector('.arrow.next')?.click();
      // eslint-disable-next-line no-undef
      await waitForSlideshow($('.slideshow'));
      slide?.remove();
      if (slideIndex >= 0) document.querySelectorAll('.pagination .item')[slideIndex]?.remove();
    },
  });
}

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.category-edit-btn');
  if (!btn) return;
  e.stopPropagation();
  openEditModal({
    categoryId: btn.dataset.categoryId,
    name: btn.dataset.name,
    description: btn.dataset.description,
    imageFileName: btn.dataset.imageFileName,
  });
});
