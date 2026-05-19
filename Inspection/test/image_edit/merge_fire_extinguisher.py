import cv2
import numpy as np

# 이미지 경로
path_down = "/home/ayaori/Capstone/capture/FireExtinguisher_down.jpg"
path_up = "/home/ayaori/Capstone/capture/FireExtinguisher_up.jpg"

# 이미지 읽기
img_down = cv2.imread(path_down)
img_up = cv2.imread(path_up)

# 가로 크기 맞추기 (혹시 다를 경우 대비)
if img_down.shape[1] != img_up.shape[1]:
    img_up = cv2.resize(img_up, (img_down.shape[1], img_up.shape[0]))

# 세로 방향으로 합치기
merged = np.vstack((img_up, img_down))

# 저장
cv2.imwrite("/home/ayaori/Capstone/capture/FireExtinguisher_merged.jpg", merged)

print("합치기 완료")