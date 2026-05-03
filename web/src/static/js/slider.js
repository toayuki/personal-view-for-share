import { initBgVideo } from './videoBackground.js';
// スライドが表示される最低時間（ミリ秒）。自動再生のインターバルとして使う
const slideshowDuration = 1500;
/**
 * 動画スライドの再生ヘルパー。
 * video._bgReady フラグで「initBgVideo をすでに呼んだか」を管理し、
 * 同じ動画に対して initBgVideo が二重実行されないようにしている。
 * @param slide - 対象の .slide 要素
 */
function playSlideVideo(slide) {
    const video = slide.querySelector('.slide-video');
    if (!video)
        return;
    if (video._bgReady) {
        // すでに初期化済み: そのまま再生だけ行う
        video.play().catch(() => { });
        return;
    }
    // 初回のみ initBgVideo（videoBackground.ts）を呼び出してフェード処理を設定する
    video._bgReady = true;
    const img = slide.querySelector('.image'); // フォールバック用の静止画
    const fadeEl = slide.querySelector('.slide-video-fade'); // 動画末尾のフェードオーバーレイ
    initBgVideo(video, {
        fadeEl,
        onSuccess: () => {
            if (img)
                img.style.display = 'none';
        },
        onFail: () => {
            video.style.display = 'none';
            if (fadeEl)
                fadeEl.style.display = 'none';
        },
    });
}
/**
 * アクティブなスライドの動画を再生し、非アクティブなスライドの動画を一時停止する。
 * スライド切り替え時に毎回呼ぶことで、不要な動画が裏で再生されるのを防ぐ。
 * @param sw - 対象の .slideshow jQuery オブジェクト
 */
function syncSlideVideos(sw) {
    sw.find('.slide').each(function () {
        const video = this.querySelector('.slide-video');
        if (!video)
            return;
        if ($(this).hasClass('is-active') || $(this).hasClass('is-prev')) {
            playSlideVideo(this);
        }
        else {
            video.pause();
        }
    });
}
/**
 * スライド切り替えメイン関数。
 * @param sw        - 対象の .slideshow jQuery オブジェクト
 * @param index     - 表示したいスライドのインデックス
 * @param auto      - 自動再生中の切り替えかどうか（true なら切り替え後に次のタイマーをセット）
 * @param direction - 'right'|'left'|undefined（undefined なら前後関係から自動判定）
 */
export function slideshowSwitch(sw, index, auto, direction) {
    // data('wait') が true の間はアニメーション中なので操作を無視する（多重トリガー防止）
    if (sw.data('wait'))
        return;
    if (!sw.data('cachedSlides'))
        sw.data('cachedSlides', sw.find('.slide'));
    const slides = sw.data('cachedSlides');
    const activeSlide = slides.filter('.is-active');
    const activeSlideImage = activeSlide.find('.image-container');
    const newSlide = slides.eq(index);
    const newSlideImage = newSlide.find('.image-container');
    const newSlideContent = newSlide.find('.slide-content');
    const newSlideElements = newSlide.find('.caption > *');
    if (newSlide.is(activeSlide))
        return;
    const timeout = sw.data('timeout');
    clearTimeout(timeout);
    sw.data('wait', true);
    if (!sw.data('cachedPages'))
        sw.data('cachedPages', sw.find('.pagination .item'));
    const pages = sw.data('cachedPages');
    pages.removeClass('is-active');
    pages.eq(index).addClass('is-active'); // ページネーションのアクティブドットを更新
    // direction が明示されない場合は、新旧スライドのDOM順序から左右を自動判定
    const slideDir = direction !== undefined ? direction : newSlide.index() > activeSlide.index() ? 'right' : 'left';
    // スライド方向を particleEffect.ts の風エフェクトに伝える
    window.dispatchEvent(new CustomEvent('windTrigger', { detail: { direction: slideDir } }));
    // 右へ進む場合と左へ進む場合で、新旧スライドの初期位置・移動先を逆にする
    // 「新スライドが右から入ってきて、古いスライドが左へ出ていく」イメージ
    let newSlideRight;
    let newSlideLeft;
    let newSlideImageRight;
    let newSlideImageLeft;
    let newSlideImageToRight;
    let newSlideImageToLeft;
    let newSlideContentLeft;
    let newSlideContentRight;
    let activeSlideImageLeft;
    if (slideDir === 'right') {
        newSlideRight = 0; // 新スライドは右端に配置
        newSlideLeft = 'auto';
        newSlideImageRight = -sw.width() / 8; // 画像は少し右にオフセット（パララックス）
        newSlideImageLeft = 'auto';
        newSlideImageToRight = 0; // アニメーション後に画像を正位置へ
        newSlideImageToLeft = 'auto';
        newSlideContentLeft = 'auto';
        newSlideContentRight = 0;
        activeSlideImageLeft = -sw.width() / 4; // 旧スライドの画像を左へ退場
    }
    else {
        newSlideRight = '';
        newSlideLeft = 0; // 新スライドは左端に配置
        newSlideImageRight = 'auto';
        newSlideImageLeft = -sw.width() / 8; // 画像は少し左にオフセット
        newSlideImageToRight = '';
        newSlideImageToLeft = 0;
        newSlideContentLeft = 0;
        newSlideContentRight = 'auto';
        activeSlideImageLeft = sw.width() / 4; // 旧スライドの画像を右へ退場
    }
    // 新スライドの初期スタイル: width:0 から展開することでワイプ効果を作る
    newSlide.css({ display: 'block', width: 0, right: newSlideRight, left: newSlideLeft, zIndex: 2 });
    // 画像コンテナはスライド幅を固定して、スライドの展開に連動してスクロールするように見せる
    newSlideImage.css({ width: sw.width(), right: newSlideImageRight, left: newSlideImageLeft });
    newSlideContent.css({
        width: sw.width(),
        left: newSlideContentLeft,
        right: newSlideContentRight,
    });
    activeSlideImage.css({ left: 0 }); // 旧スライド画像の起点をリセット（アニメーション開始基点）
    // キャプション要素をすべて y:20 に初期位置セット（後でスタッガーで上に飛ばす）
    TweenMax.set(newSlideElements, { y: 20, force3D: true });
    // アニメーション開始時点でis-activeを付け替え、旧スライドをis-prevとしてマーク
    slides.filter('.is-prev').removeClass('is-prev');
    activeSlide.addClass('is-prev');
    newSlide.addClass('is-active');
    activeSlide.removeClass('is-active');
    syncSlideVideos(sw);
    // 旧スライドの画像をパララックスで左/右に流す
    TweenMax.to(activeSlideImage, 1, { left: activeSlideImageLeft, ease: Power3.easeInOut });
    // 新スライドを width:0 → sw.width() にアニメーション（ワイプイン）
    TweenMax.to(newSlide, 1, { width: sw.width(), ease: Power3.easeInOut });
    // 新スライドの画像をパララックスオフセットから正位置へ移動（視差効果）
    TweenMax.to(newSlideImage, 1, {
        right: newSlideImageToRight,
        left: newSlideImageToLeft,
        ease: Power3.easeInOut,
    });
    // キャプション内の要素を0.1秒ずつずらして順番に浮き上がらせる（stagger）
    // delay:0.6 でワイプが終わりかけたタイミングから開始
    TweenMax.staggerFromTo(newSlideElements, 0.8, { alpha: 0, y: 60 }, { alpha: 1, y: 0, ease: Power3.easeOut, force3D: true, delay: 0.6 }, 0.1, () => {
        // ---- すべてのアニメーション完了後の後片付け ----
        // TweenMax が設定したインラインスタイルをクリアしてCSSクラスの見た目に戻す
        newSlide.css({ display: '', width: '', left: '', zIndex: '' });
        newSlideImage.css({ width: '', right: '', left: '' });
        newSlideContent.css({ width: '', left: '' });
        newSlideElements.css({ opacity: '', transform: '' });
        activeSlideImage.css({ left: '' });
        activeSlide.removeClass('is-prev');
        sw.find('.pagination').trigger('check');
        sw.data('wait', false); // 操作ロック解除
        if (auto) {
            const t = setTimeout(() => slideshowNext(sw, false, true), slideshowDuration);
            sw.data('timeout', t);
        }
    });
}
/**
 * 前後スライドへの移動。末端では折り返しループし、ループ時は direction を明示して
 * 視覚上のつながりが逆にならないようにする。
 * @param sw       - 対象の .slideshow jQuery オブジェクト
 * @param previous - true なら前のスライドへ、false なら次のスライドへ
 * @param auto     - 切り替え後に自動再生タイマーをセットするか
 */
function slideshowNext(sw, previous, auto) {
    const slides = sw.find('.slide');
    const activeSlide = slides.filter('.is-active');
    let newSlide;
    let direction;
    if (previous) {
        newSlide = activeSlide.prev('.slide');
        if (newSlide.length === 0) {
            newSlide = slides.last();
            direction = 'left';
        } // 先頭で「前へ」→ 末尾にジャンプ
    }
    else {
        newSlide = activeSlide.next('.slide');
        if (newSlide.length === 0) {
            newSlide = slides.first();
            direction = 'right';
        } // 末尾で「次へ」→ 先頭にジャンプ
    }
    slideshowSwitch(sw, newSlide.index(), auto, direction);
}
/**
 * イントロシーケンス。ページ読み込み時に全スライドを横スクロールで見せてから
 * トップスライドに戻る演出を行う。
 * @param sw         - 対象の .slideshow jQuery オブジェクト
 * @param onComplete - イントロ終了後に呼ぶコールバック（自動再生の開始など）
 */
function runIntroSequence(sw, onComplete) {
    const slides = sw.find('.slide');
    const pagination = sw.find('.pagination .item');
    // 「カテゴリ追加」用スライドはイントロに含めない
    const categorySlides = slides.filter(':not(.slide-add-category)');
    const categoryTotal = categorySlides.length;
    // スライドが1枚以下ならイントロをスキップして即完了
    if (categoryTotal <= 1) {
        $('footer, #theme-toggle').css('visibility', 'visible');
        onComplete();
        return;
    }
    // すべての .image 要素の読み込みを待ってからアニメーション開始
    // 画像が揃う前に動くと一部が空白になるため
    const images = categorySlides.find('.image').toArray();
    const loadPromises = images.map((img) => new Promise((resolve) => {
        if (img.complete) {
            resolve();
            return;
        } // すでにキャッシュ済みなら即 resolve
        img.addEventListener('load', () => resolve());
        img.addEventListener('error', () => resolve()); // 読み込み失敗でも待機を止める
    }));
    Promise.all(loadPromises).then(() => {
        const slidesContainer = sw.find('.slides');
        const w = sw.width(); // スライドショーの幅（各スライドの基準幅）
        let skipped = false; // showWelcome の多重呼び出しを防ぐフラグ
        // スキップボタンを DOM に追加
        const skipBtn = $('<div class="intro-skip-btn">skip &rsaquo;&rsaquo;</div>');
        $('body').append(skipBtn);
        // ---- イントロ終了後のクリーンアップ ----
        // アニメーションのためにインラインで設定したスタイルをすべて除去し、
        // 通常のスライドショー状態（0番スライドがアクティブ）に戻す
        function cleanup() {
            skipBtn.remove();
            sw.find('.arrows').css('visibility', '');
            sw.find('.pagination').css('visibility', '');
            $('footer, #theme-toggle').css('visibility', 'visible');
            categorySlides.each(function () {
                $(this).css({ display: '', left: '', width: '', opacity: '', zIndex: '' });
                $(this).find('.slide-content').css('visibility', '');
                $(this).find('.image-container').css('width', '');
            });
            TweenMax.set(slidesContainer, { clearProps: 'all' }); // TweenMax が設定した値もクリア
            slidesContainer.css('width', '');
            slides.removeClass('is-active');
            pagination.removeClass('is-active');
            slides.eq(0).addClass('is-active'); // 0番スライドをアクティブに戻す
            pagination.eq(0).addClass('is-active');
            onComplete();
        }
        // ---- 「Share Your Memories」ウェルカム画面の表示 ----
        // 横スクロールが終わった後、または skip 押下後に呼ばれる
        // skipped フラグで、アニメーション完了と skip 両方から呼ばれた場合の二重実行を防ぐ
        function showWelcome() {
            if (skipped)
                return;
            skipped = true;
            TweenMax.killTweensOf(slidesContainer[0]); // 進行中の横スクロールを即停止
            // スライドコンテナを最終フレーム（最後のスライドが表示されている位置）にジャンプ
            TweenMax.set(slidesContainer, { x: -(categoryTotal - 1) * w, force3D: true });
            // ウェルカムメッセージ要素を生成してスライドショー内に追加
            const welcome = $('<div class="intro-welcome"><div class="intro-welcome-text">Share Your Memories</div></div>');
            sw.find('.slideshow-inner').append(welcome);
            const welcomeText = welcome.find('.intro-welcome-text');
            // ウェルカム表示と同時に「左から右へ吹く風」エフェクトを起動
            window.dispatchEvent(new CustomEvent('windTrigger', { detail: { direction: 'left', duration: 600 } }));
            // 0.6秒で最初のスライドに戻る（x=0）
            TweenMax.to(slidesContainer, 0.6, { x: 0, ease: Power2.easeOut, force3D: true });
            // テキストをフェードイン → 0.8秒後にフェードアウト → cleanup()
            TweenMax.to(welcomeText, 0.5, {
                opacity: 1,
                delay: 0.1,
                onComplete: () => {
                    TweenMax.to(welcome, 0.5, {
                        opacity: 0,
                        ease: Power1.easeIn,
                        delay: 0.8,
                        onComplete: () => {
                            welcome.remove();
                            cleanup();
                        },
                    });
                },
            });
        }
        skipBtn.on('click', () => {
            skipBtn.hide();
            showWelcome();
        }); // スキップ時は即ウェルカム画面へ
        // イントロ中は操作 UI を隠す
        sw.find('.arrows').css('visibility', 'hidden');
        sw.find('.pagination').css('visibility', 'hidden');
        // ---- 全スライドを横に並べてスクロール準備 ----
        // slides コンテナの幅を「スライド幅 × 枚数」に広げ、各スライドを i * w の位置に配置
        // slide-content は隠したまま（タイトルなどを表示せずに画像だけ見せる）
        categorySlides.each(function (i) {
            $(this).css({ display: 'block', left: i * w, width: w, opacity: 1, zIndex: 2 });
            $(this).find('.slide-content').css('visibility', 'hidden');
            $(this).find('.image-container').css('width', w);
            playSlideVideo(this);
        });
        slidesContainer.css('width', categoryTotal * w);
        // 右向きの風を「カテゴリ数 × 400ms」の持続時間で起動
        window.dispatchEvent(new CustomEvent('windTrigger', {
            detail: { direction: 'right', duration: categoryTotal * 400 },
        }));
        // slidesContainer を「カテゴリ数 × 0.4秒」かけて左端まで流す（右スクロール演出）
        // 完了時に showWelcome() を呼ぶ
        TweenMax.to(slidesContainer, categoryTotal * 0.4, {
            x: -(categoryTotal - 1) * w,
            ease: Power2.easeInOut,
            force3D: true,
            onComplete: showWelcome,
        });
    });
}
$(document).ready(() => {
    const slideshow = $('.slideshow');
    // 全スライドに読み込み完了クラスを付与（CSS側でのフェードイン等に使う）
    $('.slide').addClass('is-loaded');
    // イントロ中はスライドのテキストと矢印を隠しておく（runIntroSequence 内でも制御するが初期化）
    slideshow.find('.slide .slide-content').css('visibility', 'hidden');
    slideshow.find('.arrows').css('visibility', 'hidden');
    syncSlideVideos(slideshow); // 初期状態でアクティブスライドの動画を再生
    // 矢印クリックで前/次スライドへ（.prev クラスがあれば前に進む）
    $('.slideshow .arrows .arrow').on('click', function () {
        slideshowNext($(this).closest('.slideshow'), $(this).hasClass('prev'), false);
    });
    // ページネーションのドットをクリックで直接そのスライドへジャンプ
    $('.slideshow .pagination .item').on('click', function () {
        slideshowSwitch($(this).closest('.slideshow'), $(this).index());
    });
    // 'check' イベント: ページネーションのアクティブドットをアクティブスライドに同期する
    // スライド切り替え完了後に trigger('check') で呼ばれる
    $('.slideshow .pagination').on('check', function () {
        const sw = $(this).closest('.slideshow');
        const p = $(this).find('.item');
        const index = sw.find('.slides .is-active').index();
        p.removeClass('is-active');
        p.eq(index).addClass('is-active');
    });
    // スライドショー本体をクリックしたら自動再生タイマーをキャンセル（手動操作優先）
    slideshow.on('click', function () {
        clearTimeout($(this).data('timeout'));
        $(this).data('timeout', null);
    });
    // スライド内のリンクボタン: ローディングスピナーを見せてから遷移
    // 直接 location.href を変えると spinner が表示される前に遷移してしまうため 50ms 遅延
    slideshow.on('click', '.slide .btn', function (e) {
        e.preventDefault();
        const href = $(this).attr('href');
        if (!href)
            return;
        const spinner = document.getElementById('loading');
        if (spinner)
            spinner.classList.remove('loaded'); // スピナー表示
        setTimeout(() => {
            location.href = href;
        }, 50);
    });
    // イントロシーケンスを起動し、完了後に自動再生を開始する
    function startIntro() {
        runIntroSequence(slideshow, () => {
            slideshow.find('.slide .slide-content').css('visibility', ''); // テキストを再表示
            slideshow.find('.arrows').css('visibility', ''); // 矢印を再表示
            syncSlideVideos(slideshow); // イントロで全動画を起動したので非アクティブを止める
            const t = setTimeout(() => slideshowNext(slideshow, false, true), slideshowDuration);
            slideshow.data('timeout', t);
        });
    }
    // 'load' イベントを使うことで、すべてのリソース（画像・動画）が揃った後にイントロを起動する
    // DOMContentLoaded より遅いが、画像サイズが確定してからアニメーション幅計算を行うために必要
    window.addEventListener('load', startIntro);
});
//# sourceMappingURL=slider.js.map