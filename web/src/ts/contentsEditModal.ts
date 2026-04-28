import { buildFormModal } from './modal.js';

interface EditOptions {
  id: string;
  title?: string;
  onSave: (data: { title: string }) => void | Promise<void>;
}

let modal: HTMLElement | null = null;

function initModal(): void {
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

export function onOpenEdit({ id, title, onSave }: EditOptions): void {
  if (!modal) initModal();

  const titleInput = modal!.querySelector<HTMLInputElement>('#edit-title')!;
  titleInput.value = title ?? '';

  modal!.classList.add('modal-open');

  (modal!.querySelector('.btn.save') as HTMLButtonElement).onclick = async () => {
    await onSave({ title: titleInput.value });
    modal!.classList.remove('modal-open');
  };

  (modal!.querySelector('.btn.cancel') as HTMLButtonElement).onclick = () => {
    modal!.classList.remove('modal-open');
  };
}
