import { onOpenEdit } from './contentsEditModal.js';
import { addConvertingOverlay, createGridItem, startConversionPolling } from './getList.js';
import { openConfirmModal } from './modal.js';

// グローバルナビ関連
const bnrBtn = $('#g_navi');
const $header = $('header');
const $footer = $('footer');
let scrollpos = 0; // メニューを開く直前のスクロール位置（閉じたときに復元）
let ttt = false; // メニュー開閉状態フラグ

$('.bg_bl').hide();

$(() => {
  $('.menu_btn').on('click', () => {
    const $items = $('#g_navi ul li');
    const total = $items.length;
    if (!ttt) {
      bnrBtn.addClass('nav-open');
      // メニューを開く: 各 li にアニメーション用 CSS 変数をセット（上から順にずらして表示）
      $items.each(function (index) {
        (this as HTMLElement).style.setProperty('--item-delay', index * 0.04 + 's');
        (this as HTMLElement).style.setProperty('--slide-from', -(40 + index * 25) + 'px');
      });
      const openDuration = ((total - 1) * 0.04 + 0.25) * 1000;
      bnrBtn.removeClass('nav-close').stop().fadeIn(openDuration);
      $('.bg_bl').stop().fadeIn(openDuration);
      $footer.hide();
      scrollpos = $(window).scrollTop()!;
      $('.menu_btn').addClass('opened');
      ttt = true;
    } else {
      // メニューを閉じる: 逆順の遅延で li を上に戻す
      $items.each(function (index) {
        (this as HTMLElement).style.setProperty('--item-delay', (total - 1 - index) * 0.04 + 's');
      });
      const closeDuration = ((total - 1) * 0.04 + 0.25) * 1000;
      bnrBtn
        .removeClass('nav-open')
        .addClass('nav-close')
        .stop()
        .fadeOut(closeDuration, () => {
          bnrBtn.removeClass('nav-close');
        });
      $('.bg_bl').stop().fadeOut(closeDuration);
      $footer.show();
      $('.menu_btn').removeClass('opened');
      window.scrollTo(0, scrollpos);
      ttt = false;
    }
  });
});

// index.htmlはスクロール位置に関わらず常にfixedを適用
if (document.querySelector('.slideshow')) {
  $header.addClass('fixed');
  $footer.addClass('fixed');
  document.body.style.overflow = 'hidden'; // スライドショーが全画面を占めるためページ自体のスクロールを無効化
} else {
  // iphoneでセーフエリア外の境界がわからないようにするため、スクロール位置に関わらず常にfixedを適用
  $header.addClass('fixed');
}

window.onload = () => {
  const spinner = document.getElementById('loading')!;
  spinner.classList.add('loaded');
  $('.grid').toggleClass('animated');
  $('.grid-item').each(function (index) {
    $(this).css({ 'transition-delay': 0.01 * index + 's' });
  });
};

const spinner = document.getElementById('loading')!;

document.getElementById('fileUpload')?.addEventListener('change', async (e) => {
  const files = Array.from((e.target as HTMLInputElement).files ?? []);
  if (files.length === 0) return;

  spinner.classList.remove('loaded');

  const categoryId = (document.getElementById('result') as HTMLElement)?.dataset.categoryId ?? '';
  // 複数ファイルの場合は動画変換を後でまとめて開始（defer）
  const defer = files.length > 1;
  const pendingVideoNames: string[] = [];

  for (const file of files) {
    await new Promise<void>((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      if (defer) formData.append('defer_conversion', 'true');

      const xhr = new XMLHttpRequest();

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          console.log(`アップロード中 [${file.name}]: ${percent}%`);
        }
      };

      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (data.content) {
            const result = document.getElementById('result')!;
            result.appendChild(createGridItem(data.content));
            if (data.content.file_type === 'video') {
              const li = result.lastElementChild as HTMLElement;
              if (li) addConvertingOverlay(li);
              if (defer) {
                pendingVideoNames.push(data.content.stored_file_name);
              } else {
                startConversionPolling();
              }
            }
          }
        } catch {}
        resolve();
      };

      xhr.onerror = () => {
        console.error(`アップロード失敗: ${file.name}`);
        reject();
      };
      xhr.open('POST', `/upload/${categoryId}`);
      xhr.send(formData);
    }).catch(() => {});
  }

  // defer した動画をまとめて変換開始
  if (pendingVideoNames.length > 0) {
    await fetch('/start-conversion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stored_file_names: pendingVideoNames }),
    });
    startConversionPolling();
  }

  spinner.classList.add('loaded');
});

const optionsBtn = document.getElementById('optionsBtn');

function getSelectedItems(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.grid-item.selected'));
}

// edit-mode の切り替え（選択モード）
if (optionsBtn) {
  optionsBtn.addEventListener('click', () => {
    const isEditMode = document.body.classList.toggle('edit-mode');
    optionsBtn.textContent = isEditMode ? 'done' : 'options';
    if (!isEditMode) {
      document
        .querySelectorAll('.grid-item.selected')
        .forEach((el) => el.classList.remove('selected'));
    }
  });
}

// 全選択 / 全解除トグル
const selectAllBtn = document.getElementById('selectAllBtn');
if (selectAllBtn) {
  selectAllBtn.addEventListener('click', () => {
    const allItems = document.querySelectorAll('.grid-item');
    const allSelected = [...allItems].every((el) => el.classList.contains('selected'));
    allItems.forEach((el) => el.classList.toggle('selected', !allSelected));
  });
}

// グリッドアイテムの操作（削除・強制削除・編集・選択）を一括でイベント委譲
document.addEventListener('click', async (e) => {
  const target = e.target as HTMLElement;

  const deleteLink = target.closest<HTMLElement>('.delete-link');
  if (deleteLink) {
    e.preventDefault();
    const isEditMode = document.body.classList.contains('edit-mode');
    const selectedItems = getSelectedItems();
    if (isEditMode && selectedItems.length > 0) {
      const clickedItem = deleteLink.closest<HTMLElement>('.grid-item');
      if (clickedItem && !clickedItem.classList.contains('selected'))
        clickedItem.classList.add('selected');
      const targets = getSelectedItems();
      await openConfirmModal({
        message: `${targets.length}件を削除しますか？`,
        onOk: async () => {
          for (const item of targets) {
            try {
              const res = await fetch(`/delete/${item.dataset.id}`);
              if (!res.ok) throw new Error();
              item.remove();
            } catch {
              console.error('削除に失敗しました');
            }
          }
        },
      });
    } else {
      const targetId = deleteLink.dataset.id!;
      await openConfirmModal({
        message: '本当に削除しますか？',
        onOk: async () => {
          try {
            const res = await fetch(`/delete/${targetId}`);
            if (!res.ok) throw new Error();
            deleteLink.closest('.grid-item')?.remove();
          } catch {
            console.error('削除に失敗しました');
          }
        },
      });
    }
  }

  // ファイルを含む完全削除（DBレコード + ストレージ）
  const forceDeleteLink = target.closest<HTMLElement>('.force-delete-link');
  if (forceDeleteLink) {
    e.preventDefault();
    const isEditMode = document.body.classList.contains('edit-mode');
    const selectedItems = getSelectedItems();
    if (isEditMode && selectedItems.length > 0) {
      const clickedItem = forceDeleteLink.closest<HTMLElement>('.grid-item');
      if (clickedItem && !clickedItem.classList.contains('selected'))
        clickedItem.classList.add('selected');
      const targets = getSelectedItems();
      await openConfirmModal({
        message: `ファイルを含む全データ ${targets.length}件を削除します。元に戻せません。`,
        onOk: async () => {
          for (const item of targets) {
            try {
              const res = await fetch(`/forceDelete/${item.dataset.id}`);
              if (!res.ok) throw new Error();
              item.remove();
            } catch {
              console.error('強制削除に失敗しました');
            }
          }
        },
      });
    } else {
      const targetId = forceDeleteLink.dataset.id!;
      await openConfirmModal({
        message: 'ファイルを含む全データを削除します。元に戻せません。',
        onOk: async () => {
          try {
            const res = await fetch(`/forceDelete/${targetId}`);
            if (!res.ok) throw new Error();
            forceDeleteLink.closest('.grid-item')?.remove();
          } catch {
            console.error('強制削除に失敗しました');
          }
        },
      });
    }
  }

  const editLink = target.closest<HTMLElement>('.edit-link');
  if (editLink) {
    e.preventDefault();
    await onOpenEdit({
      id: editLink.dataset.id!,
      title: editLink.dataset.title,
      onSave: async ({ title }) => {
        try {
          const res = await fetch(`/update/${editLink.dataset.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
          });
          if (!res.ok) throw new Error();
          editLink.dataset.title = title;
        } catch {
          console.error('更新に失敗しました');
        }
      },
    });
  }

  // edit-mode 中はサムネイルクリックでライトボックスを開かず選択トグル
  if (document.body.classList.contains('edit-mode')) {
    const isOptionLink = target.closest(
      '.delete-link, .force-delete-link, .edit-link, .download-link',
    );
    if (!isOptionLink) {
      const thumbnail = target.closest<HTMLElement>('.grid-item a[data-fancybox]');
      if (thumbnail) {
        e.preventDefault();
        thumbnail.closest<HTMLElement>('.grid-item')!.classList.toggle('selected');
      }
    }
  }
});

document.getElementById('logoutBtn')?.addEventListener('click', (e) => {
  e.preventDefault();
  fetch('/logout', { method: 'POST' }).then(() => {
    location.href = '/login';
  });
});
