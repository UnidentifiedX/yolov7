import cv2
import dxcam
import keyboard
import math
import numpy as np
from pathlib import Path
import pydirectinput
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow
import sys
import threading
import time
import torch

import cv2
import torch
import torchvision
import torch.backends.cudnn as cudnn
import yaml

from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages, letterbox
from utils.general import check_img_size, check_requirements, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utils import select_device, load_classifier, time_synchronized, TracedModel

is_active = False

def set_active():
    global is_active

    is_active = not is_active
    print("program activated" if is_active else "program deactivated")

def start_window(x, y, w, h):
    global window

    window.setGeometry(x, y, w, h)
    window.setWindowTitle("Valorant AI")

# Set up keyboard hotkey
keyboard.add_hotkey("ctrl+alt+s", set_active)

device = torch.device('cuda:0')
weights = "yolov7_custom2.pt"
conf_thres = 0.5 # default 0.25
iou_thres = 0.2 # default 0.45

# Load model
model = attempt_load(weights, map_location=device)  # load FP32 model
stride = int(model.stride.max())  # model stride
imgsz = check_img_size(img_size=640, s=stride)  # check img_size

model = TracedModel(model, device, img_size=640)
model.half()  # to FP16

# Set Dataloader
dataset = LoadImages("", img_size=imgsz, stride=stride)

# Get names and colors
names = model.module.names if hasattr(model, 'module') else model.names
colors = [[np.random.randint(0, 255) for _ in range(3)] for _ in names]

# Run inference
model(torch.zeros(1, 3, imgsz, imgsz).to(device).type_as(next(model.parameters())))  # run once
old_img_w = old_img_h = imgsz
old_img_b = 1

camera = dxcam.create()
camera.start(target_fps=200, video_mode=True)

start_window(0, 0, 1600, 900)

while True:
    if not is_active:
        cv2.destroyAllWindows()
        continue

    loop_time = time.time()

    # Read image
    img0 = camera.get_latest_frame()

    # Padded resize
    img = letterbox(img0, 640, stride)[0]

    # Convert
    img = img.transpose(2, 0, 1) # to 3x416x416
    img = np.ascontiguousarray(img)

    t0 = time.time()
    img = torch.from_numpy(img).to(device)
    img = img.half() # uint8 to fp16/32
    img /= 255.0  # 0 - 255 to 0.0 - 1.0
    if img.ndimension() == 3:
        img = img.unsqueeze(0)

    # Inference
    t1 = time_synchronized()
    with torch.no_grad():   # Calculating gradients would cause a GPU memory leak
        pred = model(img)[0]
    t2 = time_synchronized()

    # Apply NMS
    pred = non_max_suppression(pred, conf_thres, iou_thres)
    t3 = time_synchronized()

    # Process detections
    for i, det in enumerate(pred):  # detections per image
        s, im0, frame = '', img0, getattr(dataset, 'frame', 0)
        # gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh

    if len(det):
        # Rescale boxes from img_size to im0 size
        det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

        # Write results
        for *xyxy, conf, cls in reversed(det):
            label = f'{names[int(cls)]} {conf:.2f}'
            if names[int(cls)] == "enemy":
                x_avg = int((int(xyxy[0]) + int(xyxy[2]))/2)
                y_avg = int((int(xyxy[3]) + int(xyxy[1]))/2)

                pydirectinput.moveTo(x_avg, y_avg)
                pydirectinput.leftClick()

            plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=1)

    # Print time (inference + NMS)
    print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS | {math.ceil(1/(time.time() - loop_time))} FPS')

    # Stream results
    im0 = cv2.cvtColor(im0, cv2.COLOR_BGR2RGB)