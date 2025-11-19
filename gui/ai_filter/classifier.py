#!/usr/bin/env python3
"""AI GOOD/BAD 质量分类推理封装。

只保留推理相关代码：
- 使用 pair_quality_cnn.pth 中保存的 SimpleCNN 结构
- 输入一对 reference/aligned PNG，使用 aligned-reference 作为模型输入
- 输出标签("good"/"bad")和对应的置信度(softmax 概率)

依赖: torch, torchvision, pillow
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms


class SimpleCNN(nn.Module):
    """与 kats_ai_filter 中相同结构的简单 CNN 二分类器。

    输入: 3 通道 diff 图像 [3, H, W]
    输出: 2 维 logits，类别 0=bad, 1=good
    """

    def __init__(self, image_size: int = 224) -> None:
        super().__init__()

        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)

        # 224 -> 112 -> 56 -> 28，因此特征尺寸= image_size//8
        feature_size = image_size // 8
        flattened_dim = 64 * feature_size * feature_size

        self.fc1 = nn.Linear(flattened_dim, 128)
        self.fc2 = nn.Linear(128, 2)  # 输出 good / bad 两类

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = self.pool(F.relu(self.conv3(x)))
        x = torch.flatten(x, 1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x


def load_trained_model(model_path: str, device: Optional[torch.device] = None):
    """加载训练好的模型及对应 image_size。

    返回: (model, device, image_size)
    """

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(model_path, map_location=device)
    image_size = int(checkpoint.get("image_size", 224))

    model = SimpleCNN(image_size=image_size)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    return model, device, image_size


class AIPairQualityClassifier:
    """封装好的一对 reference/aligned PNG 推理器。"""

    def __init__(self, model_path: Optional[str] = None, device: Optional[torch.device] = None) -> None:
        if model_path is None:
            # 默认使用当前目录下的 pair_quality_cnn.pth
            model_path = str(Path(__file__).with_name("pair_quality_cnn.pth"))

        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"AI 模型文件不存在: {model_path}")

        self.model, self.device, self.image_size = load_trained_model(model_path, device)
        self.transform = transforms.Compose(
            [
                transforms.Resize((self.image_size, self.image_size)),
                transforms.ToTensor(),
            ]
        )

    def predict_pair(self, ref_path: str, aligned_path: str) -> Tuple[str, float]:
        """对一对 reference/aligned PNG 进行预测。

        返回:
            (label, prob)，其中 label 为 "good" 或 "bad"，
            prob 为该类别的 softmax 概率 (0~1)。
        """

        ref_img = Image.open(ref_path).convert("RGB")
        aligned_img = Image.open(aligned_path).convert("RGB")

        ref_tensor = self.transform(ref_img)
        aligned_tensor = self.transform(aligned_img)

        # 使用 aligned - reference 的差分图像作为输入
        diff = aligned_tensor - ref_tensor
        x = diff.unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(x)
            probs = torch.softmax(outputs, dim=1)[0]
            pred_label = int(torch.argmax(probs).item())
            prob = float(probs[pred_label].item())

        label_name = "good" if pred_label == 1 else "bad"
        return label_name, prob

