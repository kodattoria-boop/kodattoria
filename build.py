#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KODATTORIA サイト ビルドスクリプト
Notion DB からデータを取得し、HTMLを自動生成する

必要な環境変数（.env または GitHub Secrets）：
  NOTION_TOKEN      : Notion Integration Token
  NOTION_MAG_DB_ID  : 雑誌号管理DBの ID（Notion URLの32桁UUID）

実行：
  pip install requests pillow python-dotenv
  python build.py
"""

import os
import sys
import json
import shutil
import requests
from pathlib import Path
from datetime import datetime
from io import BytesIO
import re

try:
    from PIL import Image, ExifTags
except ImportError:
    print("❌ Pillowが必要です: pip install pillow")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .envなしでも環境変数があればOK

# ===== 設定 =====
NOTION_TOKEN     = os.environ.get("NOTION_TOKEN", "")
NOTION_MAG_DB_ID = os.environ.get("NOTION_MAG_DB_ID", "")
NOTION_VERSION   = "2022-06-28"
OUT_DIR          = Path(".")   # HTMLの出力先
IMG_DIR          = OUT_DIR / "images" / "cover"
COVER_MAX_PX     = 700
COVER_QUALITY    = 85
# =================

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def check_env():
    missing = []
    if not NOTION_TOKEN:     missing.append("NOTION_TOKEN")
    if not NOTION_MAG_DB_ID: missing.append("NOTION_MAG_DB_ID")
    if missing:
        print(f"❌ 環境変数が未設定です: {', '.join(missing)}")
        print("セットアップ手順はREADME.mdを参照してください。")
        sys.exit(1)


def fetch_magazine_issues():
    """雑誌号管理DBから「発行済」の号を新しい順に取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_MAG_DB_ID}/query"
    payload = {
        "filter": {
            "property": "ステータス",
            "status": {"equals": "発行済"}
        },
        "sorts": [{"property": "発行予定日", "direction": "descending"}]
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    res.raise_for_status()
    return res.json().get("results", [])


def fetch_production_issues():
    """雑誌号管理DBから「制作中」の号を古い順（日付が近い順）に取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_MAG_DB_ID}/query"
    payload = {
        "filter": {
            "property": "ステータス",
            "status": {"equals": "制作中"}
        },
        "sorts": [{"property": "発行予定日", "direction": "ascending"}]
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    res.raise_for_status()
    return res.json().get("results", [])


def get_file_url(file_prop):
    """ファイルプロパティからURLを取得"""
    files = file_prop or []
    if not files:
        return None
    f = files[0]
    if f["type"] == "file":
        return f["file"]["url"]
    elif f["type"] == "external":
        return f["external"]["url"]
    return None


def download_and_optimize(url, out_path):
    """画像をダウンロードしリサイズして保存"""
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    img = Image.open(BytesIO(res.content))
    # EXIF向き修正
    try:
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if ExifTags.TAGS.get(tag) == 'Orientation':
                    if val == 3:   img = img.rotate(180, expand=True)
                    elif val == 6: img = img.rotate(270, expand=True)
                    elif val == 8: img = img.rotate(90, expand=True)
    except Exception:
        pass
    img = img.convert("RGB")
    w, h = img.size
    long_edge = max(w, h)
    if long_edge > COVER_MAX_PX:
        scale = COVER_MAX_PX / long_edge
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=COVER_QUALITY, optimize=True)
    return out_path


def parse_issue(page):
    """
    ページ情報を辞書に変換する

    Args:
        page (dict): Notion API から取得したページオブジェクト

    Returns:
        dict: パースされた号情報（号、テーマ、英語テーマ、イタリア語テーマ、発行予定日、表紙URL等）
    """
    props = page["properties"]

    # 号（title型）
    vol_parts = props.get("号", {}).get("title", [])
    vol = vol_parts[0]["plain_text"] if vol_parts else ""

    # テーマ（rich_text型）
    theme_parts = props.get("テーマ", {}).get("rich_text", [])
    theme = theme_parts[0]["plain_text"] if theme_parts else ""

    # 発行予定日（date型）
    date_prop = props.get("発行予定日", {}).get("date")
    date_str = ""
    if date_prop and date_prop.get("start"):
        d = datetime.fromisoformat(date_prop["start"])
        date_str = d.strftime("%Y.%m.%d")

    # 表紙画像 URL (表記揺れ・誤字対応)
    img_files = []
    possible_keys = ["表紙画像（JPEG）", "誠面画像（JPEG）", "表面画像（JPEG）", "表紙画像", "表紙", "画像"]
    for key in possible_keys:
        if key in props:
            files_list = props[key].get("files", [])
            if files_list:
                img_files = files_list
                break
    img_url = get_file_url(img_files)

    # 英語・イタリア語テーマの取得（プロパティが存在すれば取得、なければ空文字）
    theme_en = ""
    theme_it = ""

    # 英語キー候補
    for key in ["テーマ(en)", "テーマ_en", "テーマ en", "テーマ（en）", "テーマ(English)", "テーマ(english)", "Theme_en", "Theme en", "Theme (en)", "Theme", "Theme (English)"]:
        if key in props:
            parts = props[key].get("rich_text", [])
            if parts:
                theme_en = parts[0]["plain_text"]
                break

    # イタリア語キー候補
    for key in ["テーマ(it)", "テーマ_it", "テーマ it", "テーマ（it）", "テーマ(Italian)", "テーマ(italian)", "Theme_it", "Theme it", "Theme (it)", "テーマ(伊)", "テーマ(伊語)"]:
        if key in props:
            parts = props[key].get("rich_text", [])
            if parts:
                theme_it = parts[0]["plain_text"]
                break

    return {
        "vol": vol,
        "theme": theme,
        "theme_en": theme_en,
        "theme_it": theme_it,
        "date": date_str,
        "img_url": img_url
    }


# OSのロケール設定に依存せず、常に英語表記の曜日を取得するためのマッピング
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_event_date(date_str):
    """
    Notionから取得した日付文字列を「M.DD (Day)」形式（例: 8.15 (Sat)）にフォーマットする。
    OSのロケール設定に依存しないように曜日を取得する。

    Args:
        date_str (str): 「YYYY.MM.DD」形式の日付文字列

    Returns:
        str: フォーマットされた日付文字列
    """
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str, "%Y.%m.%d")
        weekday = WEEKDAYS_EN[d.weekday()]
        return f"{d.month}.{d.day:02d} ({weekday})"
    except Exception as e:
        print(f"  ⚠️ 日付フォーマットの変換に失敗しました ({date_str}): {e}")
        return date_str


def build_cover_images(issues):
    """表紙画像をダウンロードし最適化"""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for issue in issues:
        vol_slug = issue["vol"].replace(".", "").replace(" ", "-").lower()
        img_path = IMG_DIR / f"{vol_slug}.jpg"
        issue["img_path"] = None
        if issue["img_url"]:
            try:
                download_and_optimize(issue["img_url"], img_path)
                issue["img_path"] = f"images/cover/{vol_slug}.jpg"
                print(f"  ✓ 表紙画像: {img_path.name}")
            except Exception as e:
                print(f"  ⚠️ 画像取得失敗 ({issue['vol']}): {e}")


def render_mag_list(issues):
    """雑誌リストHTMLを生成"""
    items = []
    for issue in issues:
        vol   = issue["vol"]
        theme = issue["theme"]
        date  = issue["date"]
        img_p = issue.get("img_path")

        if img_p:
            cover_html = f'<img src="{img_p}" alt="{vol} {theme}">'
        else:
            cover_html = '<span data-lang="ja">表紙</span><span data-lang="en">Cover</span><span data-lang="it">Copertina</span>'

        items.append(f"""
            <li>
              <div class="mag-cover-box">{cover_html}</div>
              <div class="mag-info">
                <div><span class="vol-label">{vol}</span><strong>{theme}</strong></div>
                <div style="color:#999;font-size:x-small;">{date}</div>
              </div>
            </li>""")
    return "\n".join(items)


def build_magazine_html(issues):
    mag_list = render_mag_list(issues)
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KODATTORIA - 雑誌アーカイブ</title>
<link rel="stylesheet" href="style.css">
</head>
<body class="lang-ja">

<div id="lang-bar">
  <button onclick="setLang('ja')" class="active" id="btn-ja">日本語</button>
  <button onclick="setLang('en')" id="btn-en">English</button>
  <button onclick="setLang('it')" id="btn-it">Italiano</button>
</div>

<div id="wrapper">
  <table id="main-table"><tbody><tr>
    <td id="left-cell">
      <div id="photo-box">
        <img src="home.jpg" alt="KODATTORIAの写真">
      </div>
      <ul id="site-nav">
        <li><a href="index.html"><span data-lang="ja">トップ</span><span data-lang="en">Top</span><span data-lang="it">Top</span></a></li>
        <li class="active"><a href="magazine.html"><span data-lang="ja">雑誌アーカイブ</span><span data-lang="en">Magazine</span><span data-lang="it">Rivista</span></a></li>
        <li><a href="goods.html"><span data-lang="ja">グッズ</span><span data-lang="en">Goods</span><span data-lang="it">Merchandise</span></a></li>
      </ul>
    </td>
    <td id="info-cell">
      <div id="site-title">KODATTORIAのホームページ</div>
      <div id="site-tagline">
        <span data-lang="ja">間借りイタリアン &amp; 雑誌 &amp; 別荘プロジェクト</span>
        <span data-lang="en">Pop-up Italian &amp; Magazine &amp; Villa Project</span>
        <span data-lang="it">Ristorante Itinerante &amp; Rivista &amp; Progetto Villa</span>
      </div>
      <div class="section-title">
        <span data-lang="ja">雑誌アーカイブ</span>
        <span data-lang="en">Magazine Archive</span>
        <span data-lang="it">Archivio Rivista</span>
      </div>
      <ul class="mag-list">{mag_list}
      </ul>
      <p class="purchase-note">
        <span data-lang="ja">※ 購入は間借り営業日の現地のみ。オンライン販売なし。</span>
        <span data-lang="en">&dagger; On-site only during pop-up events. Not sold online.</span>
        <span data-lang="it">&dagger; Disponibile solo durante gli eventi. Non vendiamo online.</span>
      </p>
    </td>
  </tr></tbody></table>
  <div id="footer">&copy; KODATTORIA &nbsp;|&nbsp; <a href="https://www.instagram.com/koda.ttoria" target="_blank">Instagram</a></div>
</div>
<script src="lang.js"></script>
</body>
</html>
"""
    out = OUT_DIR / "magazine.html"
    out.write_text(html, encoding="utf-8")
    print(f"  ✓ {out} 生成")


def update_index_html(production_issues):
    """
    制作中の雑誌データから次回営業日情報を取得し、index.html の内容を更新する

    Args:
        production_issues (list): パース済みの「制作中」雑誌オブジェクトのリスト
    """
    index_file = OUT_DIR / "index.html"
    if not index_file.exists():
        print(f"  ⚠️ {index_file} が見つかりません。スキップします。")
        return

    if not production_issues:
        print("  ⚠️ 制作中の雑誌（ステータス：制作中）が見つからないため、index.html の次回営業日は更新されません。")
        return

    # production_issues が Notion API からのページオブジェクト（未パース）で渡された場合はパースする
    if production_issues and isinstance(production_issues[0], dict) and "properties" in production_issues[0]:
        production_issues = [parse_issue(p) for p in production_issues]

    # 最も日付が近い制作中の号を使用
    next_issue = production_issues[0]
    vol = next_issue["vol"]
    theme_ja = next_issue["theme"]
    # 英語とイタリア語は、Notionから取得できていればそれを使用し、なければ日本語をフォールバック
    theme_en = next_issue.get("theme_en") or theme_ja
    theme_it = next_issue.get("theme_it") or theme_ja

    formatted_date = format_event_date(next_issue["date"])

    # 挿入するHTMLを構築
    next_event_html = f"""            <!-- NEXT_EVENT_START -->
            <div class="date">{formatted_date}</div>
            <div class="vol">
              <span data-lang="ja">KODATTORIA {vol}「{theme_ja}」 発行日</span>
              <span data-lang="en">KODATTORIA {vol} &ldquo;{theme_en}&rdquo; &mdash; release day</span>
              <span data-lang="it">Uscita di KODATTORIA {vol} &ldquo;{theme_it}&rdquo;</span>
            </div>
            <!-- NEXT_EVENT_END -->"""

    # index.htmlの読み込みと置換（正規表現でマーカー間を堅牢に置換）
    content = index_file.read_text(encoding="utf-8")

    pattern = re.compile(r"<!-- NEXT_EVENT_START -->.*?<!-- NEXT_EVENT_END -->", re.DOTALL)
    if pattern.search(content):
        # 既存ブロックを新しいHTMLで置換
        new_content = pattern.sub(next_event_html, content, count=1)
        index_file.write_text(new_content, encoding="utf-8")
        print(f"  ✓ {index_file} の次回営業日を更新しました: {vol} ({formatted_date})")
    else:
        print(f"  ⚠️ {index_file} 内に '<!-- NEXT_EVENT_START -->' または '<!-- NEXT_EVENT_END -->' が見つかりません。")


def main():
    check_env()
    print("=" * 50)
    print("  KODATTORIA ビルドスクリプト")
    print(f"  実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n[1/4] Notion DB から発行済みの雑誌データを取得中...")
    pages = fetch_magazine_issues()
    issues = [parse_issue(p) for p in pages]
    print(f"  ✓ {len(issues)}冊の発行済アーカイブを取得")
    for iss in issues:
        print(f"     {iss['vol']} 「{iss['theme']}」 {iss['date']}")

    print("\n[2/4] Notion DB から制作中の雑誌データを取得中...")
    prod_pages = fetch_production_issues()
    prod_issues = [parse_issue(p) for p in prod_pages]
    print(f"  ✓ {len(prod_issues)}冊の制作中の雑誌を取得")
    for iss in prod_issues:
        print(f"     {iss['vol']} 「{iss['theme']}」 {iss['date']}")

    print("\n[3/4] 表紙画像をダウンロード・最適化中...")
    build_cover_images(issues)

    print("\n[4/4] HTMLを生成・更新中...")
    build_magazine_html(issues)
    update_index_html(prod_issues)

    print("\n" + "=" * 50)
    print("✅ ビルド完了！")
    print("=" * 50)


if __name__ == "__main__":
    main()
