import { openNotificationModal } from '/static/js/modal.js';

let shareModal = null;
let currentShareUrl = '';

function initShareModal() {
  document.body.insertAdjacentHTML('beforeend', `
    <div id="share-modal" class="overlay">
      <div class="modal">
        <div class="modal-icon"><i class="fa-solid fa-share-nodes"></i></div>
        <h2>共有</h2>
        <div class="share-square-btns">
          <button class="share-square-btn" id="share-qr-btn">
            <i class="fa-solid fa-qrcode"></i>
            <span>QR</span>
          </button>
          <button class="share-square-btn" id="share-link-btn">
            <i class="fa-solid fa-link"></i>
            <span>リンク</span>
          </button>
        </div>
        <div class="share-qr-container" id="share-qr-container" style="display:none;"></div>
        <div class="actions" style="margin-top:20px; justify-content:center;">
          <button class="btn cancel" id="share-modal-close">閉じる</button>
        </div>
      </div>
    </div>
  `);
  shareModal = document.getElementById('share-modal');

  shareModal.querySelector('#share-qr-btn').addEventListener('click', () => {
    const container = shareModal.querySelector('#share-qr-container');
    if (container.style.display === 'none') {
      container.style.display = 'flex';
      if (!container.dataset.generated) {
        // eslint-disable-next-line no-undef
        new QRCode(container, { text: currentShareUrl, width: 160, height: 160, colorDark: '#000000', colorLight: '#ffffff' });
        container.dataset.generated = '1';
      }
    } else {
      container.style.display = 'none';
    }
  });

  shareModal.querySelector('#share-link-btn').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(currentShareUrl);
      openNotificationModal({ message: 'リンクをコピーしました' });
    } catch {
      openNotificationModal({ message: 'コピーできませんでした', detail: currentShareUrl });
    }
  });

  shareModal.querySelector('#share-modal-close').addEventListener('click', () => {
    shareModal.classList.remove('modal-open');
  });
}

function openShareModal(categoryId) {
  if (!shareModal) initShareModal();
  currentShareUrl = `${location.origin}/${categoryId}.html`;
  const container = shareModal.querySelector('#share-qr-container');
  container.style.display = 'none';
  container.innerHTML = '';
  delete container.dataset.generated;
  shareModal.classList.add('modal-open');
}

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.category-share-btn');
  if (!btn) return;
  e.stopPropagation();
  openShareModal(btn.dataset.categoryId);
});
