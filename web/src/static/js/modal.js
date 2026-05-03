/**
 * モーダルのDOM構造を生成してbodyに追加し、overlay要素を返す。
 * 表示は行わない（modal-openは付けない）。
 * 呼び出し側が返り値を保持し、必要なタイミングでclassList.add('modal-open')して表示する。
 * フォームなど何度も開閉するモーダルに使う。
 */
export function buildFormModal({ id, icon = null, title, bodyHTML, }) {
    const iconHTML = icon != null ? `<div class="modal-icon">${icon}</div>` : '';
    document.body.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="overlay">
      <div class="modal">
        ${iconHTML}
        <h2>${title}</h2>
        ${bodyHTML}
        <p class="modal-error" style="display:none;"></p>
        <div class="actions">
          <button class="btn save"><span class="btn-inner">保存</span></button>
          <button class="btn cancel"><span class="btn-inner">キャンセル</span></button>
        </div>
      </div>
    </div>
  `);
    return document.getElementById(id);
}
/**
 * 通知モーダルを生成・即表示し、閉じたらDOMから破棄する。
 * 表示のたびに新しい要素を生成する使い捨て方式。
 * 操作完了後の成功通知など、一度表示すれば不要になるケースに使う。
 */
export function openNotificationModal({ message, detail = '' }) {
    const overlay = document.createElement('div');
    overlay.className = 'overlay modal-open';
    overlay.innerHTML = `
    <div class="modal">
      <div class="modal-icon"><i class="fa-solid fa-circle-check"></i></div>
      <h2>${message}</h2>
      ${detail ? `<p>${detail}</p>` : ''}
      <div class="actions">
        <button class="btn cancel"><span class="btn-inner">閉じる</span></button>
      </div>
    </div>
  `;
    overlay.querySelector('button').addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
}
let confirmModal = null;
export function openConfirmModal({ message, onOk }) {
    if (!confirmModal) {
        document.body.insertAdjacentHTML('beforeend', `
      <div id="confirm-modal" class="overlay">
        <div class="modal">
          <div class="modal-icon">!</div>
          <h2>削除</h2>
          <p id="confirm-modal-message"></p>
          <div class="actions">
            <button class="btn delete"><span class="btn-inner">削除</span></button>
            <button class="btn cancel"><span class="btn-inner">キャンセル</span></button>
          </div>
        </div>
      </div>
    `);
        confirmModal = document.getElementById('confirm-modal');
    }
    confirmModal.querySelector('#confirm-modal-message').textContent = message;
    confirmModal.classList.add('modal-open');
    confirmModal.querySelector('.btn.delete').onclick = () => {
        confirmModal.classList.remove('modal-open');
        onOk === null || onOk === void 0 ? void 0 : onOk();
    };
    confirmModal.querySelector('.btn.cancel').onclick = () => {
        confirmModal.classList.remove('modal-open');
    };
}
//# sourceMappingURL=modal.js.map