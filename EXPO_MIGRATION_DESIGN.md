# React Native Expo 移行設計書

## 1. 現状分析

### システム構成（現行）

```
personal-view-for-share/
├── api/          FastAPI REST API (SQLite)
└── web/          FastAPI SSR + TypeScript/jQuery フロントエンド
```

| レイヤー | 技術 | 主な役割 |
|---|---|---|
| API サーバー | FastAPI + SQLite | 認証・カテゴリ/コンテンツ CRUD・ユーザー管理 |
| Web サーバー | FastAPI + Jinja2 | セッション管理・ファイル処理・HTML 配信 |
| フロントエンド | TypeScript + jQuery | UI・アップロード・HLS ポーリング |

### 主要機能一覧

| 機能 | 現状 | 移行難度 |
|---|---|---|
| ログイン / サインアップ / パスワードリセット | Cookie セッション + HTML フォーム | 中（トークン化が必要） |
| カテゴリ一覧・作成・編集・削除 | SSR + fetch API | 低 |
| コンテンツ一覧・アップロード・削除 | multipart + XHR | 中 |
| 画像ライトボックス | Fancybox | 低（expo-image-viewing） |
| HLS 動画ストリーミング | video.js / hls.js | 低（expo-av は HLS ネイティブ対応） |
| パーティクルエフェクト | Canvas + requestAnimationFrame | 高（代替実装が必要） |
| 動画背景（カテゴリページ） | `<video>` autoplay | 中（expo-av） |
| スライドショー（ホーム） | CSS transform + JS | 中 |
| 招待 URL 発行・承認 | Cookie セッション + リダイレクト | 中 |
| ロールベースアクセス制御 | サーバーサイド判定 | 低（クライアント側に複製） |
| 監査ログ（admin） | SSE ストリーミング | 高（代替必要） |

---

## 2. 移行方針

### 基本方針

1. **バックエンドは最小限の変更で流用する**  
   `api/` サーバーはほぼそのまま利用。`web/` サーバーはファイル処理（アップロード・HLS 変換・画像配信）の部分だけを残し、HTML 配信は廃止する。

2. **認証をトークンベースに切り替える**  
   現行の Cookie セッションを JWT（または Bearer トークン）に変更し、`expo-secure-store` に保存する。

3. **段階的移行**  
   既存 Web もしばらく並行稼働させ、モバイルアプリ完成後に Web を廃止する。

### バックエンド変更方針

| 変更箇所 | 変更内容 |
|---|---|
| `api/src/main.py` `/login/verify` | レスポンスに JWT を追加 |
| `web/src/main.py` | セッション Cookie 認証に加え `Authorization: Bearer <token>` ヘッダーを受け付けるよう拡張 |
| `web/src/main.py` HTML 配信エンドポイント | 廃止（または維持したまま放置） |

---

## 3. アーキテクチャ設計（移行後）

```
┌────────────────────────────────────────────────────────┐
│              React Native Expo App                     │
│                                                        │
│  screens/          components/          hooks/         │
│  HomeScreen        CategoryCard         useAuth        │
│  CategoryScreen    ContentGrid          useContents    │
│  LoginScreen       MediaViewer          useCategories  │
│  UploadScreen      ModalSheet           useUpload      │
└───────────────────┬────────────────────────────────────┘
                    │  HTTPS / Bearer Token
          ┌─────────┴─────────┐
          │                   │
   ┌──────▼──────┐   ┌────────▼────────┐
   │  api/       │   │  web/           │
   │  FastAPI    │   │  FastAPI        │
   │  SQLite     │   │  (ファイル処理) │
   └─────────────┘   └─────────────────┘
```

---

## 4. 技術スタック

| カテゴリ | パッケージ | 用途 |
|---|---|---|
| フレームワーク | `expo` (SDK 52+) | ベース |
| ナビゲーション | `@react-navigation/native` + `@react-navigation/stack` | 画面遷移 |
| 状態管理 | `zustand` | グローバル状態（認証・カテゴリ） |
| HTTP | `axios` + `react-query` (TanStack Query) | API 通信・キャッシュ |
| 認証トークン保存 | `expo-secure-store` | JWT 永続化 |
| 画像表示 | `expo-image` | 高速キャッシュ付き画像 |
| 動画再生 | `expo-av` または `expo-video` | HLS / MP4 |
| ライトボックス | `react-native-image-viewing` | 画像フルスクリーン |
| ファイル選択 | `expo-document-picker` + `expo-image-picker` | アップロード |
| ファイルシステム | `expo-file-system` | ダウンロード保存 |
| 共有 | `expo-sharing` | ダウンロード後の共有 |
| フォーム | `react-hook-form` + `zod` | バリデーション付きフォーム |
| アニメーション | `react-native-reanimated` + `react-native-gesture-handler` | アニメーション |
| パーティクル代替 | `react-native-reanimated`（カスタム実装） | ホーム背景演出 |
| スタイル | `nativewind` (Tailwind for RN) または StyleSheet | スタイリング |
| アイコン | `@expo/vector-icons` (FontAwesome 互換) | アイコン |

---

## 5. ディレクトリ構成

```
expo-app/
├── app/                    # Expo Router (File-based routing)
│   ├── (auth)/
│   │   ├── login.tsx
│   │   ├── signup.tsx
│   │   ├── signup-details.tsx
│   │   ├── forgot-password.tsx
│   │   └── reset-password.tsx
│   ├── (main)/
│   │   ├── _layout.tsx     # ドロワー or タブナビゲーション
│   │   ├── index.tsx       # ホーム（カテゴリスライドショー）
│   │   ├── category/
│   │   │   └── [id].tsx    # カテゴリコンテンツ一覧
│   │   ├── how-to-use.tsx
│   │   └── logs.tsx        # admin 限定
│   └── invite/
│       └── [token].tsx     # 招待確認ページ
├── src/
│   ├── api/
│   │   ├── client.ts       # axios インスタンス（Bearer トークン自動付与）
│   │   ├── auth.ts         # 認証 API
│   │   ├── categories.ts   # カテゴリ API
│   │   ├── contents.ts     # コンテンツ API
│   │   └── upload.ts       # アップロード API
│   ├── components/
│   │   ├── CategoryCard.tsx
│   │   ├── ContentGrid.tsx
│   │   ├── ContentGridItem.tsx
│   │   ├── MediaViewer.tsx      # 画像/動画統合ビューワー
│   │   ├── ParticleBackground.tsx
│   │   ├── VideoBackground.tsx
│   │   ├── modals/
│   │   │   ├── FormModal.tsx
│   │   │   ├── ConfirmModal.tsx
│   │   │   ├── CategoryCreateModal.tsx
│   │   │   ├── CategoryEditModal.tsx
│   │   │   ├── ContentEditModal.tsx
│   │   │   └── ShareModal.tsx
│   │   └── ConversionProgress.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useCategories.ts
│   │   ├── useContents.ts
│   │   ├── useUpload.ts
│   │   └── useConversionPolling.ts
│   ├── stores/
│   │   └── authStore.ts    # zustand（ユーザー情報・トークン）
│   ├── types/
│   │   ├── auth.ts
│   │   ├── category.ts
│   │   └── content.ts
│   └── utils/
│       ├── fileType.ts
│       └── urls.ts         # API_BASE URL 管理
├── assets/
├── app.json
└── package.json
```

---

## 6. 画面設計

### 6.1 ホーム画面（index.tsx）

現行の `index.html`（スライドショー形式）を再現する。

| 要素 | 現行 | 移行後 |
|---|---|---|
| カテゴリスライド | CSS transform + JS slider.ts | `FlatList` + `react-native-reanimated` |
| 背景画像/動画 | `<img>` / `<video>` | `expo-image` / `expo-av` |
| パーティクル | Canvas 2D | `Reanimated` カスタムパーティクル or 省略 |
| グローバルナビ | jQuery fadeIn/Out | `Animated.View` + ドロワーナビ |

### 6.2 カテゴリ画面（category/[id].tsx）

| 要素 | 現行 | 移行後 |
|---|---|---|
| コンテンツグリッド | `<ul class="grid">` | `FlatList` (numColumns=3) |
| 画像表示 | Fancybox | `react-native-image-viewing` |
| 動画再生 | video.js + HLS | `expo-av` (`useVideoPlayer`) |
| アップロード | `<input type="file">` | `expo-document-picker` + `expo-image-picker` |
| 編集モード | `classList.toggle('edit-mode')` | `useState(isEditMode)` |
| HLS 変換状態 | 1秒ポーリング | `useConversionPolling` フック（setInterval） |

### 6.3 ログイン / 認証画面

現行フォームを `react-hook-form` で再実装。  
セッション Cookie → `expo-secure-store` に JWT を保存。

---

## 7. API 変更設計

### 7.1 `api/src/main.py` への変更（最小限）

**`/login/verify` レスポンス拡張**

```python
# 変更前
return {"ok": True, "user_id": row["id"], "role": row["role"], ...}

# 変更後（JWT を追加）
import jwt, time
token = jwt.encode(
    {"sub": row["id"], "role": row["role"], "exp": time.time() + 86400 * 180},
    SECRET_KEY, algorithm="HS256"
)
return {"ok": True, "user_id": row["id"], "role": row["role"],
        "viewable_category_ids": row["viewable_category_ids"],
        "access_token": token}
```

### 7.2 `web/src/main.py` への変更

**Bearer トークン認証を既存 Cookie 認証と並行サポート**

```python
def _get_session(request: Request) -> dict:
    """Cookie または Bearer トークンからセッション情報を取得する"""
    # 既存の Cookie セッション
    token = request.cookies.get("session")
    if token and token in active_sessions:
        return active_sessions[token]
    # モバイルアプリ向け Bearer トークン
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        jwt_token = auth_header[7:]
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=["HS256"])
        return {"user_id": payload["sub"], "role": payload["role"], ...}
    return {}
```

### 7.3 モバイル向け新規エンドポイント（web サーバーに追加）

| エンドポイント | 用途 |
|---|---|
| `POST /api/login` | JWT を返すログイン（Web とは別に）|
| `GET /api/me` | 現在ユーザー情報返却 |

既存エンドポイント（`/upload/:id`, `/delete/:id`, `/categories`, など）はそのまま流用可能。

---

## 8. 認証フロー設計

```
App 起動
  └─ SecureStore に token があるか？
       ├─ YES → GET /api/me で有効期限確認
       │          ├─ OK  → ホーム画面
       │          └─ 401 → ログイン画面
       └─ NO  → ログイン画面

ログイン成功
  └─ JWT を SecureStore.setItemAsync('access_token', token)
  └─ zustand authStore に user 情報をセット
  └─ ホーム画面へ遷移

ログアウト
  └─ SecureStore.deleteItemAsync('access_token')
  └─ authStore をリセット
  └─ ログイン画面へ遷移
```

---

## 9. ファイルアップロード設計

現行 Web は `XMLHttpRequest` + `FormData`。モバイルでも同様のアプローチが使える。

```typescript
// src/api/upload.ts
export async function uploadFile(categoryId: string, file: FileInfo) {
  const formData = new FormData();
  formData.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.mimeType ?? 'application/octet-stream',
  } as any);

  const response = await apiClient.post(`/upload/${categoryId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      const percent = Math.round((e.loaded / (e.total ?? 1)) * 100);
      onProgress?.(percent);
    },
  });
  return response.data;
}
```

**ファイルピッカー統合**

```typescript
// 画像・動画の選択
const result = await ImagePicker.launchImageLibraryAsync({
  mediaTypes: ImagePicker.MediaTypeOptions.All,
  allowsMultipleSelection: true,
});

// その他ファイル（PDF等）の選択
const result = await DocumentPicker.getDocumentAsync({ multiple: true });
```

---

## 10. メディア表示設計

### 10.1 画像ライトボックス

```typescript
// react-native-image-viewing を使用
<ImageViewing
  images={images.map(item => ({ uri: contentUrl(categoryId, item) }))}
  imageIndex={selectedIndex}
  visible={visible}
  onRequestClose={() => setVisible(false)}
/>
```

### 10.2 HLS 動画（expo-av）

```typescript
const player = useVideoPlayer(
  `${API_BASE}/personal-web/contents/${categoryId}/video/${item.file_name}`,
  (p) => { p.loop = false; }
);

<VideoView
  player={player}
  style={styles.video}
  allowsFullscreen
  allowsPictureInPicture
/>
```

expo-av は iOS の AVPlayer / Android の ExoPlayer を使うため、HLS (`.m3u8`) をネイティブで再生可能。**サーバー側の HLS 変換ロジック（ffmpeg）は変更不要。**

---

## 11. パーティクルエフェクト移行

現行は Canvas 2D で実装。React Native では Canvas が使えないため `react-native-reanimated` で代替実装する。

```typescript
// src/components/ParticleBackground.tsx
// Reanimated の worklet でパーティクルを Animated.View として管理
// 現行の particleEffect.ts のロジック（速度・透明度・サイズ）を移植
```

パーティクル数を現行より削減（モバイル GPU 負荷考慮：50〜80個）。

---

## 12. 移行フェーズ

### Phase 1 — 基盤構築（1〜2週間）

- [ ] Expo プロジェクト作成（`create-expo-app`）
- [ ] Expo Router のファイルベースルーティング設定
- [ ] `api/` サーバーへの JWT 発行追加
- [ ] `web/` サーバーへの Bearer トークン認証追加
- [ ] `src/api/client.ts`（axios + 自動トークン付与）
- [ ] `authStore`（zustand）と `useAuth` フック
- [ ] ログイン画面・サインアップ画面

### Phase 2 — コア機能（2〜3週間）

- [ ] ホーム画面（カテゴリスライドショー）
- [ ] カテゴリ画面（コンテンツグリッド）
- [ ] 画像ライトボックス（react-native-image-viewing）
- [ ] HLS 動画再生（expo-av）
- [ ] 画像・動画アップロード（ImagePicker + DocumentPicker）
- [ ] HLS 変換進捗ポーリング
- [ ] コンテンツ削除・強制削除
- [ ] コンテンツタイトル編集

### Phase 3 — カテゴリ管理・招待（1〜2週間）

- [ ] カテゴリ作成・編集・削除モーダル
- [ ] カテゴリ背景画像・動画設定
- [ ] 招待 URL 発行（ShareModal）
- [ ] 招待 URL 受け入れ画面

### Phase 4 — 演出・細部（1週間）

- [ ] パーティクルエフェクト（Reanimated 実装）
- [ ] 動画背景（VideoBackground）
- [ ] ナビゲーションアニメーション
- [ ] ローディング状態・エラーハンドリング

### Phase 5 — Admin 機能（任意）

- [ ] ログ閲覧画面（SSE → ポーリングに変更、またはWebView埋め込み）
- [ ] ユーザー管理

---

## 13. 移行しない/変更する箇所

| 現行機能 | 方針 | 理由 |
|---|---|---|
| Jinja2 テンプレート | 廃止 | RN で再実装 |
| jQuery | 廃止 | React コンポーネントに置換 |
| Fancybox | `react-native-image-viewing` に置換 | Web 専用ライブラリ |
| `<canvas>` パーティクル | Reanimated で再実装 | Web API 非対応 |
| SSE ログストリーミング | ポーリングまたは WebView | RN の EventSource サポートが限定的 |
| Cookie セッション | JWT + SecureStore | モバイルでは Cookie 管理が複雑 |
| HLS 変換（ffmpeg） | **そのまま流用** | サーバーサイド処理のため変更不要 |
| SQLite DB スキーマ | **そのまま流用** | 変更不要 |

---

## 14. リスクと対策

| リスク | 対策 |
|---|---|
| 動画背景がモバイルでパフォーマンス低下 | 静止画フォールバックを用意。autoplay は `isMuted` 必須（iOS 制限） |
| 大容量ファイルアップロードのタイムアウト | `expo-file-system` の `uploadAsync` を使用（バックグラウンド対応） |
| HLS セグメントの認証（Bearer トークン）| `web/main.py` の `/personal-web/contents/` エンドポイントに Bearer 認証を追加 |
| Android の HLS 再生互換性 | ExoPlayer（expo-av の Android 実装）は HLS をフルサポート |
| iOS の `autoplay` 動画制限 | `isMuted={true}` + `shouldPlay={true}` を組み合わせる |
| パーティクルエフェクトのバッテリー消費 | 画面非アクティブ時（AppState）にアニメーションを停止 |
