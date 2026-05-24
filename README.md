# 🚭 SmokeSentry AI — 校園吸煙行為智慧辨識與預警系統 v1.3

> 多模態 AI 校園吸煙辨識系統 — 融合真實 MediaPipe 鏡頭偵測 + 完整管理後台

## 🗂️ 檔案結構

```
smokesentry/
├── index.html       # 主頁 + 互動 DEMO（支援真實鏡頭串流）
├── dashboard.html   # 總覽儀表板（CAM-01 真實串流）
├── cameras.html     # 即時攝影機全螢幕（多視角）
├── alerts.html      # 🚨 警示管理（Email + LINE Bot 通報）
├── stats.html       # 統計報表（圖表 + 匯出）
├── heatmap.html     # 熱點分析（熱力圖 + 校園地圖）
├── records.html     # 違規紀錄（搜尋 + 詳情側板）
├── notify.html      # 通知設定（SMTP + LINE Token）
├── settings.html    # 系統設定（AI 參數 + 攝影機管理）
├── server.py        # Flask 後端（MediaPipe + Email + LINE Bot API）
├── smoke_demo.py    # 獨立 OpenCV 視窗版本（本地測試用）
├── shared.css       # 共用樣式
└── shared.js        # 共用 sidebar/topbar/toast
```

---

## 🚀 兩種使用模式

### 模式 A — 靜態 Demo（無需 Python，直接上 GitHub Pages）

所有頁面**不需要後端**即可完整瀏覽：
- Canvas 動畫模擬攝影機畫面
- 所有互動按鈕有 fallback 邏輯
- 通報按鈕顯示「模擬模式」提示

**部署到 GitHub Pages：**
1. 上傳所有 `.html` + `shared.css` + `shared.js`（不需要 `.py`）
2. Settings → Pages → main branch → Save
3. 約 1 分鐘後上線

---

### 模式 B — 完整功能（本地執行，真實鏡頭 + 通報）

#### 1. 安裝依賴

```bash
pip install flask flask-cors opencv-python mediapipe numpy
# Email 使用內建 smtplib（無需額外安裝）
# LINE Bot 使用內建 urllib（無需額外安裝）
```

#### 2. 設定 Email（server.py 第 258–264 行）

```python
EMAIL_CONFIG = {
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender':    'your-account@gmail.com',   # ← 修改
    'password':  'your-app-password',         # ← Gmail App Password
    'use_tls':   True,
}
```

> Gmail 需開啟「兩步驟驗證」並產生「應用程式密碼」
> 設定說明：https://myaccount.google.com/apppasswords

#### 3. 設定 LINE Bot（server.py 第 314–315 行）

```python
LINE_CHANNEL_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'  # ← LINE Messaging API Token
DEFAULT_TARGET     = 'YOUR_GROUP_OR_USER_ID'       # ← 群組 Chat ID (C開頭) 或 User ID (U開頭)
```

> LINE Bot 申請：https://developers.line.biz/console/
> 將 Bot 加入群組後發送訊息，即可從 Webhook 取得 Chat ID

#### 4. 啟動伺服器

```bash
python server.py
```

開啟瀏覽器前往：**http://localhost:5000**

---

## 📡 API 端點一覽

| 端點 | 方法 | 說明 |
|------|------|------|
| `/video_feed` | GET | MJPEG 攝影機串流 |
| `/api/launch-demo` | POST | 啟動 MediaPipe 攝影機 |
| `/api/stop-demo` | POST | 停止攝影機 |
| `/api/set-state` | POST | 切換偵測模式 (normal/eating/smoking/lighting) |
| `/api/status` | GET | 查詢系統運行狀態 |
| `/api/send-email` | POST | 發送 Email 通報 |
| `/api/send-line` | POST | 發送 LINE Bot 推播 |
| `/api/send-both` | POST | Email + LINE 同步通報 |

### API 範例

```json
// POST /api/send-email
{
  "recipients": ["wang@school.edu.tw", "li@school.edu.tw"],
  "subject": "【SmokeSentry 警示】CAM-01 吸菸事件",
  "body": "事件詳情...",
  "urgency": "high"
}

// POST /api/send-line
{
  "message": "🚨 SmokeSentry 警示\n地點：廁所外走廊 B棟\n時間：14:32:07",
  "targets": ["C_your_group_id"]
}
```

---

## 🎮 偵測模式說明

| 按鈕 | 模式 | 說明 |
|------|------|------|
| 😐 正常行走 | normal | 啟動攝影機，Auto 偵測 |
| 🍔 吃東西 | eating | 強制進入吃東西模式（展示多模態排除誤判）|
| 🚬 觸發吸煙 | smoking | 模擬吸菸場景（需手部+夾取姿態）|
| 🔥 點煙偵測 | lighting | 模擬點煙場景 |

---

## 🔧 系統架構

```
真實鏡頭 (cv2)
    ↓
MediaPipe Hands + FaceMesh   ← 姿態估計
    ↓
情境融合判斷邏輯
    ↓
MJPEG Stream → 瀏覽器顯示
    ↓
警示觸發 → Email (smtplib) + LINE Bot (urllib)
```

---

*SmokeSentry AI v1.3 — 智慧校園健康管理解決方案*
