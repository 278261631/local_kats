# FITS文件标记功能指南

## 🆕 新功能：直接在FITS文件中标记星点

现在程序支持在原始FITS文件中直接标记星点，生成带有圆圈标记的新FITS文件。

## 功能特点

### ✨ **双重输出**
- **JPG图像**: 可视化的彩色标记图像（原有功能）
- **FITS文件**: 带有星点标记的科学数据文件（新功能）

### 🎯 **FITS标记特点**
- **保持原始数据**: 不破坏原始FITS文件
- **高对比度标记**: 标记强度比背景亮5倍标准差
- **圆环标记**: 空心圆圈，不遮挡星点本身
- **可调大小**: 根据星点面积和设置参数调整圆圈大小

## 使用方法

### 1. 使用 `detect_stars_direct.py`

```bash
# 基本使用 - 生成FITS标记文件
python detect_stars_direct.py \
  --min-area 25 \
  --threshold-factor 4.0 \
  --min-circularity 0.6 \
  --save-marked-fits

# 自定义标记样式
python detect_stars_direct.py \
  --min-area 15 \
  --threshold-factor 3.5 \
  --circle-thickness 2 \
  --circle-size-factor 2.5 \
  --save-marked-fits
```

### 2. 使用 `detect_stars_configurable.py`

```bash
# 预设模式 + FITS标记
python detect_stars_configurable.py \
  --mode selective \
  --save-marked-fits

# 自定义参数 + FITS标记
python detect_stars_configurable.py \
  --min-area 20 \
  --threshold-factor 3.5 \
  --circle-thickness 1 \
  --circle-size-factor 2.0 \
  --save-marked-fits
```

## 输出文件

### 📁 **文件命名规则**

原始文件: `aligned_comparison_20250715_175203_difference.fits`

生成文件:
- **JPG图像**: `aligned_comparison_20250715_175203_difference_stars.jpg`
- **标记FITS**: `aligned_comparison_20250715_175203_difference_marked.fits`

### 📊 **实际测试结果**

| 模式 | 检测星点数 | JPG文件 | FITS文件 | 处理时间 |
|------|------------|---------|----------|----------|
| 4个星点模式 | 4个 | ✅ | ✅ | 4.59秒 |
| SELECTIVE模式 | 6个 | ✅ | ✅ | 4.41秒 |

## 技术细节

### 🔧 **FITS标记算法**

1. **复制原始数据**: 创建原始FITS数据的副本
2. **计算标记强度**: `标记强度 = 中位数 + 5×标准差`
3. **绘制圆环**: 在指定位置绘制空心圆圈
4. **双圈设计**: 大圆圈 + 内圈（当圆圈足够大时）
5. **保存文件**: 使用astropy保存为新的FITS文件

### ⚙️ **标记参数影响**

- **`--circle-thickness`**: 控制FITS中圆环的厚度
- **`--circle-size-factor`**: 控制圆圈大小倍数
- **星点面积**: 自动影响圆圈基础大小

### 📈 **性能影响**

- **处理时间**: 增加约2-3秒（用于FITS文件生成）
- **文件大小**: 标记FITS文件与原文件大小相同
- **内存使用**: 需要额外内存存储标记后的数据

## 应用场景

### 🔬 **科学研究**
- 在原始数据中永久标记发现的星点
- 便于后续分析和验证
- 保持科学数据的完整性

### 📊 **数据分析**
- 在天文软件中直接查看标记结果
- 与其他FITS处理工具兼容
- 便于批量处理和自动化分析

### 🎯 **质量控制**
- 验证星点检测的准确性
- 对比不同参数设置的效果
- 生成标准化的标记数据

## 注意事项

### ⚠️ **重要提醒**

1. **文件大小**: 标记FITS文件与原文件大小相同
2. **处理时间**: 启用FITS标记会增加处理时间
3. **存储空间**: 确保有足够空间存储额外的FITS文件
4. **数据完整性**: 标记不会破坏原始星点数据

### 💡 **使用建议**

1. **选择性使用**: 只在需要时启用 `--save-marked-fits`
2. **参数调优**: 先用JPG模式调试参数，再生成FITS
3. **批量处理**: 可以同时处理多个FITS文件
4. **备份原文件**: 虽然不会修改原文件，但建议备份重要数据

## 示例命令

### 🎯 **推荐用法**

```bash
# 精选模式 - 6个高质量星点
python detect_stars_direct.py \
  --min-area 15 \
  --threshold-factor 3.5 \
  --min-circularity 0.5 \
  --circle-thickness 1 \
  --circle-size-factor 2.0 \
  --save-marked-fits

# 最少模式 - 4个最亮星点
python detect_stars_direct.py \
  --min-area 25 \
  --threshold-factor 4.0 \
  --min-circularity 0.6 \
  --circle-thickness 2 \
  --circle-size-factor 2.5 \
  --save-marked-fits
```

现在您可以获得两种格式的标记结果：可视化的JPG图像和科学数据格式的FITS文件！
