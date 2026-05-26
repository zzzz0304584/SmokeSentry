"""
SmokeSentry 後端伺服器 v1.3
執行方式：python server.py
開啟瀏覽器：http://localhost:5000
"""

from flask import Flask, jsonify, send_from_directory, Response, request
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import os
import smtplib
import urllib.request
import urllib.error
import json as _json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__, static_folder='.')
CORS(app)

# ============================================================
# 設定區（已填入真實 API 金鑰）
# ============================================================

# Gmail SMTP — App Password
EMAIL_CONFIG = {
    'smtp_host': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender':    'smokesentry.ai.alert@gmail.com',   # 寄件 Gmail
    'password':  'zfjv ngtx nnou nztq',               # Gmail App Password
    'use_tls':   True,
}

# LINE Messaging API
LINE_CONFIG = {
    'channel_id':     '2010200164',
    'channel_secret': 'b48958f7ace83369c958dba4e24256b7',
    'channel_token':  'b48958f7ace83369c958dba4e24256b7',  # Channel Secret 作 Token（請視情況換成 Long-lived token）
    'default_target': 'U7096788b7ec534ad48ca473335c38aac',  # User ID
}

# ============================================================
# 全域狀態
# ============================================================
demo_running = False
demo_lock    = threading.Lock()
latest_frame = None
frame_lock   = threading.Lock()

demo_state = {
    'eating_mode':       False,
    'smoke_simulated':   False,
    'ignition_simulated':False,
}

# 警示事件 queue（供前端輪詢）
alert_queue = []
alert_lock  = threading.Lock()


# ============================================================
# 工具函式
# ============================================================
def push_alert(event_type: str, confidence: float, location: str = 'CAM-01'):
    """記錄一筆警示事件，並同時送出 LINE 通知"""
    entry = {
        'time':       time.strftime('%H:%M:%S'),
        'type':       event_type,
        'confidence': round(confidence, 1),
        'location':   location,
    }
    with alert_lock:
        alert_queue.insert(0, entry)
        if len(alert_queue) > 50:
            alert_queue.pop()

    # 背景發送 LINE 通知（不阻塞串流）
    msg = (
        f"🚨 SmokeSentry 即時警示\n"
        f"━━━━━━━━━━━━━━\n"
        f"📍 地點：{location}\n"
        f"🕐 時間：{entry['time']}\n"
        f"🎯 類型：{event_type}\n"
        f"📊 信心度：{confidence:.1f}%\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚠️ 請立即前往查看"
    )
    threading.Thread(target=_send_line_sync,
                     args=([LINE_CONFIG['default_target']], msg),
                     daemon=True).start()


def _send_line_sync(targets: list, message: str):
    """直接呼叫 LINE API（同步，在子執行緒中執行）"""
    # 先嘗試用 Channel Secret 當 Bearer Token
    # 正式環境請換成 Long-lived channel access token（從 LINE Developers Console 取得）
    token = LINE_CONFIG['channel_token']
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
    }
    for target in targets:
        payload = _json.dumps({
            'to': target,
            'messages': [{'type': 'text', 'text': message}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.line.me/v2/bot/message/push',
            data=payload, headers=headers, method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                print(f"[LINE] ✓ 推播至 {target}  status={resp.status}")
        except urllib.error.HTTPError as he:
            body = he.read().decode('utf-8', errors='ignore')
            print(f"[LINE] ✗ HTTPError {he.code}: {body}")
        except Exception as e:
            print(f"[LINE] ✗ {e}")


def _send_email_sync(recipients: list, subject: str, body: str, urgency: str = 'med'):
    """直接呼叫 SMTP（同步，在子執行緒中執行）"""
    color = '#dc2626' if urgency == 'high' else '#f59e0b' if urgency == 'med' else '#16a34a'
    label = '🔴 緊急' if urgency == 'high' else '🟡 一般' if urgency == 'med' else '🟢 低'

    html_body = f"""
    <html><body style="font-family:sans-serif;background:#f5f7fa;padding:20px;margin:0">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08)">
        <div style="background:{color};padding:22px 28px;color:white">
          <h2 style="margin:0;font-size:20px">{label} SmokeSentry 警示通報</h2>
          <p style="margin:6px 0 0;opacity:.85;font-size:13px">SmokeSentry AI 校園吸煙智慧辨識系統</p>
        </div>
        <div style="padding:28px">
          <pre style="background:#f8fafc;border:1px solid #e2e8f0;padding:18px;border-radius:8px;
                      white-space:pre-wrap;font-family:'Courier New',monospace;font-size:13px;
                      line-height:1.7;color:#334155;margin:0">{body}</pre>
        </div>
        <div style="background:#f1f5f9;padding:16px 28px;text-align:center;
                    font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0">
          此訊息由 SmokeSentry AI 自動發送 ·
          <a href="http://localhost:5000/dashboard.html" style="color:#3b82f6">開啟後台管理</a>
        </div>
      </div>
    </body></html>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'SmokeSentry AI <{EMAIL_CONFIG["sender"]}>'
    msg['To']      = ', '.join(recipients)
    if urgency == 'high':
        msg['X-Priority'] = '1'
        msg['X-MSMail-Priority'] = 'High'
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port'], timeout=15) as srv:
            if EMAIL_CONFIG['use_tls']:
                srv.ehlo()
                srv.starttls()
                srv.ehlo()
            srv.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            srv.sendmail(EMAIL_CONFIG['sender'], recipients, msg.as_string())
        print(f"[Email] ✓ 已發送至 {', '.join(recipients)}")
        return True, None
    except smtplib.SMTPAuthenticationError as e:
        print(f"[Email] ✗ 認證失敗: {e}")
        return False, f'SMTP 認證失敗：{e}'
    except smtplib.SMTPException as e:
        print(f"[Email] ✗ SMTP 錯誤: {e}")
        return False, str(e)
    except Exception as e:
        print(f"[Email] ✗ 未知錯誤: {e}")
        return False, str(e)


# ============================================================
# MediaPipe 偵測執行緒
# ============================================================
def run_smoke_demo():
    global latest_frame, demo_running

    mp_hands    = mp.solutions.hands
    mp_face     = mp.solutions.face_mesh
    mp_drawing  = mp.solutions.drawing_utils

    hands     = mp_hands.Hands(max_num_hands=2,
                               min_detection_confidence=0.6,
                               min_tracking_confidence=0.6)
    face_mesh = mp_face.FaceMesh(max_num_faces=1,
                                  min_detection_confidence=0.6,
                                  min_tracking_confidence=0.6)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    HAND_MOUTH_THRESHOLD = 90
    PINCH_THRESHOLD      = 75
    HOLD_SECONDS         = 1.5
    EATING_FINGER_COUNT  = 4
    hand_near_start      = None
    last_alert_time      = 0
    ALERT_COOLDOWN       = 15   # 秒，避免重複觸發

    def dist(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    def draw_text(img, text, pos, scale=0.65, color=(255,255,255), thickness=2):
        x, y = pos
        cv2.putText(img, text, (x+2, y+2), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (0,0,0), thickness+2, cv2.LINE_AA)
        cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness, cv2.LINE_AA)

    with demo_lock:
        demo_running = True

    print("[Camera] 攝影機開啟中…")

    while demo_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        hand_results = hands.process(rgb)
        face_results = face_mesh.process(rgb)

        # 讀取當前外部控制狀態
        eating_mode       = demo_state['eating_mode']
        smoke_simulated   = demo_state['smoke_simulated']
        ignition_simulated= demo_state['ignition_simulated']

        mouth_pos          = None
        near_now           = False
        pinch_gesture      = False
        eating_like_gesture= False
        finger_positions   = []
        all_fingertip_pos  = []
        elapsed            = 0

        # 嘴巴偵測
        if face_results.multi_face_landmarks:
            lm = face_results.multi_face_landmarks[0]
            ul = lm.landmark[13]; ll = lm.landmark[14]
            mouth_pos = (int(((ul.x+ll.x)/2)*w),
                         int(((ul.y+ll.y)/2)*h))
            cv2.circle(frame, mouth_pos, 8, (0,255,255), -1)
            draw_text(frame, 'Mouth', (mouth_pos[0]+10, mouth_pos[1]),
                      scale=0.55, color=(0,255,255))

        # 手部偵測
        if hand_results.multi_hand_landmarks:
            for hl in hand_results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
                tips    = [hl.landmark[i] for i in [4,8,12,16,20]]
                tip_pos = [(int(t.x*w), int(t.y*h)) for t in tips]
                all_fingertip_pos.extend(tip_pos)
                finger_positions.extend(tip_pos[:3])
                colors  = [(255,0,255),(255,0,0),(255,255,0),(0,255,0),(0,128,255)]
                for pos, col in zip(tip_pos, colors):
                    cv2.circle(frame, pos, 7, col, -1)
                if (dist(tip_pos[0], tip_pos[1]) < PINCH_THRESHOLD or
                        dist(tip_pos[1], tip_pos[2]) < PINCH_THRESHOLD):
                    pinch_gesture = True
                    draw_text(frame, 'Pinch',
                              (tip_pos[1][0]+10, tip_pos[1][1]-10),
                              scale=0.55, color=(0,165,255))

        # 距離判斷
        if mouth_pos and finger_positions:
            if min(dist(mouth_pos, f) for f in finger_positions) < HAND_MOUTH_THRESHOLD:
                near_now = True
        if mouth_pos and all_fingertip_pos:
            if sum(1 for f in all_fingertip_pos
                   if dist(mouth_pos, f) < HAND_MOUTH_THRESHOLD) >= EATING_FINGER_COUNT:
                eating_like_gesture = True

        # 持續時間
        if near_now:
            if hand_near_start is None:
                hand_near_start = time.time()
            elapsed = time.time() - hand_near_start
            hand_near_mouth = elapsed >= HOLD_SECONDS
        else:
            hand_near_start = None
            elapsed = 0
            hand_near_mouth = False

        # 情境判斷
        if eating_mode:
            scenario, risk = 'Eating Mode',           'SAFE'
        elif hand_near_mouth and pinch_gesture and smoke_simulated:
            scenario, risk = 'Smoking Detected',      'HIGH'
        elif hand_near_mouth and pinch_gesture and ignition_simulated:
            scenario, risk = 'Ignition Detected',     'HIGH'
        elif hand_near_mouth and pinch_gesture:
            scenario, risk = 'Suspicious Behavior',   'MEDIUM-HIGH'
        elif hand_near_mouth and eating_like_gesture:
            scenario, risk = 'Eating-like Behavior',  'SAFE'
        elif hand_near_mouth:
            scenario, risk = 'Hand-to-Mouth',         'MEDIUM'
        else:
            scenario, risk = 'Normal',                'SAFE'

        risk_color = {
            'HIGH':        (0,0,255),
            'MEDIUM-HIGH': (0,100,255),
            'MEDIUM':      (0,200,255),
            'SAFE':        (0,220,0),
        }.get(risk, (0,220,0))

        # 自動警示通報（HIGH risk，有冷卻時間）
        if risk == 'HIGH' and (time.time() - last_alert_time) > ALERT_COOLDOWN:
            last_alert_time = time.time()
            conf = 94.0 if smoke_simulated else 88.0
            push_alert(scenario, conf, 'CAM-01 廁所外走廊 B棟')
            print(f"[Alert] 觸發警示 → {scenario}  conf={conf}%")

        # HUD 覆蓋
        overlay = frame.copy()
        cv2.rectangle(overlay, (0,0), (w, 55), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        draw_text(frame, 'SmokeSentry CAM-01',  (12, 22), scale=0.6)
        draw_text(frame, time.strftime('%H:%M:%S'), (w-110, 22), scale=0.6)
        draw_text(frame, f'Scenario : {scenario}', (12, 80), scale=0.6, color=risk_color)
        draw_text(frame, f'Risk     : {risk}',     (12,110), scale=0.6, color=risk_color)
        draw_text(frame, f'Hold     : {elapsed:.1f}s', (12,140), scale=0.55)
        draw_text(frame, '1:Auto  2:Eating  3:Smoke  4:Ignition',
                  (12, h-12), scale=0.45, color=(180,180,180))

        if risk == 'HIGH':
            # 紅色警示邊框
            cv2.rectangle(frame, (0,0), (w-1,h-1), (0,0,255), 3)
            draw_text(frame, '! ALERT !', (w//2-50, h//2),
                      scale=1.2, color=(0,0,255), thickness=3)

        ret2, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if ret2:
            with frame_lock:
                latest_frame = buf.tobytes()

    cap.release()
    with demo_lock:
        demo_running = False
    print("[Camera] 攝影機已釋放")


# ============================================================
# MJPEG 串流
# ============================================================
def generate_stream():
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, 'Press [Walking] to start camera',
                        (60, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,180,255), 2)
            _, buf = cv2.imencode('.jpg', blank)
            frame  = buf.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.033)


# ============================================================
# Flask 路由 — 靜態頁面
# ============================================================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


# ============================================================
# Flask 路由 — 攝影機 API
# ============================================================
@app.route('/video_feed')
def video_feed():
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/launch-demo', methods=['POST'])
def launch_demo():
    global demo_running
    if not demo_running:
        t = threading.Thread(target=run_smoke_demo, daemon=True)
        t.start()
        time.sleep(0.6)
    return jsonify({'success': True,
                    'message': '已啟動 SmokeSentry 攝影機（MediaPipe）'})

@app.route('/api/stop-demo', methods=['POST'])
def stop_demo():
    global demo_running
    demo_running = False
    return jsonify({'success': True, 'message': '攝影機已停止'})

@app.route('/api/set-state', methods=['POST'])
def set_state():
    data = request.get_json()
    if 'mode' in data:
        m = data['mode']
        demo_state['eating_mode']        = (m == 'eating')
        demo_state['smoke_simulated']    = (m == 'smoking')
        demo_state['ignition_simulated'] = (m == 'lighting')
    return jsonify({'success': True})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'running': demo_running})

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """讓前端輪詢最新警示"""
    with alert_lock:
        return jsonify({'alerts': alert_queue[:20]})


# ============================================================
# Flask 路由 — Email 通報
# ============================================================
@app.route('/api/send-email', methods=['POST'])
def send_email():
    data       = request.get_json() or {}
    recipients = data.get('recipients', [])
    subject    = data.get('subject',    '【SmokeSentry 警示】吸菸事件通報')
    body       = data.get('body',       '（無內容）')
    urgency    = data.get('urgency',    'med')

    if not recipients:
        return jsonify({'success': False, 'message': '未指定收件人'}), 400

    ok, err = _send_email_sync(recipients, subject, body, urgency)
    if ok:
        return jsonify({'success': True,
                        'message': f'Email 已成功發送至 {len(recipients)} 位管理者',
                        'recipients': recipients})
    else:
        return jsonify({'success': False, 'message': err or 'Email 發送失敗'}), 500


# ============================================================
# Flask 路由 — LINE Bot 通報
# ============================================================
@app.route('/api/send-line', methods=['POST'])
def send_line():
    data    = request.get_json() or {}
    message = data.get('message', '')
    targets = data.get('targets', [LINE_CONFIG['default_target']])

    if not message:
        return jsonify({'success': False, 'message': '訊息不可為空'}), 400
    if not targets:
        targets = [LINE_CONFIG['default_target']]

    token   = LINE_CONFIG['channel_token']
    headers = {
        'Content-Type':  'application/json',
        'Authorization': f'Bearer {token}',
    }

    success_count = 0
    errors        = []

    for target in targets:
        payload = _json.dumps({
            'to': target,
            'messages': [{'type': 'text', 'text': message}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.line.me/v2/bot/message/push',
            data=payload, headers=headers, method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    success_count += 1
                    print(f"[LINE] ✓ 推播至 {target}")
        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8', errors='ignore')
            print(f"[LINE] ✗ {he.code}: {err_body}")
            errors.append(f'{target}: HTTP {he.code}')
        except Exception as e:
            print(f"[LINE] ✗ {e}")
            errors.append(str(e))

    if success_count > 0:
        return jsonify({'success': True,
                        'message': f'LINE Bot 已推播至 {success_count} 個目標',
                        'count': success_count})
    else:
        return jsonify({'success': False,
                        'message': f'LINE 推播失敗，請確認 Channel Token 是否正確',
                        'errors': errors}), 500


# ============================================================
# Flask 路由 — 同步通報（Email + LINE）
# ============================================================
@app.route('/api/send-both', methods=['POST'])
def send_both():
    data       = request.get_json() or {}
    recipients = data.get('recipients', [])
    subject    = data.get('subject',    '【SmokeSentry 警示】吸菸事件通報')
    body       = data.get('body',       '')
    urgency    = data.get('urgency',    'med')
    message    = data.get('message',    body)
    targets    = data.get('targets',    [LINE_CONFIG['default_target']])

    results = {}

    # Email
    if recipients:
        ok, err = _send_email_sync(recipients, subject, body, urgency)
        results['email'] = {
            'success': ok,
            'message': f'Email 已發送至 {len(recipients)} 位' if ok else (err or '失敗')
        }
    else:
        results['email'] = {'success': False, 'message': '未指定收件人'}

    # LINE
    line_ok, line_err_count = True, 0
    token   = LINE_CONFIG['channel_token']
    headers = {
        'Content-Type':  'application/json',
        'Authorization': f'Bearer {token}',
    }
    sent_count = 0
    for target in targets:
        payload = _json.dumps({
            'to': target,
            'messages': [{'type': 'text', 'text': message or body}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.line.me/v2/bot/message/push',
            data=payload, headers=headers, method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    sent_count += 1
        except Exception as e:
            line_err_count += 1
            print(f"[LINE/both] ✗ {e}")

    results['line'] = {
        'success': sent_count > 0,
        'message': f'LINE 已推播至 {sent_count} 個目標' if sent_count > 0 else 'LINE 推播失敗'
    }

    all_ok = results['email']['success'] and results['line']['success']
    return jsonify({
        'success': all_ok,
        'message': '同步通報完成（Email + LINE Bot）' if all_ok else '部分通報失敗，請查看 details',
        'details': results
    })


# ============================================================
# 啟動
# ============================================================
if __name__ == '__main__':
    print("=" * 58)
    print("  SmokeSentry AI 後端伺服器 v1.3")
    print("  ──────────────────────────────────────────────")
    print("  開啟瀏覽器前往：http://localhost:5000")
    print()
    print("  API 端點：")
    print("    GET  /video_feed        MJPEG 攝影機串流")
    print("    POST /api/launch-demo   啟動攝影機 + MediaPipe")
    print("    POST /api/stop-demo     停止攝影機")
    print("    POST /api/set-state     切換偵測模式")
    print("    GET  /api/status        查詢運行狀態")
    print("    GET  /api/alerts        最新警示列表")
    print("    POST /api/send-email    Email 通報")
    print("    POST /api/send-line     LINE Bot 推播")
    print("    POST /api/send-both     Email + LINE 同步")
    print()
    print("  LINE Bot  → User ID:", LINE_CONFIG['default_target'])
    print("  Email     → 從:", EMAIL_CONFIG['sender'])
    print("=" * 58)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
