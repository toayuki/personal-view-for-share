export interface BgVideoOptions {
  fadeEl?: HTMLElement | null;
  onSuccess?: () => void;
  onFail?: () => void;
}

/**
 * 動画背景の初期化とフェード管理。
 * @param videoEl          - 対象の &lt;video&gt; 要素
 * @param options.fadeEl   - 動画末尾にフェードアウト効果を付けるオーバーレイ要素（省略可）
 * @param options.onSuccess - 再生開始成功時のコールバック
 * @param options.onFail   - 再生失敗時のコールバック（ブラウザのAutoPlay制限など）
 */
export function initBgVideo(videoEl: HTMLVideoElement, options?: BgVideoOptions): void {
  if (!videoEl) return;
  const opts = options ?? {};
  const fadeEl = opts.fadeEl ?? null; // フェードオーバーレイ（なければ null）
  const fadeDuration = 0.8;           // フェード開始から完了までの秒数
  let fading = false;                 // フェードが進行中かどうかのフラグ（二重起動防止）

  // ---- 動画末尾のフェードアウト処理 ----
  // timeupdate は再生位置が変わるたびに発火する（おおよそ 4〜66ms 間隔）
  // 残り時間が fadeDuration 以下になったらフェードオーバーレイを不透明にする
  videoEl.addEventListener('timeupdate', () => {
    // duration が未確定、すでにフェード中、フェード要素がない場合はスキップ
    if (!videoEl.duration || fading || !fadeEl) return;
    const remaining = videoEl.duration - videoEl.currentTime;
    if (remaining <= fadeDuration) {
      fading = true;
      // 残り時間ぴったりのトランジション時間でフェードイン（暗転が動画終了に同期する）
      fadeEl.style.transition = `opacity ${remaining}s linear`;
      fadeEl.style.opacity = '1'; // オーバーレイを表示 → 動画が見えなくなる
    }
  });

  // ---- 動画終了時にループ再生 ----
  // loop 属性を使わず JS で制御するのは、ended イベントを捕捉してフラグリセットするため
  videoEl.addEventListener('ended', () => {
    videoEl.currentTime = 0;
    videoEl.play();
    // fading フラグのリセットは 'playing' イベント側で行う
  });

  // ---- 再生再開時にフェードオーバーレイを透明に戻す ----
  // ended → play() → playing の順に発火する
  // 500ms の遅延は、currentTime=0 にリセットした直後の1フレーム目が見えるのを待つため
  // （即座に opacity:0 にすると、前フレームと最初のフレームが切り替わる瞬間が見えることがある）
  if (fadeEl) {
    videoEl.addEventListener('playing', () => {
      setTimeout(() => {
        fadeEl.style.transition = `opacity ${fadeDuration}s linear`;
        fadeEl.style.opacity = '0'; // オーバーレイを非表示 → 動画が見える状態に戻す
        fading = false;             // フェードフラグをリセットして次のループに備える
      }, 500);
    });
  }

  // play() は Promise を返す（古いブラウザでは undefined）ので、then/catch で結果を扱う
  const p = videoEl.play();
  if (p !== undefined) {
    p.then(() => opts.onSuccess?.()).catch(() => opts.onFail?.());
  }
}
