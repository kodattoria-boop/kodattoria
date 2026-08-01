# KODATTORIA サイト 運用ガイド

## ファイル構成

```
kodattoria-site/
├── index.html        トップページ
├── magazine.html     雑誌アーカイブ（自動生成）
├── goods.html        グッズページ
├── style.css         共通デザイン
├── lang.js           言語切り替え
├── build.py          自動ビルドスクリプト
├── optimize.py       写真最適化ツール
├── images/
│   ├── cover/            雑誌表紙（build.pyが自動生成）
│   ├── dish/             料理写真（optimize.pyで追加）
│   └── photo/            その他写真
├── .github/workflows/
│   └── deploy.yml        GitHub Actions自動デプロイ
└── .env.example      環境変数のサンプル
```

---

## 初回セットアップ

### 1. Notion Integration Token を取得

1. https://www.notion.so/my-integrations を開く
2. **「+ New integration」** をクリック
3. 名前: `KODATTORIA Site` など適当に
4. 表示された **Internal Integration Token** をコピー

### 2. 雑誌号管理DB を Integration に共有

1. Notionで雑誌号管理DBページを開く
2. 右上の「•••」メニュー → **Connections** → 作成した Integration を追加

### 3. 雑誌号管理DBの ID を確認

1. 雑誌号管理DBページをブラウザで開く
2. URLから**32桁のID**をコピー
   ```
   https://www.notion.so/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?v=...
                         ↑↑↑↑ここが Database ID
   ```

### 4. GitHubに Secrets を登録

1. GitHubリポジトリ → **Settings** → **Secrets and variables** → **Actions**
2. 以下を2つ追加:

| 名前 | 値 |
|---|---|
| `NOTION_TOKEN` | 手順１で取得したトークン |
| `NOTION_MAG_DB_ID` | 手順３で確認したDBのID |

---

## 毎月の運用フロー

### 雑誌を新増するとき（自動化済みはここだけ！）

1. **Notionの雑誌号管理DB**に新しい行を追加
   - `号`: vol.9
   - `テーマ`: 感動した！プーリア
   - `発行予定日`: 2026-08-15
   - `誠面画像（JPEG）`: 表紙写真をアップロード
   - `ステータス`: **発行済**に変更
2. GitHub → **Actions** → **「KODATTORIA サイト 自動ビルド」** → **Run workflow**
3. 2、3分待つ→サイトに自動反映 ✅

### 料理写真を追加するとき

1. `input/` フォルダに写真を入れる
2. `optimize.py` をダブルクリック→「1. dish」を選択
3. `images/dish/` に最適化済み写真が出力される
4. GitHubにプッシュ → Cloudflare Pagesに自動デプロイ ✅

---

## ローカルで手動実行（テスト用）

```bash
pip install requests pillow python-dotenv
cp .env.example .env
# .env を編集して値を入れる
python build.py
```
