from ultralytics import YOLO
import torch

def main():
    # GPU 확인
    print("CUDA 사용 가능:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    # 데이터셋 경로
    data_yaml = "/home/ayaori/Capstone/data_set/FireExtinguisher_gauge.v2i.yolov11/data.yaml"

    # YOLOv11 nano 모델 로드 (가볍고 실시간에 좋음)
    model = YOLO("yolo11n.pt")

    # 학습 시작
    model.train(
        
        data=data_yaml,
        epochs=100,        # 처음엔 50~100
        imgsz=640,
        batch=16,          # VRAM 부족하면 8
        device=0,          # GPU 사용
        workers=8,
        project="Capstone",
        name="pressure_gauge",
        exist_ok=True
    )

if __name__ == "__main__":
    main()
