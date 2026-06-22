#!/usr/bin/env bash
# =============================================================================
# deploy_github_pages.sh — 一鍵把「進擊的小黨：村里級議員選舉 GIS」上架 GitHub Pages
#
# 用法：
#   bash deploy_github_pages.sh [repo名稱] [public|private]
#   例： bash deploy_github_pages.sh tw-council-small-parties-gis public
#
# 前置需求：git、GitHub CLI(gh) 且已 gh auth login（需 repo 權限）。
#
# 會公開：docs/（互動地圖）、data/normalized/（開放資料集 CSV/JSON）、程式碼、README。
# 不會公開：data/raw/（183MB 中選會原始檔，由 .gitignore 排除，可由 fetch_data.py 重建）。
# =============================================================================
set -euo pipefail

REPO_NAME="${1:-tw-council-small-parties-gis}"
VISIBILITY="${2:-public}"
DESC="全台 2014/2018/2022 縣市・直轄市議員選舉村里級 GIS（含落選、政黨別）— 為時代力量/台灣基進/歐巴桑等小黨佈局而整理"

cd "$(dirname "$0")"
echo "▶ 專案目錄：$(pwd)"

command -v git >/dev/null || { echo "✗ 需要 git"; exit 1; }
command -v gh  >/dev/null || { echo "✗ 需要 GitHub CLI：brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "✗ 請先登入：gh auth login"; exit 1; }

[ -f docs/index.html ]  || { echo "✗ 找不到 docs/index.html（先跑 build_map.py）"; exit 1; }
[ -f docs/data.js ]     || { echo "✗ 找不到 docs/data.js（先跑 build_map.py）"; exit 1; }

# GitHub Pages 由 /docs 提供；.nojekyll 避免 Jekyll 處理掉 _ 開頭或特殊檔
touch docs/.nojekyll

# git init + commit
[ -d .git ] || { echo "▶ git init"; git init -b main >/dev/null; }
git add -A
git commit -m "進擊的小黨：村里級議員選舉 GIS（2014/2018/2022）+ 資料管線" \
  >/dev/null 2>&1 && echo "▶ 已建立 commit" || echo "▶ (無新變更可提交)"

# 建立 remote 並 push
if git remote get-url origin >/dev/null 2>&1; then
  echo "▶ 推送到既有 origin"; git push -u origin main
else
  echo "▶ 建立 GitHub repo ${REPO_NAME} (${VISIBILITY}) 並推送"
  gh repo create "${REPO_NAME}" --"${VISIBILITY}" --source=. --push --description "${DESC}"
fi

# 啟用 Pages（main /docs）
OWNER=$(gh api user -q .login)
echo "▶ 啟用 GitHub Pages (main /docs)…"
gh api -X POST "repos/${OWNER}/${REPO_NAME}/pages" \
     -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1 \
  || gh api -X PUT "repos/${OWNER}/${REPO_NAME}/pages" \
       -f "source[branch]=main" -f "source[path]=/docs" >/dev/null 2>&1 \
  || echo "  (若失敗，請到 repo Settings ▸ Pages 設 Source = main / docs)"

echo ""
URL=$(gh api "repos/${OWNER}/${REPO_NAME}/pages" -q .html_url 2>/dev/null || true)
echo "✅ 完成！約 1–2 分鐘後可開："
echo "   ${URL:-https://${OWNER}.github.io/${REPO_NAME}/}"
echo "Repo： https://github.com/${OWNER}/${REPO_NAME}"
