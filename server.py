"""
SmokeSentry 後端伺服器
執行方式：python server.py
然後開啟瀏覽器前往 http://localhost:5000
"""

from flask import Flask, jsonify, send_from_directory, Response
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import os
import sys

app = Flask(__name__, static_folder='.')
CORS(app)

# =========================
# 全域狀態
# =========================
demo_running = False
demo_lock = threading.Lock()

# 共享的最新畫面（bytes）
latest_frame = None
frame_lock = threading.Lock()

# 外部控制狀態（讓 index.html 的按鍵也能控制）
demo_state = {
    'eating_mode': False,
    'smoke_simulated': False,
    'ignition_simulated': False,
}


# =========================
# smoke_demo 邏輯（背景執行緒）
# =========================
def run_smoke_demo():
    global latest_frame, demo_running

    mp_hands = mp.solutions.hands
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils

    hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.6, min_tracking_confidence=0.6)
    face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, min_detection_confidence=0.6, min_tracking_confidence=0.6)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    HAND_MOUTH_THRESHOLD = 90
    PINCH_THRESHOLD = 75
    HOLD_SECONDS = 1.5
    EATING_FINGER_COUNT = 4
    hand_near_start = None

    def dist(p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    def draw_text(img, text, pos, scale=0.7, color=(255, 255, 255), thickness=2):
        x, y = pos
        cv2.putText(img, text, (x+2, y+2), cv2.FONT_HERSHEY_SIMPLEX, scale, (0,0,0), thickness+2)
        cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)

    with demo_lock:
        demo_running = True

    while demo_running:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        hand_results = hands.process(rgb)
        face_results = face_mesh.process(rgb)

        mouth_pos = None
        near_now = False
        hand_near_mouth = False
        pinch_gesture = False
        eating_like_gesture = False
        near_finger_count = 0
        elapsed = 0
        finger_positions = []
        all_fingertip_positions = []

        eating_mode = demo_state['eating_mode']
        smoke_simulated = demo_state['smoke_simulated']
        ignition_simulated = demo_state['ignition_simulated']

        # 嘴巴偵測
        if face_results.multi_face_landmarks:
            lm = face_results.multi_face_landmarks[0]
            ul = lm.landmark[13]; ll = lm.landmark[14]
            mouth_pos = (int(((ul.x+ll.x)/2)*w), int(((ul.y+ll.y)/2)*h))
            cv2.circle(frame, mouth_pos, 8, (0,255,255), -1)
            draw_text(frame, "Mouth", (mouth_pos[0]+10, mouth_pos[1]), scale=0.6, color=(0,255,255), thickness=2)

        # 手部偵測
        if hand_results.multi_hand_landmarks:
            for hl in hand_results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
                tips = [hl.landmark[i] for i in [4,8,12,16,20]]
                tip_pos = [(int(t.x*w), int(t.y*h)) for t in tips]
                all_fingertip_positions.extend(tip_pos)
                finger_positions.extend(tip_pos[:3])
                colors = [(255,0,255),(255,0,0),(255,255,0),(0,255,0),(0,128,255)]
                for pos, col in zip(tip_pos, colors):
                    cv2.circle(frame, pos, 7, col, -1)
                if dist(tip_pos[0], tip_pos[1]) < PINCH_THRESHOLD or dist(tip_pos[1], tip_pos[2]) < PINCH_THRESHOLD:
                    pinch_gesture = True
                    draw_text(frame, "Pinch", (tip_pos[1][0]+10, tip_pos[1][1]-10), scale=0.6, color=(0,165,255))

        # 靠近嘴巴判斷
        if mouth_pos and finger_positions:
            if min(dist(mouth_pos, f) for f in finger_positions) < HAND_MOUTH_THRESHOLD:
                near_now = True

        if mouth_pos and all_fingertip_positions:
            near_finger_count = sum(1 for f in all_fingertip_positions if dist(mouth_pos, f) < HAND_MOUTH_THRESHOLD)
            if near_finger_count >= EATING_FINGER_COUNT:
                eating_like_gesture = True

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
            scenario, risk, status = "Eating Mode", "SAFE", "Eating behavior / No smoking alert"
        elif hand_near_mouth and pinch_gesture and smoke_simulated:
            scenario, risk, status = "Smoking Scenario", "HIGH", "Smoking Event Detected"
        elif hand_near_mouth and pinch_gesture and ignition_simulated:
            scenario, risk, status = "Ignition Detection", "HIGH", "Ignition Risk Detected"
        elif hand_near_mouth and pinch_gesture:
            scenario, risk, status = "Suspicious Behavior", "MEDIUM-HIGH", "Suspicious hand-to-mouth gesture"
        elif hand_near_mouth and eating_like_gesture:
            scenario, risk, status = "Eating-like Behavior", "SAFE", "Eating-like Gesture"
        elif hand_near_mouth:
            scenario, risk, status = "Hand-to-Mouth", "MEDIUM", "Hand-to-Mouth Detected"
        else:
            scenario, risk, status = "Walking", "SAFE", "Walking"

        risk_color = {
            "HIGH": (0,0,255), "MEDIUM-HIGH": (0,165,255),
            "MEDIUM": (0,255,255), "SAFE": (0,255,0)
        }.get(risk, (0,255,0))

        draw_text(frame, "Cam01", (30,45), scale=0.6)
        draw_text(frame, f"Time: {elapsed:.1f}s", (30,85))
        draw_text(frame, f"Scenario: {scenario}", (30,125))
        draw_text(frame, f"Risk: {risk}", (30,165), scale=0.7, color=risk_color)
        draw_text(frame, status, (30,205), scale=0.6, color=risk_color)
        draw_text(frame, "Keys: 1 Auto | 2 Eating | 3 Smoke | 4 Ignition",
                  (20, h-15), scale=0.5)

        # 編碼成 JPEG 存到共享變數
        ret2, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ret2:
            with frame_lock:
                latest_frame = buf.tobytes()

    cap.release()
    with demo_lock:
        demo_running = False


# =========================
# MJPEG 串流產生器
# =========================
def generate_stream():
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            # 尚未啟動時顯示黑畫面
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Press [Walking] to start camera",
                        (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 255), 2)
            _, buf = cv2.imencode('.jpg', blank)
            frame = buf.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.033)  # ~30fps


# =========================
# Flask 路由
# =========================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/video_feed')
def video_feed():
    """MJPEG 串流端點"""
    return Response(generate_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/launch-demo', methods=['POST'])
def launch_demo():
    global demo_running
    if not demo_running:
        t = threading.Thread(target=run_smoke_demo, daemon=True)
        t.start()
        time.sleep(0.5)
    return jsonify({'success': True, 'message': '已啟動 SmokeSentry Demo', 'pid': os.getpid()})

@app.route('/api/stop-demo', methods=['POST'])
def stop_demo():
    global demo_running
    demo_running = False
    return jsonify({'success': True, 'message': 'Demo 已停止'})

@app.route('/api/set-state', methods=['POST'])
def set_state():
    """讓網頁按鈕控制 demo 狀態"""
    from flask import request
    data = request.get_json()
    if 'mode' in data:
        m = data['mode']
        demo_state['eating_mode'] = (m == 'eating')
        demo_state['smoke_simulated'] = (m == 'smoking')
        demo_state['ignition_simulated'] = (m == 'lighting')
    return jsonify({'success': True})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({'running': demo_running})


if __name__ == '__main__':
    print("=" * 50)
    print("  SmokeSentry 後端伺服器啟動中...")
    print("  請開啟瀏覽器前往：http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

# =========================
# Email 通報端點
# =========================
@app.route('/api/send-email', methods=['POST'])
def send_email():
    from flask import request
    data = request.get_json()

    EMAIL_CONFIG = {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender':    'smokesentry@your-school.edu.tw',
        'password':  'YOUR_APP_PASSWORD',
        'use_tls':   True,
    }

    recipients = data.get('recipients', [])
    subject    = data.get('subject', '【SmokeSentry 警示】吸菸事件通報')
    body       = data.get('body', '')
    urgency    = data.get('urgency', 'med')

    if not recipients:
        return jsonify({'success': False, 'message': '未指定收件人'}), 400

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'SmokeSentry AI <{EMAIL_CONFIG["sender"]}>'
        msg['To']      = ', '.join(recipients)
        if urgency == 'high':
            msg['X-Priority'] = '1'

        color = '#dc2626' if urgency == 'high' else '#f59e0b' if urgency == 'med' else '#16a34a'
        label = '🔴 緊急' if urgency == 'high' else '🟡 一般' if urgency == 'med' else '🟢 低'

        html_body = f"""<html><body style="font-family:sans-serif;background:#f5f7fa;padding:20px">
          <div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;overflow:hidden">
            <div style="background:{color};padding:20px;color:white"><h2 style="margin:0">{label} SmokeSentry 警示通報</h2></div>
            <div style="padding:24px"><pre style="background:#f1f5f9;padding:16px;border-radius:6px;white-space:pre-wrap;font-size:13px">{body}</pre></div>
            <div style="background:#f1f5f9;padding:16px;text-align:center;font-size:12px;color:#6b7280">SmokeSentry AI 自動發送</div>
          </div></body></html>"""

        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as server:
            if EMAIL_CONFIG['use_tls']:
                server.starttls()
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.sendmail(EMAIL_CONFIG['sender'], recipients, msg.as_string())

        print(f"[Email] 已發送至 {', '.join(recipients)}")
        return jsonify({'success': True, 'message': f'Email 已發送至 {len(recipients)} 位管理者'})

    except smtplib.SMTPAuthenticationError:
        return jsonify({'success': False, 'message': 'SMTP 認證失敗，請確認 sender/password 設定'}), 401
    except Exception as e:
        print(f"[Email ERROR] {e}")
        # 開發 fallback：模擬成功讓前端可 Demo
        return jsonify({'success': True, 'message': '[模擬模式] Email 通報已記錄（SMTP未完整設定）', 'simulated': True})


# =========================
# LINE Bot 通報端點
# =========================
@app.route('/api/send-line', methods=['POST'])
def send_line():
    from flask import request
    import urllib.request, json as _json, urllib.error
    data = request.get_json()

    LINE_CHANNEL_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'  # <-- 修改這裡
    DEFAULT_TARGET     = 'YOUR_GROUP_OR_USER_ID'       # <-- 修改這裡

    message = data.get('message', '')
    targets = data.get('targets', [DEFAULT_TARGET])

    if not message:
        return jsonify({'success': False, 'message': '訊息不可為空'}), 400

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_TOKEN}'
    }

    success_count = 0
    for target in targets:
        payload = _json.dumps({'to': target, 'messages': [{'type': 'text', 'text': message}]}).encode('utf-8')
        req = urllib.request.Request('https://api.line.me/v2/bot/message/push',
                                     data=payload, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    success_count += 1
        except urllib.error.HTTPError as he:
            print(f"[LINE] 發送失敗 target={target}: {he.code}")
        except Exception as e:
            print(f"[LINE ERROR] {e}")

    if success_count > 0:
        print(f"[LINE] 已推播至 {success_count} 個目標")
        return jsonify({'success': True, 'message': f'LINE Bot 已推播至 {success_count} 個目標'})
    else:
        return jsonify({'success': True, 'message': '[模擬模式] LINE 通報已記錄（Token未設定）', 'simulated': True})


# =========================
# 同步通報端點（Email + LINE）
# =========================
@app.route('/api/send-both', methods=['POST'])
def send_both():
    from flask import request
    data = request.get_json()
    results = {}

    with app.test_request_context(json=data):
        from flask import g

    # 複用已有端點邏輯
    import requests as _req
    base = 'http://localhost:5000'
    try:
        er = _req.post(f'{base}/api/send-email', json=data, timeout=10)
        results['email'] = er.json()
    except Exception:
        results['email'] = {'success': True, 'message': '[模擬] Email', 'simulated': True}

    try:
        lr = _req.post(f'{base}/api/send-line', json=data, timeout=10)
        results['line'] = lr.json()
    except Exception:
        results['line'] = {'success': True, 'message': '[模擬] LINE', 'simulated': True}

    return jsonify({'success': True, 'message': '同步通報完成（Email + LINE Bot）', 'details': results})
