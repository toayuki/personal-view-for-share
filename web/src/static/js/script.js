var _a, _b;
import { openConfirmModal } from './modal.js';
import { onOpenEdit } from './contentsEditModal.js';
import { createGridItem, startConversionPolling, addConvertingOverlay } from './getList.js';
// グローバルナビ関連
const bnrBtn = $('#g_navi');
const $header = $('header');
const $footer = $('footer');
let scrollpos = 0; // メニューを開く直前のスクロール位置（閉じたときに復元）
let ttt = false; // メニュー開閉状態フラグ
$('.bg_bl').hide();
$(function () {
    $('.menu_btn').on('click', function () {
        const $items = $('#g_navi ul li');
        const total = $items.length;
        if (!ttt) {
            bnrBtn.addClass('nav-open');
            // メニューを開く: 各 li にアニメーション用 CSS 変数をセット（上から順にずらして表示）
            $items.each(function (index) {
                this.style.setProperty('--item-delay', (index * 0.04) + 's');
                this.style.setProperty('--slide-from', -(40 + index * 25) + 'px');
            });
            const openDuration = ((total - 1) * 0.04 + 0.25) * 1000;
            bnrBtn.removeClass('nav-close').stop().fadeIn(openDuration);
            $('.bg_bl').stop().fadeIn(openDuration);
            $footer.hide();
            scrollpos = $(window).scrollTop();
            $('.menu_btn').addClass('opened');
            ttt = true;
        }
        else {
            // メニューを閉じる: 逆順の遅延で li を上に戻す
            $items.each(function (index) {
                this.style.setProperty('--item-delay', ((total - 1 - index) * 0.04) + 's');
            });
            const closeDuration = ((total - 1) * 0.04 + 0.25) * 1000;
            bnrBtn.removeClass('nav-open').addClass('nav-close').stop().fadeOut(closeDuration, function () {
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
}
else {
    // iphoneでセーフエリア外の境界がわからないようにするため、スクロール位置に関わらず常にfixedを適用
    $header.addClass('fixed');
}
window.onload = function () {
    const spinner = document.getElementById('loading');
    spinner.classList.add('loaded');
    $('.grid').toggleClass('animated');
    $('.grid-item').each(function (index) {
        $(this).css({ 'transition-delay': (0.01 * index) + 's' });
    });
};
const spinner = document.getElementById('loading');
(_a = document.getElementById('fileUpload')) === null || _a === void 0 ? void 0 : _a.addEventListener('change', async (e) => {
    var _a, _b, _c;
    const files = Array.from((_a = e.target.files) !== null && _a !== void 0 ? _a : []);
    if (files.length === 0)
        return;
    spinner.classList.remove('loaded');
    const categoryId = (_c = (_b = document.getElementById('result')) === null || _b === void 0 ? void 0 : _b.dataset.categoryId) !== null && _c !== void 0 ? _c : '';
    // 複数ファイルの場合は動画変換を後でまとめて開始（defer）
    const defer = files.length > 1;
    const pendingVideoNames = [];
    for (const file of files) {
        await new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            if (defer)
                formData.append('defer_conversion', 'true');
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
                        const result = document.getElementById('result');
                        result.appendChild(createGridItem(data.content));
                        if (data.content.file_type === 'video') {
                            const li = result.lastElementChild;
                            if (li)
                                addConvertingOverlay(li);
                            if (defer) {
                                pendingVideoNames.push(data.content.stored_file_name);
                            }
                            else {
                                startConversionPolling();
                            }
                        }
                    }
                }
                catch (_a) { }
                resolve();
            };
            xhr.onerror = () => { console.error(`アップロード失敗: ${file.name}`); reject(); };
            xhr.open('POST', `/upload/${categoryId}`);
            xhr.send(formData);
        }).catch(() => { });
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
function getSelectedItems() {
    return Array.from(document.querySelectorAll('.grid-item.selected'));
}
// edit-mode の切り替え（選択モード）
if (optionsBtn) {
    optionsBtn.addEventListener('click', () => {
        const isEditMode = document.body.classList.toggle('edit-mode');
        optionsBtn.textContent = isEditMode ? 'done' : 'options';
        if (!isEditMode) {
            document.querySelectorAll('.grid-item.selected').forEach(el => el.classList.remove('selected'));
        }
    });
}
// 全選択 / 全解除トグル
const selectAllBtn = document.getElementById('selectAllBtn');
if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
        const allItems = document.querySelectorAll('.grid-item');
        const allSelected = [...allItems].every(el => el.classList.contains('selected'));
        allItems.forEach(el => el.classList.toggle('selected', !allSelected));
    });
}
// グリッドアイテムの操作（削除・強制削除・編集・選択）を一括でイベント委譲
document.addEventListener('click', async (e) => {
    const target = e.target;
    const deleteLink = target.closest('.delete-link');
    if (deleteLink) {
        e.preventDefault();
        const isEditMode = document.body.classList.contains('edit-mode');
        const selectedItems = getSelectedItems();
        if (isEditMode && selectedItems.length > 0) {
            const clickedItem = deleteLink.closest('.grid-item');
            if (clickedItem && !clickedItem.classList.contains('selected'))
                clickedItem.classList.add('selected');
            const targets = getSelectedItems();
            await openConfirmModal({
                message: `${targets.length}件を削除しますか？`,
                onOk: async () => {
                    for (const item of targets) {
                        try {
                            const res = await fetch(`/delete/${item.dataset.id}`);
                            if (!res.ok)
                                throw new Error();
                            item.remove();
                        }
                        catch (_a) {
                            console.error('削除に失敗しました');
                        }
                    }
                },
            });
        }
        else {
            const targetId = deleteLink.dataset.id;
            await openConfirmModal({
                message: '本当に削除しますか？',
                onOk: async () => {
                    var _a;
                    try {
                        const res = await fetch(`/delete/${targetId}`);
                        if (!res.ok)
                            throw new Error();
                        (_a = deleteLink.closest('.grid-item')) === null || _a === void 0 ? void 0 : _a.remove();
                    }
                    catch (_b) {
                        console.error('削除に失敗しました');
                    }
                },
            });
        }
    }
    // ファイルを含む完全削除（DBレコード + ストレージ）
    const forceDeleteLink = target.closest('.force-delete-link');
    if (forceDeleteLink) {
        e.preventDefault();
        const isEditMode = document.body.classList.contains('edit-mode');
        const selectedItems = getSelectedItems();
        if (isEditMode && selectedItems.length > 0) {
            const clickedItem = forceDeleteLink.closest('.grid-item');
            if (clickedItem && !clickedItem.classList.contains('selected'))
                clickedItem.classList.add('selected');
            const targets = getSelectedItems();
            await openConfirmModal({
                message: `ファイルを含む全データ ${targets.length}件を削除します。元に戻せません。`,
                onOk: async () => {
                    for (const item of targets) {
                        try {
                            const res = await fetch(`/forceDelete/${item.dataset.id}`);
                            if (!res.ok)
                                throw new Error();
                            item.remove();
                        }
                        catch (_a) {
                            console.error('強制削除に失敗しました');
                        }
                    }
                },
            });
        }
        else {
            const targetId = forceDeleteLink.dataset.id;
            await openConfirmModal({
                message: 'ファイルを含む全データを削除します。元に戻せません。',
                onOk: async () => {
                    var _a;
                    try {
                        const res = await fetch(`/forceDelete/${targetId}`);
                        if (!res.ok)
                            throw new Error();
                        (_a = forceDeleteLink.closest('.grid-item')) === null || _a === void 0 ? void 0 : _a.remove();
                    }
                    catch (_b) {
                        console.error('強制削除に失敗しました');
                    }
                },
            });
        }
    }
    const editLink = target.closest('.edit-link');
    if (editLink) {
        e.preventDefault();
        await onOpenEdit({
            id: editLink.dataset.id,
            title: editLink.dataset.title,
            onSave: async ({ title }) => {
                try {
                    const res = await fetch(`/update/${editLink.dataset.id}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ title }),
                    });
                    if (!res.ok)
                        throw new Error();
                    editLink.dataset.title = title;
                }
                catch (_a) {
                    console.error('更新に失敗しました');
                }
            },
        });
    }
    // edit-mode 中はサムネイルクリックでライトボックスを開かず選択トグル
    if (document.body.classList.contains('edit-mode')) {
        const isOptionLink = target.closest('.delete-link, .force-delete-link, .edit-link, .download-link');
        if (!isOptionLink) {
            const thumbnail = target.closest('.grid-item a[data-fancybox]');
            if (thumbnail) {
                e.preventDefault();
                thumbnail.closest('.grid-item').classList.toggle('selected');
            }
        }
    }
});
(_b = document.getElementById('logoutBtn')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', e => {
    e.preventDefault();
    fetch('/logout', { method: 'POST' }).then(() => { location.href = '/login'; });
});
//# sourceMappingURL=script.js.map