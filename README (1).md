# 🚭 SmokeSentry AI — 校園吸煙行為智慧辨識與預警系統

> 多模態 AI 校園吸煙辨識系統 — Demo 網站

[![GitHub Pages](https://img.shields.io/badge/Deploy-GitHub%20Pages-blue)](https://pages.github.com/)

## 📋 計畫簡介

本系統結合 YOLOv8 影像辨識、MediaPipe 姿態估計與 MQ-135 煙霧感測，建立三層式多模態校園吸煙行為智慧辨識預警系統。

### 核心技術
- **YOLOv8** — 即時物件偵測（人物、香菸）
- **MediaPipe** — 人體姿態關鍵點分析
- **MQ-135** — 空氣品質感測器
- **多模態融合** — 三路資料交叉驗證，降低誤判率

## 🗂️ 檔案結構

```
smoking-detection-demo/
├── index.html        # 主頁 + 互動 DEMO
├── dashboard.html    # 管理後台儀表板
└── README.md
```

## 🚀 部署到 GitHub Pages

### 步驟一：建立 Repository

1. 前往 [GitHub](https://github.com) 登入
2. 點擊右上角 **"New repository"**
3. Repository 名稱輸入：`smokesentry-demo`（或任意名稱）
4. 設定為 **Public**
5. 點擊 **"Create repository"**

### 步驟二：上傳檔案

**方法 A — 網頁上傳（最簡單）：**
1. 在 Repository 頁面點擊 **"uploading an existing file"**
2. 將 `index.html` 和 `dashboard.html` 拖曳上傳
3. 點擊 **"Commit changes"**

**方法 B — Git 指令：**
```bash
git init
git add .
git commit -m "🚭 SmokeSentry AI Demo v1.0"
git branch -M main
git remote add origin https://github.com/你的帳號/smokesentry-demo.git
git push -u origin main
```

### 步驟三：啟用 GitHub Pages

1. 進入 Repository → **Settings**
2. 左側選單找到 **"Pages"**
3. Source 選擇 **"Deploy from a branch"**
4. Branch 選擇 **"main"**，資料夾選 **"/ (root)"**
5. 點擊 **"Save"**

約 1-2 分鐘後，網站將發布於：
```
https://你的帳號.github.io/smokesentry-demo/
```

## 🎮 Demo 功能說明

### 主頁 (index.html)
- 🖥️ **英雄區塊** — 模擬即時監控畫面（Canvas 動畫）
- ⚙️ **互動 Demo** — 四種情境觸發：
  - 😐 正常行走
  - 🍔 吃東西（誤判測試 — 展示多模態融合如何排除誤報）
  - 🔥 點煙偵測
  - 🚬 吸煙場景（觸發完整警示流程）
- 📡 **即時感測器數值** — 模擬 MQ-135 數據變化
- 📊 **信心度面板** — 三路辨識信心度即時顯示

### 後台儀表板 (dashboard.html)
- 📹 **四路攝影機** — 即時 Canvas 模擬
- 📈 **24小時趨勢圖** — 違規事件時間分布
- 🗺️ **熱點分析熱力圖** — 時段 × 位置矩陣
- 📋 **違規事件紀錄表** — 可匯出 CSV
- 🌡️ **感測器即時數值** — 動態更新模擬

## 🔧 技術規格

| 項目 | 說明 |
|------|------|
| 前端框架 | 純 HTML / CSS / JavaScript |
| 外部依賴 | Google Fonts（CDN） |
| 瀏覽器相容 | Chrome / Firefox / Safari / Edge |
| 部署需求 | 靜態網頁，無需後端伺服器 |

## 📌 注意事項

- 本 Demo 為**純前端模擬**，所有感測數據與影像均為程式產生
- 實際系統需串接 YOLOv8 推論引擎、MediaPipe SDK 與 MQ-135 硬體
- 個人資料保護相關機制（臉部打碼）在實際部署時需進行合規審查

## 👥 系統架構

```
INPUT 輸入層          AI 辨識層              OUTPUT 輸出層
─────────────    ───────────────────    ──────────────────
監控攝影機     →  YOLOv8 物件偵測    →  即時廣播警示
MQ-135 感測器  →  MediaPipe 姿態分析  →  臉部打碼回傳
               →  多模態融合判斷     →  後端管理平台
```

---
*SmokeSentry AI — 智慧校園健康管理解決方案*
