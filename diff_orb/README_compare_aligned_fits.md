# 已对齐FITS文件差异比较工具

## 概述

`compare_aligned_fits.py` 是一个专门用于比较已对齐FITS文件差异的Python脚本。该工具设计用于处理 `E:\fix_data\align-diff` 文件夹中由 `run_alignment_comparison.py` 生成的已对齐FITS文件。

## 功能特点

- **自动文件识别**: 自动识别目录中的参考文件和对齐文件
- **差异检测**: 使用高斯模糊和阈值处理检测图像差异
- **新亮点标记**: 自动检测并标记新出现的亮点
- **双格式输出**: 同时生成FITS和JPG格式的结果文件
- **详细报告**: 生成包含亮点位置和面积信息的文本报告

## 输出文件

### FITS格式文件
- `*_difference.fits`: 差异图像
- `*_binary_diff.fits`: 二值化差异图像
- `*_marked.fits`: 标记新亮点的图像

### JPG格式文件
- `*_reference.jpg`: 参考图像
- `*_aligned.jpg`: 对齐图像
- `*_difference.jpg`: 差异图像（热力图显示）
- `*_binary_diff.jpg`: 二值化差异图像
- `*_marked.jpg`: 标记新亮点的图像

### 文本报告
- `*_bright_spots.txt`: 详细的亮点信息报告

## 使用方法

### 基本用法
```bash
# 使用默认参数处理 E:\fix_data\align-diff 目录
python compare_aligned_fits.py
```

### 指定输入目录
```bash
python compare_aligned_fits.py --input E:\fix_data\align-diff
```

### 指定输出目录
```bash
python compare_aligned_fits.py --input E:\fix_data\align-diff --output my_results
```

### 调整检测参数
```bash
# 调整差异检测阈值
python compare_aligned_fits.py --threshold 0.05

# 调整高斯模糊参数
python compare_aligned_fits.py --gaussian-sigma 1.5

# 组合参数
python compare_aligned_fits.py --threshold 0.05 --gaussian-sigma 1.5 --output sensitive_results
```

## 参数说明

- `--input, -i`: 输入目录路径（默认: `E:\fix_data\align-diff`）
- `--output, -o`: 输出目录路径（默认: 自动生成时间戳目录）
- `--threshold, -t`: 差异检测阈值（默认: 0.1，值越小越敏感）
- `--gaussian-sigma, -g`: 高斯模糊参数（默认: 1.0，用于降噪）

## 处理流程

1. **文件识别**: 自动识别目录中的参考文件和对齐文件
2. **数据加载**: 加载FITS文件数据并进行预处理
3. **图像标准化**: 使用百分位数进行鲁棒标准化
4. **差异计算**: 计算两个图像之间的绝对差异
5. **噪声过滤**: 应用高斯模糊减少噪声影响
6. **阈值处理**: 使用阈值生成二值化差异图像
7. **亮点检测**: 查找连通区域并过滤合理大小的亮点
8. **结果输出**: 生成FITS、JPG和文本格式的结果文件

## 检测参数调优

### 差异阈值 (threshold)
- **默认值**: 0.1
- **较小值** (0.05-0.08): 更敏感，检测更多细微差异
- **较大值** (0.15-0.2): 较不敏感，只检测明显差异

### 高斯模糊 (gaussian-sigma)
- **默认值**: 1.0
- **较小值** (0.5-0.8): 保留更多细节，但可能增加噪声
- **较大值** (1.5-2.0): 更好的降噪效果，但可能丢失细节

## 输出示例

处理完成后，工具会显示类似以下的结果摘要：

```
处理完成！
============================================================
参考文件: comparison_reference_*.fits
对齐文件: comparison_aligned_*.fits
检测到新亮点: 1411 个

新亮点详情:
  #1: 位置(129, 3191), 面积19.5像素
  #2: 位置(46, 3190), 面积9.0像素
  ...

输出文件已保存到: aligned_diff_results_20250715_140115
```

## 注意事项

1. **输入文件要求**: 输入目录应包含已对齐的FITS文件
2. **文件命名**: 工具会自动识别包含"reference"和"aligned"关键词的文件
3. **内存使用**: 处理大型FITS文件时可能需要较多内存
4. **处理时间**: 根据图像大小，处理时间可能从几秒到几分钟不等

## 依赖库

- numpy
- opencv-python (cv2)
- matplotlib
- astropy
- scipy

## 日志文件

工具会生成 `aligned_fits_comparison.log` 日志文件，记录详细的处理过程和任何错误信息。

## 故障排除

1. **文件未找到**: 确保输入目录存在且包含FITS文件
2. **内存不足**: 尝试处理较小的图像或增加系统内存
3. **处理缓慢**: 检查图像大小，考虑使用中央区域处理
4. **检测结果异常**: 调整阈值和高斯模糊参数

## 版本信息

- 版本: 1.0
- 创建日期: 2025-07-15
- 作者: Augment Agent
