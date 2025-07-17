# 星点检测参数使用指南

## 直接参数程序使用

现在您可以直接传入所有检测参数，完全自定义检测行为：

```bash
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --min-circularity 0.5
```

## 参数说明

### 必需参数

| 参数 | 类型 | 说明 | 影响 |
|------|------|------|------|
| `--min-area` | int | 最小星点面积（像素） | 越大检测到的星点越少 |
| `--threshold-factor` | float | 阈值因子 | 越大检测越严格，星点越少 |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--max-area` | int | 1000 | 最大星点面积（像素） |
| `--min-circularity` | float | 0.4 | 最小圆度 (0-1) |
| `--min-solidity` | float | 0.6 | 最小实心度 (0-1) |
| `--adaptive-threshold` | flag | False | 使用自适应阈值 |
| `--dark-star-mode` | flag | False | 启用暗星检测模式 |
| `--circle-thickness` | int | 1 | 圆圈线条粗细（像素） |
| `--circle-size-factor` | float | 1.5 | 圆圈大小倍数 |

## 实际测试结果

基于当前FITS文件的测试结果：

| 参数组合 | 检测星点数 | 适用场景 |
|----------|------------|----------|
| `--min-area 25 --threshold-factor 4.0 --min-circularity 0.6` | **4个** | 只要最亮的主要星点 |
| `--min-area 15 --threshold-factor 3.5 --min-circularity 0.5` | **6个** | 较明显的星点 |
| `--min-area 8 --threshold-factor 2.5 --min-circularity 0.3` | **247个** | 包含较多星点 |

## 参数调整策略

### 🎯 减少星点数量
```bash
# 方法1: 增加最小面积
python detect_stars_direct.py --min-area 30 --threshold-factor 3.0

# 方法2: 提高阈值因子
python detect_stars_direct.py --min-area 15 --threshold-factor 4.5

# 方法3: 提高圆度要求
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --min-circularity 0.7

# 方法4: 组合使用
python detect_stars_direct.py --min-area 25 --threshold-factor 4.0 --min-circularity 0.6 --min-solidity 0.8
```

### 📈 增加星点数量
```bash
# 方法1: 降低最小面积
python detect_stars_direct.py --min-area 5 --threshold-factor 3.0

# 方法2: 降低阈值因子
python detect_stars_direct.py --min-area 10 --threshold-factor 2.0

# 方法3: 降低圆度要求
python detect_stars_direct.py --min-area 10 --threshold-factor 3.0 --min-circularity 0.2

# 方法4: 使用自适应阈值
python detect_stars_direct.py --min-area 8 --threshold-factor 2.5 --adaptive-threshold

# 方法5: 启用暗星模式
python detect_stars_direct.py --min-area 5 --threshold-factor 2.0 --dark-star-mode --adaptive-threshold
```

## 可视化样式调整

### 🎨 圆圈样式参数

```bash
# 更大更细的圆圈（推荐）
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --circle-thickness 1 --circle-size-factor 2.0

# 更大更粗的圆圈
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --circle-thickness 2 --circle-size-factor 2.5

# 小而精细的圆圈
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --circle-thickness 1 --circle-size-factor 1.0

# 大而醒目的圆圈
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --circle-thickness 3 --circle-size-factor 3.0
```

## 常用参数组合

### 极简模式 (1-5个星点)
```bash
python detect_stars_direct.py --min-area 30 --threshold-factor 5.0 --min-circularity 0.7 --min-solidity 0.8 --circle-thickness 1 --circle-size-factor 2.0
```

### 精选模式 (5-15个星点)
```bash
python detect_stars_direct.py --min-area 20 --threshold-factor 4.0 --min-circularity 0.6 --min-solidity 0.7 --circle-thickness 1 --circle-size-factor 2.0
```

### 标准模式 (15-50个星点)
```bash
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --min-circularity 0.5 --min-solidity 0.6 --circle-thickness 1 --circle-size-factor 1.5
```

### 丰富模式 (50-200个星点)
```bash
python detect_stars_direct.py --min-area 10 --threshold-factor 3.0 --min-circularity 0.4 --min-solidity 0.6
```

### 完整模式 (200+个星点)
```bash
python detect_stars_direct.py --min-area 8 --threshold-factor 2.5 --min-circularity 0.3 --min-solidity 0.5
```

### 暗星模式 (1000+个星点)
```bash
python detect_stars_direct.py --min-area 5 --threshold-factor 2.0 --min-circularity 0.3 --min-solidity 0.5 --adaptive-threshold --dark-star-mode
```

## 参数优化建议

### 1. 从严格参数开始
建议从较严格的参数开始，然后逐步放宽：
```bash
# 开始
python detect_stars_direct.py --min-area 25 --threshold-factor 4.0 --min-circularity 0.6

# 如果星点太少，逐步调整
python detect_stars_direct.py --min-area 20 --threshold-factor 4.0 --min-circularity 0.6
python detect_stars_direct.py --min-area 20 --threshold-factor 3.5 --min-circularity 0.6
python detect_stars_direct.py --min-area 20 --threshold-factor 3.5 --min-circularity 0.5
```

### 2. 单一参数调整
每次只调整一个参数，观察效果：
- 调整 `min-area`: 影响最直接
- 调整 `threshold-factor`: 影响最显著
- 调整 `min-circularity`: 影响质量

### 3. 使用详细模式
```bash
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --verbose
```

## 其他选项

### 自定义输入输出目录
```bash
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5 --input-dir "D:\my_fits" --output-dir "D:\results"
```

### 查看帮助
```bash
python detect_stars_direct.py --help
```

现在您可以完全控制所有检测参数，根据具体需求精确调整星点检测行为！
