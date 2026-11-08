import cv2
import os

# 현재 파일 위치: RL/img_dataset/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VIDEO_DIR = os.path.join(BASE_DIR, "..", "clean_videos")
OUTPUT_DIR = os.path.join(BASE_DIR, "image")

# 몇 번째 clean video를 사용할지 입력
video_index = input("clean video index: ").strip()

video_path = os.path.join(
    VIDEO_DIR,
    f"clean_video_{video_index}.mp4"
)

if not os.path.exists(video_path):
    print(f"Video not found: {video_path}")
    exit()

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 일단 3초마다 한 장
INTERVAL_SEC = 5

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Failed to open video.")
    exit()

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps

print(f"Video: clean_video_{video_index}.mp4")
print(f"FPS: {fps:.2f}")
print(f"Duration: {duration:.2f} sec")
print(f"Extract interval: {INTERVAL_SEC} sec")

time_sec = 0
count = 0

while time_sec < duration:
    cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)

    ret, frame = cap.read()

    if not ret:
        break

    filename = (
        f"video{video_index}_"
        f"{int(time_sec):05d}s.jpg"
    )

    output_path = os.path.join(OUTPUT_DIR, filename)

    cv2.imwrite(output_path, frame)

    count += 1
    time_sec += INTERVAL_SEC

cap.release()

print(f"Done. Extracted {count} images.")
print(f"Saved to: {OUTPUT_DIR}")