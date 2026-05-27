"""
SmokeSentry 通知診斷腳本
執行方式：python test_notify.py

這個腳本不需要啟動 Flask server，直接測試 LINE 和 Email 是否能送達。
"""

import smtplib
import urllib.request
import urllib.error
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─────────────────────────────────────────────────────
#  ⚙️  設定區：確認這三個值都正確
# ─────────────────────────────────────────────────────

# Gmail SMTP
SENDER_EMAIL = 'smokesentry.ai.alert@gmail.com'
APP_PASSWORD  = 'zfjv ngtx nnou nztq'           # Gmail App Password（含空格）

# ⚠️  收件人：填你真正想收到警報信的信箱（可以和寄件人相同）
RECIPIENT_EMAIL = 'smokesentry.ai.alert@gmail.com'   # ← 換成你要收信的 Email

# LINE Messaging API
# ⚠️  這裡必須填「Long-lived Channel Access Token」
#     取得方式：https://developers.line.biz/console/
#       → 選你的 Channel → Messaging API → Channel access token → Issue
LINE_TOKEN   = ''   # ← 貼上 Long-lived Channel Access Token（很長的字串）
LINE_USER_ID = 'U7096788b7ec534ad48ca473335c38aac'

# ─────────────────────────────────────────────────────

def test_email():
    print("\n" + "="*50)
    print("  📧 Email SMTP 測試")
    print("="*50)
    print(f"  寄件人：{SENDER_EMAIL}")
    print(f"  收件人：{RECIPIENT_EMAIL}")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = '【SmokeSentry】✅ 通知測試成功'
    msg['From']    = f'SmokeSentry AI <{SENDER_EMAIL}>'
    msg['To']      = RECIPIENT_EMAIL
    body = '這是 SmokeSentry 通知診斷測試信，收到此信表示 Email 設定正確。'
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(SENDER_EMAIL, APP_PASSWORD)
            srv.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
        print("  結果：✅ 發送成功！請檢查收件匣（含垃圾郵件資料夾）")
    except smtplib.SMTPAuthenticationError as e:
        print(f"  結果：❌ 認證失敗")
        print(f"  原因：{e}")
        print()
        print("  常見原因與解法：")
        print("  1. App Password 格式錯誤 → 確認是 16 碼，含空格也可以")
        print("  2. Gmail 帳號未開啟兩步驟驗證 → 需先啟用才能使用 App Password")
        print("  3. App Password 是給『其他應用程式』而非 Gmail → 確認類型正確")
    except Exception as e:
        print(f"  結果：❌ 失敗：{e}")


def test_line():
    print("\n" + "="*50)
    print("  💬 LINE Bot 推播測試")
    print("="*50)

    if not LINE_TOKEN:
        print("  結果：⚠️  尚未填入 LINE_TOKEN")
        print()
        print("  取得步驟：")
        print("  1. 前往 https://developers.line.biz/console/")
        print("  2. 選擇你的 Channel（Messaging API 類型）")
        print("  3. 點選『Messaging API』頁籤")
        print("  4. 往下找『Channel access token』→ 點『Issue』")
        print("  5. 複製生成的 Token（很長，約 174 個字元）貼入 LINE_TOKEN")
        print()
        print("  ⚠️  注意：Channel Secret ≠ Channel Access Token")
        print("     Channel Secret = b48958f7ace83369c958dba4e24256b7（短，32碼）")
        print("     Channel Access Token = 很長的字串，從 Issue 按鈕取得")
        return

    print(f"  Token 前10碼：{LINE_TOKEN[:10]}...")
    print(f"  目標 User ID：{LINE_USER_ID}")

    payload = json.dumps({
        'to': LINE_USER_ID,
        'messages': [{'type': 'text', 'text': '✅ SmokeSentry LINE Bot 測試成功！\n通知功能正常運作。'}]
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.line.me/v2/bot/message/push',
        data=payload,
        headers={
            'Content-Type':  'application/json',
            'Authorization': f'Bearer {LINE_TOKEN}',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  結果：✅ 推播成功！HTTP {resp.status}")
            print("  請查看 LINE App，應該已收到訊息")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        print(f"  結果：❌ HTTP {e.code} 錯誤")
        print(f"  回應：{body}")
        print()
        if e.code == 401:
            print("  原因：Token 無效或過期")
            print("  解法：回到 LINE Developers Console 重新 Issue 一個新 Token")
        elif e.code == 400:
            print("  原因：User ID 格式錯誤，或該 User 尚未加 Bot 為好友")
            print("  解法：確認 User ID 以 'U' 開頭，且已加 Bot 好友")
    except Exception as e:
        print(f"  結果：❌ 連線失敗：{e}")


if __name__ == '__main__':
    print("\nSmokeSentry 通知診斷工具")
    print("─" * 50)
    test_email()
    test_line()
    print("\n" + "="*50)
    print("  診斷完成")
    print("="*50 + "\n")
