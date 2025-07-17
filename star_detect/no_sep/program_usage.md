# 程序使用指南

## 三种程序选择

### 1. 🎯 `detect_stars_direct.py` - 纯参数模式
**推荐用于**: 完全自定义控制

```bash
# 必需参数
python detect_stars_direct.py --min-area 15 --threshold-factor 3.5

# 完整参数
python detect_stars_direct.py \
  --min-area 15 \
  --max-area 1000 \
  --threshold-factor 3.5 \
  --min-circularity 0.5 \
  --min-solidity 0.6 \
  --circle-thickness 1 \
  --circle-size-factor 2.5
```

### 2. ⚙️ `detect_stars_configurable.py` - 混合模式
**推荐用于**: 预设模式或自定义参数

```bash
# 使用预设模式
python detect_stars_configurable.py --mode selective

# 使用自定义参数（支持所有参数）
python detect_stars_configurable.py \
  --min-area 5 \
  --max-area 4000 \
  --threshold-factor 0.5 \
  --min-circularity 0.6 \
  --min-solidity 0.2 \
  --circle-thickness 1 \
  --circle-size-factor 2.5
```

### 3. 📋 `detect_stars.py` - 固定模式
**推荐用于**: 快速使用，参数已预设

```bash
python detect_stars.py
```

## 参数对比

| 参数 | direct.py | configurable.py | detect_stars.py |
|------|-----------|-----------------|-----------------|
| 预设模式 | ❌ | ✅ | ✅ |
| 自定义参数 | ✅ | ✅ | ❌ |
| 可视化样式 | ✅ | ✅ | ❌ |
| 参数验证 | ✅ | ✅ | ❌ |

## 常用场景

### 🎯 只要几个最亮的星点
```bash
python detect_stars_direct.py \
  --min-area 25 \
  --threshold-factor 4.0 \
  --min-circularity 0.6 \
  --circle-thickness 1 \
  --circle-size-factor 2.5
```

### ⭐ 适中数量的星点
```bash
python detect_stars_configurable.py --mode selective
# 或者
python detect_stars_direct.py \
  --min-area 15 \
  --threshold-factor 3.5 \
  --min-circularity 0.5
```

### 🌌 大量星点检测
```bash
python detect_stars_direct.py \
  --min-area 5 \
  --threshold-factor 1.0 \
  --min-circularity 0.3 \
  --adaptive-threshold \
  --dark-star-mode
```

### 🎨 自定义可视化样式
```bash
# 大而细的圆圈
python detect_stars_direct.py \
  --min-area 15 \
  --threshold-factor 3.5 \
  --circle-thickness 1 \
  --circle-size-factor 3.0

# 小而粗的圆圈
python detect_stars_direct.py \
  --min-area 15 \
  --threshold-factor 3.5 \
  --circle-thickness 3 \
  --circle-size-factor 1.0
```

## 参数快速参考

### 检测参数
- `--min-area`: 最小面积（越大星点越少）
- `--threshold-factor`: 阈值因子（越大星点越少）
- `--min-circularity`: 圆度要求（0-1，越大越圆）
- `--min-solidity`: 实心度要求（0-1，越大越实心）

### 可视化参数
- `--circle-thickness`: 线条粗细（1=细，2=中，3=粗）
- `--circle-size-factor`: 圆圈大小（1.0=标准，2.0=两倍）

### 高级参数
- `--adaptive-threshold`: 自适应阈值
- `--dark-star-mode`: 暗星检测模式

## 错误解决

### 参数不识别错误
确保使用正确的程序：
- 可视化样式参数只在 `detect_stars_direct.py` 和 `detect_stars_configurable.py` 中可用
- `detect_stars.py` 不支持命令行参数

### 参数冲突错误
在 `detect_stars_configurable.py` 中：
- 不能同时使用 `--mode` 和自定义参数
- 要么用预设模式，要么用自定义参数

## 推荐使用

根据您的需求：

1. **快速使用**: `detect_stars_configurable.py --mode selective`
2. **精确控制**: `detect_stars_direct.py --min-area 15 --threshold-factor 3.5`
3. **可视化调整**: 添加 `--circle-thickness 1 --circle-size-factor 2.5`

现在所有程序都支持可视化样式参数，您可以完全控制星点标记的外观！
