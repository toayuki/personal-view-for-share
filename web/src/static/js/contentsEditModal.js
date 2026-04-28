import { buildFormModal } from './modal.js';
let modal = null;
function initModal() {
    modal = buildFormModal({
        id: 'edit-modal',
        icon: '✎',
        title: 'Edit',
        bodyHTML: `
      <div class="edit-fields">
        <label class="edit-label">Title</label>
        <input id="edit-title" type="text" class="edit-input">
      </div>
    `,
    });
}
export function onOpenEdit({ id, title, onSave }) {
    if (!modal)
        initModal();
    const titleInput = modal.querySelector('#edit-title');
    titleInput.value = title !== null && title !== void 0 ? title : '';
    modal.classList.add('modal-open');
    modal.querySelector('.btn.save').onclick = async () => {
        await onSave({ title: titleInput.value });
        modal.classList.remove('modal-open');
    };
    modal.querySelector('.btn.cancel').onclick = () => {
        modal.classList.remove('modal-open');
    };
}
//# sourceMappingURL=contentsEditModal.js.map