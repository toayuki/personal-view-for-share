import { openNotificationModal } from '/static/js/modal.js';

let shareModal = null;
let currentShareUrl = '';

function initShareModal() {
  document.body.insertAdjacentHTML('beforeend', `
    <div id="share-modal" class="overlay">
      <div class="modal">
        <div class="modal-icon"><i class="fa-solid fa-share-nodes"></i></div>
        <h2>share</h2>
        <p id="share-modal-status" style="font-size:11px; color:var(--color-modal-sub); margin:12px 0 0;"></p>
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
          <button class="btn cancel" id="share-modal-close"><span class="btn-inner">閉じる</span></button>
        </div>
      </div>
    </div>
  `);
  shareModal = document.getElementById('share-modal');

  shareModal.querySelector('#share-qr-btn').addEventListener('click', () => {
    if (!currentShareUrl) return;
    const container = shareModal.querySelector('#share-qr-container');
    if (container.style.display === 'none') {
      container.style.display = 'flex';
      if (!container.dataset.generated) {
        const qrWrap = document.createElement('div');
        qrWrap.style.cssText = 'position:relative; display:inline-block; line-height:0;';
        container.appendChild(qrWrap);
        // eslint-disable-next-line no-undef
        new QRCode(qrWrap, { text: currentShareUrl, width: 160, height: 160, colorDark: '#000000', colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.H });
        // -- QR中央ラベル（不要な場合は以下の3行をコメントアウト） --
        // const labelEl = document.createElement('div');
        // labelEl.textContent = 'share with you';
        // labelEl.style.cssText = 'position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); background:#fff; padding:6px 10px; font-size:8px; letter-spacing:0.05em; white-space:nowrap; font-family:sans-serif; color:#000; line-height:1; border-radius:50%;';
        // qrWrap.appendChild(labelEl);
        // --------------------------------------------------------
        container.dataset.generated = '1';
      }
    } else {
      container.style.display = 'none';
    }
  });

  shareModal.querySelector('#share-link-btn').addEventListener('click', async () => {
    if (!currentShareUrl) return;
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

async function openShareModal(categoryId) {
  if (!shareModal) initShareModal();
  currentShareUrl = '';
  const container = shareModal.querySelector('#share-qr-container');
  container.style.display = 'none';
  container.innerHTML = '';
  delete container.dataset.generated;
  const status = shareModal.querySelector('#share-modal-status');
  status.textContent = '招待リンクを生成中...';
  shareModal.classList.add('modal-open');

  try {
    const res = await fetch('/invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_id: categoryId }),
    });
    if (res.ok) {
      const data = await res.json();
      currentShareUrl = data.url;
      status.textContent = '24時間有効な招待リンクを発行しました';
    } else {
      status.textContent = '招待リンクの生成に失敗しました';
    }
  } catch {
    status.textContent = '招待リンクの生成に失敗しました';
  }
}

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.category-share-btn');
  if (!btn) return;
  e.stopPropagation();
  openShareModal(btn.dataset.categoryId);
});
