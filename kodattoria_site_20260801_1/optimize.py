#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KODATTORIA 写真最適化スクリプト

使い方：
  1. 写真を input/ フォルダに入れる
  2. このファイルをダブルクリック（または python optimize.py で実行）
  3. images/ フォルダに最適化済み写真が出てくる

カテゴリ：
  - dish   : 料理写真  （最大庁50px、品質80）
  - cover  : 雑誌表紙  （最大700px、品質85）
  - photo  : その他    （最大200px、品質80）
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ExifTags
except ImportError:
    print("❌ Pillowがインストールされていません。")
    print("ターミナルで: pip install Pillow")
    input("エンターで閉じる...")
    sys.exit(1)

# ===== 設定 =====
INPUT_DIR  = Path("input")    # 元写真を入れる場所
OUTPUT_DIR = Path("images")   # 出力先

CATEGORIES = {
    "dish":  {"max_px": 1150, "quality": 80},   # 料理写真
    "cover": {"max_px": 700,  "quality": 85},   # 雑誌表紙
    "photo": {"max_px": 1200, "quality": 80},   # その他
}

SUPPORTED = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

# ==================

def fix_orientation(img):
    """EXIF情報を元に画像を正しい向きに修正"""
    try:
        exif = img._getexif()
        if exif is None:
            return img
        for tag, val in exif.items():
            if ExifTags.TAGS.get(tag) == 'Orientation':
                if val == 3:
                    img = img.rotate(180, expand=True)
                elif val == 6:
                    img = img.rotate(270, expand=True)
                elif val == 8:
                    img = img.rotate(90, expand=True)
    except Exception:
        pass
    return img

def resize(img, max_px):
    """long edge が max_px を超える場合のみ縮小"""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_px:
        return img
    scale = max_px / long_edge
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

def safe_name(src_name, category, index):
    """kodattoria_dish_001.jpg のような安全なファイル名を生成"""
    return f"kodattoria_{category}_{index:03d}.jpg"

def process(input_path, output_path, max_px, quality):
    img = Image.open(input_path)
    img = fix_orientation(img)
    img = img.convert("RGB")
    img = resize(img, max_px)
    img.save(output_path, "JPEG", quality=quality, optimize=True)
    before_kb = input_path.stat().st_size // 1024
    after_kb  = output_path.stat().st_size // 1024
    return before_kb, after_kb

def main():
    print("=" * 50)
    print("  KODATTORIA 写真最適化ツール")
    print("=" * 50)

    if not INPUT_DIR.exists():
        INPUT_DIR.mkdir()
        print(f"\n✅ '{INPUT_DIR}' フォルダを作りました。")
        print(f"   写真をここに入れてから再実行してください。")
        input("\nエンターで閉じる...")
        return

    # カテゴリを問い合わせ
    print("\n写真の種類を選んでください：")
    print("  1. dish  : 料理写真")
    print("  2. cover : 雑誌表紙")
    print("  3. photo : その他（イベント、メンバー等）")
    choice = input("\n番号を入力 (1/2/3): ").strip()
    cats = {"1": "dish", "2": "cover", "3": "photo"}
    if choice not in cats:
        print("❌ 1、2、3のいずれかを入力してください。")
        input("\nエンターで閉じる...")
        return
    category = cats[choice]
    cfg = CATEGORIES[category]

    # 出力ディレクトリ作成
    out_dir = OUTPUT_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)

    # 既存ファイルの番号を確認して連番を決める
    existing = sorted(out_dir.glob("kodattoria_*.jpg"))
    nums = []
    for f in existing:
        m = re.search(r"_(\d+)\.jpg$", f.name)
        if m:
            nums.append(int(m.group(1)))
    start_index = max(nums) + 1 if nums else 1

    # 入力ファイル一覧
    files = [f for f in sorted(INPUT_DIR.iterdir())
             if f.suffix.lower() in SUPPORTED and not f.name.startswith('.')]

    if not files:
        print(f"\n⚠️ '{INPUT_DIR}' に写真がありません。")
        print("   写真を1枚以上入れてから再実行してください。")
        input("\nエンターで閉じる...")
        return

    print(f"\n{len(files)}枚の写真を処理中... カテゴリ: [{category}]")
    print("-" * 40)

    total_before = 0
    total_after  = 0
    results = []

    for i, src in enumerate(files, start=start_index):
        out_name = safe_name(src.name, category, i)
        out_path = out_dir / out_name
        try:
            before_kb, after_kb = process(src, out_path, cfg["max_px"], cfg["quality"])
            total_before += before_kb
            total_after  += after_kb
            ratio = int((1 - after_kb / max(before_kb, 1)) * 100)
            print(f"  ✓ {src.name[:30]:<30} {before_kb:>5}KB → {after_kb:>4}KB (-{ratio}%)")
            results.append(out_name)
        except Exception as e:
            print(f"  ❌ {src.name}: {e}")

    print("-" * 40)
    total_ratio = int((1 - total_after / max(total_before, 1)) * 100)
    print(f"  合計: {total_before}KB → {total_after}KB (-{total_ratio}%)")
    print(f"\n✅ 完了！ images/{category}/ に保存されました。")
    print("\nサイトに込めるファイル名:")
    for r in results:
        print(f"  images/{category}/{r}")

    input("\nエンターで閉じる...")

if __name__ == "__main__":
    main()
