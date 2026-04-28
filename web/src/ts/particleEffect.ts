// Three.js をCDNから動的に読み込むため、先にスタイルとcanvasだけを即挿入しておく
// （スクリプトの onload 後に canvas が存在していないと WebGLRenderer が失敗するため）

// canvas を全面に固定表示するスタイルをJSで注入
// pointer-events:none でマウス操作を透過させ、z-index:2 でコンテンツの後ろに重ねる
const style = document.createElement('style');
style.textContent = `
  #particle-canvas {
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    pointer-events: none;
    z-index: 2;
  }
`;
document.head.appendChild(style);

// Three.js がレンダリング先として使う canvas 要素をbodyの先頭に挿入
const canvas = document.createElement('canvas');
canvas.id = 'particle-canvas';
document.body.prepend(canvas);

// Three.js 本体を CDN から非同期ロード。onload 内でシーン構築を行う
const script = document.createElement('script');
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
script.onload = function () {
  // ---- Three.js シーン基本セットアップ ----
  const scene = new THREE.Scene();

  // PerspectiveCamera(視野角, アスペクト比, near, far)
  // 視野角75°は自然な遠近感。far=1000 は z=-600〜600 の粒子をすべてカバーする
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);

  // alpha:true で背景を透明にし、下のHTML/CSS が透けて見えるようにする
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0); // 完全透明クリア

  // ---- パーティクル用テクスチャ生成 ----
  // Canvas 2D でラジアルグラデーションを描き、ボケた円形テクスチャを作る
  // これを PointsMaterial.map に使うことで、点が柔らかい光球に見える
  function createCircleTexture() {
    const size = 128;
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const ctx = c.getContext('2d')!;

    // 中心から端に向かって白→透明のグラデーション（ソフトグロー効果）
    // 各 colorStop の位置と不透明度で光の広がり方を制御している
    const g = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
    g.addColorStop(0,    'rgba(255,255,255,1)');   // 中心: 完全不透明
    g.addColorStop(0.06, 'rgba(255,255,255,0.9)'); // コア外縁
    g.addColorStop(0.18, 'rgba(255,255,255,0.5)'); // 明るいハロー
    g.addColorStop(0.35, 'rgba(255,255,255,0.12)');// 薄いグロー
    g.addColorStop(0.65, 'rgba(255,255,255,0.03)');// ほぼ透明
    g.addColorStop(1,    'rgba(255,255,255,0)');   // 完全透明（エッジ）
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);

    // Canvas の描画内容を Three.js テクスチャに変換
    return new THREE.CanvasTexture(c);
  }

  // ---- パーティクルデータ配列の定義 ----
  // GPU に一括転送する都合で、すべて Float32Array（型付き配列）を使う
  const count = 800; // 画面上の粒子総数

  const positions      = new Float32Array(count * 3); // 各粒子の xyz 座標
  const colors         = new Float32Array(count * 3); // 各粒子の rgb 色（0〜1）
  const phases         = new Float32Array(count);     // 横揺れサイン波の初期位相（粒子ごとにずらす）
  const speeds         = new Float32Array(count);     // 上昇速度（フレームあたりの y 移動量）
  const amplitudes     = new Float32Array(count);     // 横揺れの振れ幅
  const fadeStartY     = new Float32Array(count);     // この y 座標を超えると上端へ向かってフェードアウト開始
  const windVels       = new Float32Array(count);     // 現在の風による x 速度（ラグ付きで目標値に追従）
  const windLag        = new Float32Array(count);     // 風速の追従係数（小さいほど追従が遅く、ふわっとした動き）
  const baseR          = new Float32Array(count);     // 粒子本来の赤成分（フェード・ちらつき乗算前）
  const baseG          = new Float32Array(count);     // 同上（緑）
  const baseB          = new Float32Array(count);     // 同上（青）
  const twinklePhase   = new Float32Array(count);     // ちらつきサイン波の初期位相
  const twinkleSpeed   = new Float32Array(count);     // ちらつきの速さ（粒子ごとに変える）

  // ---- 色温度バリエーション ----
  // 星/蛍光体のような自然な光源を模倣するため、暖色〜寒色を混在させる
  // RGB 比率で指定（1.0 が最大輝度）
  const tints: [number, number, number][] = [
    [1.00, 0.92, 0.75], // 暖色（キャンドル光）
    [1.00, 0.97, 0.88], // やや暖色
    [1.00, 1.00, 1.00], // 中性白
    [1.00, 1.00, 1.00], // 中性白（出現頻度を上げるため重複）
    [0.88, 0.95, 1.00], // やや寒色
    [0.80, 0.90, 1.00], // 寒色（月光）
  ];

  // y 座標のフェード開始点をランダムに決める（-100〜100 の範囲）
  // 上端に近いほど早くフェードアウトするが、個体差を出すためランダムにする
  function randomFadeStart(): number { return -100 + Math.random() * 200; }

  // 画面右側に粒子が多く見えるよう、x 座標の出現分布を非対称にしている
  // 右寄りデザインのため: 遠右(55%) > 近右(30%) > 左(15%) の確率で配置
  function randomX(): number {
    const r = Math.random();
    if (r < 0.55) return 100 + Math.random() * 100;  // 遠右: 55%
    if (r < 0.85) return Math.random() * 100;         // 近右: 30%
    return -200 + Math.random() * 200;                // 左: 15%
  }

  // ---- 各粒子の初期値を設定 ----
  for (let i = 0; i < count; i++) {
    const tint = tints[Math.floor(Math.random() * tints.length)];
    baseR[i] = tint[0];
    baseG[i] = tint[1];
    baseB[i] = tint[2];

    positions[i*3]   = randomX();
    positions[i*3+1] = Math.random() * 400 - 200; // y: -200〜200（上下全体にばらまく）
    positions[i*3+2] = (Math.random() - 0.5) * 600; // z: -300〜300（奥行きで遠近感を出す）

    phases[i]        = Math.random() * Math.PI * 2; // 0〜2π のランダム初期位相
    speeds[i]        = 0.5 + Math.random() * 0.5;   // 上昇速度: 0.5〜1.0
    amplitudes[i]    = 2 + Math.random() * 4;        // 横揺れ幅: 2〜6

    fadeStartY[i]    = randomFadeStart();
    colors[i*3]      = baseR[i];
    colors[i*3+1]    = baseG[i];
    colors[i*3+2]    = baseB[i];

    windVels[i]      = 0;
    windLag[i]       = 0.015 + Math.random() * 0.07; // 追従係数: 小さいほど風への反応が遅い

    twinklePhase[i]  = Math.random() * Math.PI * 2;
    twinkleSpeed[i]  = 0.4 + Math.random() * 1.2;    // ちらつき速度: 0.4〜1.6
  }

  // ---- Three.js ジオメトリ・マテリアル構築 ----
  const geometry = new THREE.BufferGeometry();
  // 位置と色を BufferAttribute として登録（GPU が直接参照できる形式）
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color',    new THREE.BufferAttribute(colors,    3));

  const material = new THREE.PointsMaterial({
    map: createCircleTexture(),  // 柔らかい光球テクスチャ
    size: 3,                     // 画面上のピクセルサイズ（sizeAttenuation で奥ほど小さくなる）
    transparent: true,
    opacity: 0.85,
    depthWrite: false,           // 半透明どうしのZファイティングを防ぐ
    blending: THREE.AdditiveBlending, // 加算合成: 重なると明るくなり、星雲・炎のような輝きに
    vertexColors: true,          // colors 属性を頂点ごとの色として使う
    sizeAttenuation: true,       // 遠くの粒子を小さく表示（透視投影に従う）
  });

  scene.add(new THREE.Points(geometry, material));

  // カメラを z=200 に置き、z=0 付近の粒子群を正面から見る
  camera.position.z = 200;

  // ---- 風エフェクト制御 ----
  let windDir = 1;
  let windStartTime = -Infinity; // 初期値を過去にすることで「風なし」状態にする
  let windDuration = 1000;
  const WIND_MAX = 1.8; // 風の最大速度（x 方向の加速度上限）

  // スライドが切り替わると slider.js から 'windTrigger' カスタムイベントが飛んでくる
  // direction: 'right'|'left', duration: ミリ秒
  window.addEventListener('windTrigger', function (e: Event) {
    const detail = (e as CustomEvent).detail;
    windDir = detail.direction === 'right' ? 1 : -1;
    windStartTime = Date.now();
    windDuration = detail.duration ?? 1000;
  });

  // ---- メインアニメーションループ ----
  (function animate() {
    requestAnimationFrame(animate); // 次フレームに自身を再予約

    // Date.now() * 0.002 で「秒の2倍」スケールの連続時間値を生成（サイン波の t に使う）
    const time = Date.now() * 0.002;
    const pos = geometry.attributes.position.array as Float32Array;
    const col = geometry.attributes.color.array as Float32Array;

    // 風のタイムライン: t=0〜1 に正規化し、sin(t*π) で「吹いてから収まる」形を作る
    // t が 1 を超えると windTarget=0 になり、風が止まる
    const t = Math.min((Date.now() - windStartTime) / windDuration, 1);
    const windTarget = -windDir * WIND_MAX * Math.sin(t * Math.PI);

    for (let i = 0; i < count; i++) {
      // 各粒子は windTarget に向かって windLag 係数で指数的に収束する（慣性シミュレーション）
      // windLag が小さいほど追従が遅く、ふわりとした動き
      windVels[i] += (windTarget - windVels[i]) * windLag[i];

      // y 方向: 一定速度で上昇
      pos[i*3+1] += speeds[i];

      // x 方向: サイン波の横揺れ + 風速
      pos[i*3]   += Math.sin(time + phases[i]) * amplitudes[i] * 0.1 + windVels[i];

      // ---- フェードアウト計算 ----
      // y が fadeStartY より小さい間は fade=1（完全表示）
      // fadeStartY を超えると y=200 に向かって線形に fade が 0 に近づく
      const y = pos[i*3+1];
      const fs = fadeStartY[i];
      const fade = y < fs ? 1 : Math.max(0, 1 - (y - fs) / (200 - fs));

      // ちらつき: 0.75〜1.0 の範囲でゆらぐ（0.75 + 0.25 * sin で下限を保証）
      const twinkle = 0.75 + 0.25 * Math.sin(time * twinkleSpeed[i] + twinklePhase[i]);

      // フェードとちらつきを乗算してから baseRGB に掛ける
      const b = fade * twinkle;
      col[i*3]   = baseR[i] * b;
      col[i*3+1] = baseG[i] * b;
      col[i*3+2] = baseB[i] * b;

      // ---- 画面上端を超えたらリセット（再生成）----
      // y > 200 になったら底（y=-200）に戻し、x・位相・フェード開始点を乱数で再設定
      if (y > 200) {
        pos[i*3+1] = -200;
        pos[i*3]   = randomX();
        pos[i*3+2] = (Math.random() - 0.5) * 600;
        phases[i]       = Math.random() * Math.PI * 2;
        fadeStartY[i]   = randomFadeStart();
        twinklePhase[i] = Math.random() * Math.PI * 2;
        // 色もリセット（フェードアウト中に死んだ場合に備えて）
        col[i*3]   = baseR[i];
        col[i*3+1] = baseG[i];
        col[i*3+2] = baseB[i];
      }
    }

    // CPU側で書き換えた配列を GPU に反映させるために needsUpdate フラグを立てる
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.color.needsUpdate    = true;

    renderer.render(scene, camera);
  })();

  // ウィンドウリサイズ時にカメラとレンダラーを追従させる
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix(); // aspect 変更後は必ず呼ぶ
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
};
document.head.appendChild(script);
