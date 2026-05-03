"use strict";
let items = [];
let currentIndex = 0;
let hlsInstance = null; // HLS.js インスタンス（画面遷移時に破棄が必要）
// オーバーレイ・UI要素を生成して body に追加
const overlay = document.createElement('div');
overlay.id = 'lb-overlay';
const content = document.createElement('div');
content.id = 'lb-content';
const closeBtn = document.createElement('button');
closeBtn.id = 'lb-close';
closeBtn.setAttribute('aria-label', '閉じる');
closeBtn.innerHTML = '&times;';
const prevBtn = document.createElement('button');
prevBtn.id = 'lb-prev';
prevBtn.setAttribute('aria-label', '前へ');
prevBtn.innerHTML = '&#10094;';
const nextBtn = document.createElement('button');
nextBtn.id = 'lb-next';
nextBtn.setAttribute('aria-label', '次へ');
nextBtn.innerHTML = '&#10095;';
overlay.appendChild(closeBtn);
overlay.appendChild(prevBtn);
overlay.appendChild(content);
overlay.appendChild(nextBtn);
document.body.appendChild(overlay);
function open(index) {
    currentIndex = index;
    render();
    overlay.classList.add('lb-open');
    document.body.style.overflow = 'hidden'; // 背景スクロールを抑制
}
function close() {
    if (hlsInstance) {
        hlsInstance.destroy();
        hlsInstance = null;
    }
    overlay.classList.remove('lb-open');
    document.body.style.overflow = '';
    content.innerHTML = '';
}
function render() {
    if (hlsInstance) {
        hlsInstance.destroy();
        hlsInstance = null;
    }
    content.innerHTML = '';
    const item = items[currentIndex];
    if (item.type === 'video' || item.type === 'html5video') {
        const video = document.createElement('video');
        video.controls = true;
        video.autoplay = true;
        video.setAttribute('playsinline', ''); // iOS Safari でネイティブプレイヤーを開かずインライン再生
        if (item.href.endsWith('.m3u8')) {
            // HLS: ブラウザが非対応なら HLS.js を使用、Safari は Native HLS で再生
            if (typeof Hls !== 'undefined' && Hls.isSupported()) {
                hlsInstance = new Hls();
                hlsInstance.loadSource(item.href);
                hlsInstance.attachMedia(video);
            }
            else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                video.src = item.href;
            }
        }
        else {
            video.src = item.href;
        }
        content.appendChild(video);
    }
    else {
        const img = document.createElement('img');
        img.src = item.href;
        content.appendChild(img);
    }
    // 端のアイテムでは前後ボタンを非表示
    prevBtn.style.visibility = currentIndex === 0 ? 'hidden' : 'visible';
    nextBtn.style.visibility = currentIndex === items.length - 1 ? 'hidden' : 'visible';
}
function prev() {
    if (currentIndex > 0)
        open(currentIndex - 1);
}
function next() {
    if (currentIndex < items.length - 1)
        open(currentIndex + 1);
}
closeBtn.addEventListener('click', close);
// オーバーレイ背景クリックで閉じる
overlay.addEventListener('click', (e) => {
    if (e.target === overlay)
        close();
});
prevBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    prev();
});
nextBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    next();
});
// キーボード操作
document.addEventListener('keydown', (e) => {
    if (!overlay.classList.contains('lb-open'))
        return;
    if (e.key === 'Escape')
        close();
    if (e.key === 'ArrowLeft')
        prev();
    if (e.key === 'ArrowRight')
        next();
});
// data-fancybox 属性を持つリンクのクリックをインターセプト
document.addEventListener('click', (e) => {
    if (document.body.classList.contains('edit-mode'))
        return;
    const a = e.target.closest('a[data-fancybox]');
    if (!a)
        return;
    e.preventDefault();
    const group = a.dataset.fancybox;
    const allLinks = Array.from(document.querySelectorAll(`a[data-fancybox="${group}"]`));
    items = allLinks.map((el) => { var _a; return ({ href: el.href, type: (_a = el.dataset.type) !== null && _a !== void 0 ? _a : 'image' }); });
    open(allLinks.indexOf(a));
});
//# sourceMappingURL=lightbox.js.map