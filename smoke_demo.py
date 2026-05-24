import cv2
import mediapipe as mp
import numpy as np
import time

# =========================
# MediaPipe 初始化
# =========================
mp_hands = mp.solutions.hands
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# =========================
# Camera 初始化
# =========================
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) #目前0是筆電相機，1是外接相機
cv2.namedWindow("SmokeSentry Prototype", cv2.WINDOW_NORMAL)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# =========================
# 狀態變數
# =========================
hand_near_start = None
smoke_simulated = False
ignition_simulated = False
eating_mode = False


HAND_MOUTH_THRESHOLD = 90
PINCH_THRESHOLD = 75
HOLD_SECONDS = 1.5
EATING_FINGER_COUNT = 4


def dist(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))


def draw_text(img, text, pos, scale=0.7, color=(255, 255, 255), thickness=2):
    x, y = pos

    # 黑色陰影
    cv2.putText(
        img, text, (x + 2, y + 2),
        cv2.FONT_HERSHEY_SIMPLEX, scale,
        (0, 0, 0), thickness + 2
    )

    # 主文字
    cv2.putText(
        img, text, (x, y),
        cv2.FONT_HERSHEY_SIMPLEX, scale,
        color, thickness
    )


while True:
    ret, frame = cap.read()

    if not ret:
        print("Cannot open camera")
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
    min_distance = None
    elapsed = 0

    finger_positions = []
    all_fingertip_positions = []

    # =========================
    # 嘴巴偵測
    # =========================
    if face_results.multi_face_landmarks:
        face_landmarks = face_results.multi_face_landmarks[0]

        upper_lip = face_landmarks.landmark[13]
        lower_lip = face_landmarks.landmark[14]

        mouth_x = int(((upper_lip.x + lower_lip.x) / 2) * w)
        mouth_y = int(((upper_lip.y + lower_lip.y) / 2) * h)
        mouth_pos = (mouth_x, mouth_y)

        cv2.circle(frame, mouth_pos, 8, (0, 255, 255), -1)
        draw_text(frame, "Mouth", (mouth_x + 10, mouth_y),
                  scale=0.6, color=(0, 255, 255), thickness=2)

    # =========================
    # 手部偵測
    # =========================
    if hand_results.multi_hand_landmarks:
        for hand_landmarks in hand_results.multi_hand_landmarks:

            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            thumb_tip = hand_landmarks.landmark[4]
            index_tip = hand_landmarks.landmark[8]
            middle_tip = hand_landmarks.landmark[12]
            ring_tip = hand_landmarks.landmark[16]
            pinky_tip = hand_landmarks.landmark[20]

            thumb_pos = (int(thumb_tip.x * w), int(thumb_tip.y * h))
            index_pos = (int(index_tip.x * w), int(index_tip.y * h))
            middle_pos = (int(middle_tip.x * w), int(middle_tip.y * h))
            ring_pos = (int(ring_tip.x * w), int(ring_tip.y * h))
            pinky_pos = (int(pinky_tip.x * w), int(pinky_tip.y * h))

            all_fingertip_positions.extend([
                thumb_pos, index_pos, middle_pos, ring_pos, pinky_pos
            ])

            # 用前三指代表主要手部靠嘴距離
            finger_positions.extend([thumb_pos, index_pos, middle_pos])

            # 畫五根手指尖
            cv2.circle(frame, thumb_pos, 7, (255, 0, 255), -1)
            cv2.circle(frame, index_pos, 7, (255, 0, 0), -1)
            cv2.circle(frame, middle_pos, 7, (255, 255, 0), -1)
            cv2.circle(frame, ring_pos, 7, (0, 255, 0), -1)
            cv2.circle(frame, pinky_pos, 7, (0, 128, 255), -1)

            thumb_index_dist = dist(thumb_pos, index_pos)
            index_middle_dist = dist(index_pos, middle_pos)

            # 夾取姿勢：大拇指+食指 或 食指+中指距離很近
            if thumb_index_dist < PINCH_THRESHOLD or index_middle_dist < PINCH_THRESHOLD:
                pinch_gesture = True
                draw_text(frame, "Pinch Gesture",
                          (index_pos[0] + 10, index_pos[1] - 10),
                          scale=0.6, color=(0, 165, 255), thickness=2)

    # =========================
    # 手是否靠近嘴巴
    # =========================
    if mouth_pos and finger_positions:
        min_distance = min(dist(mouth_pos, f) for f in finger_positions)

        if min_distance < HAND_MOUTH_THRESHOLD:
            near_now = True

    # =========================
    # 吃東西類型：多根手指靠近嘴巴
    # =========================
    if mouth_pos and all_fingertip_positions:
        near_finger_count = sum(
            1 for f in all_fingertip_positions
            if dist(mouth_pos, f) < HAND_MOUTH_THRESHOLD
        )

        if near_finger_count >= EATING_FINGER_COUNT:
            eating_like_gesture = True

    # =========================
    # 持續時間判斷
    # =========================
    if near_now:
        if hand_near_start is None:
            hand_near_start = time.time()

        elapsed = time.time() - hand_near_start
        hand_near_mouth = elapsed >= HOLD_SECONDS
    else:
        hand_near_start = None
        elapsed = 0
        hand_near_mouth = False

    # =========================
    # 情境 + 風險判斷
    # =========================
    if eating_mode:
        scenario = "Eating Mode"
        risk = "SAFE"
        status = "Eating behavior / No smoking alert"

    elif hand_near_mouth and pinch_gesture and smoke_simulated:
        scenario = "Smoking Scenario"
        risk = "HIGH"
        status = "Smoking Event Detected"

    elif hand_near_mouth and pinch_gesture and ignition_simulated:
        scenario = "Ignition Detection"
        risk = "HIGH"
        status = "Ignition Risk Detected"

    elif hand_near_mouth and pinch_gesture:
        scenario = "Suspicious Behavior"
        risk = "MEDIUM-HIGH"
        status = "Suspicious hand-to-mouth gesture"

    elif hand_near_mouth and eating_like_gesture:
        scenario = "Eating-like Behavior"
        risk = "SAFE"
        status = "Eating-like Gesture / No smoking alert"

    elif hand_near_mouth:
        scenario = "Hand-to-Mouth Behavior"
        risk = "MEDIUM"
        status = "Hand-to-Mouth Detected"

    else:
        scenario = "Walking"
        risk = "SAFE"
        status = "Walking"

    # =========================
    # 顏色設定
    # =========================
    if risk == "HIGH":
        risk_color = (0, 0, 255)
    elif risk == "MEDIUM-HIGH":
        risk_color = (0, 165, 255)
    elif risk == "MEDIUM":
        risk_color = (0, 255, 255)
    else:
        risk_color = (0, 255, 0)

    # =========================
    # HUD 顯示
    # =========================
    #draw_hud_panel(frame)

    draw_text(frame, "Cam01", (30, 45),
              scale=0.6, color=(255, 255, 255), thickness=2)

    #if min_distance is not None:
        #draw_text(frame, f"Hand-Mouth Distance: {int(min_distance)} px", (30, 85))
    #else:
        #draw_text(frame, "Hand-Mouth Distance: --", (30, 85))

    draw_text(frame, f"Time: {elapsed:.1f}s", (30, 85))
    draw_text(frame, f"Scenario: {scenario}", (30, 125))
    #draw_text(frame, f"Hand Near Mouth: {hand_near_mouth}", (30, 190))
    #draw_text(frame, f"Pinch Gesture: {pinch_gesture}", (30, 225))
    #draw_text(frame, f"Eating-like Gesture: {eating_like_gesture}", (30, 260))
    #draw_text(frame, f"Near Finger Count: {near_finger_count}", (30, 295))
    #draw_text(frame, f"Smoke Simulated: {smoke_simulated}", (30, 330))
    #draw_text(frame, f"Ignition Simulated: {ignition_simulated}", (30, 365))

    draw_text(frame, f"Risk Level: {risk}", (30, 165),
              scale=0.7, color=risk_color, thickness=2)

    draw_text(frame, status, (30, 205),
              scale=0.6, color=risk_color, thickness=2)

    draw_text(frame,
              "Keys: 1 Auto | 2 Eating | 3 Smoke | 4 Ignition | Q Quit",
              (20, h - 15),
              scale=0.5,
              color=(255, 255, 255),
              thickness=2)

    cv2.imshow("SmokeSentry Prototype", frame)

    # =========================
    # 鍵盤控制
    # =========================
    key = cv2.waitKey(1) & 0xFF

    if key == ord("1"):
        eating_mode = False
        smoke_simulated = False
        ignition_simulated = False
    
    elif key == ord("2"):
        eating_mode = True
        smoke_simulated = False
        ignition_simulated = False

    elif key == ord("3"):
        eating_mode = False
        smoke_simulated = True
        ignition_simulated = False

    elif key == ord("4"):
        eating_mode = False
        ignition_simulated = True
        smoke_simulated = False


    elif key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()