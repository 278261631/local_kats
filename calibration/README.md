# FITS图像校准工具

专业的天文FITS图像校准工具，实现标准的天文图像校准流程，包括bias减除、dark减除和flat field校正。

## 🌟 功能特点

### 核心功能
- **Bias减除** - 消除CCD读出噪声和偏置电平
- **Dark减除** - 消除热噪声和暗电流，支持曝光时间缩放
- **Flat Field校正** - 校正像素响应不均匀性和光学系统渐晕
- **灵活校准模式** - 支持跳过任意校准步骤（bias/dark/flat）
- **批量处理** - 支持单个文件和批量文件校准
- **错误处理** - 完善的错误处理和日志记录

### 技术特性
- 支持标准FITS格式文件
- 自动检测和处理不同的HDU结构
- 智能曝光时间检测和缩放
- 统计信息计算和验证
- 可配置的输出格式和参数

## 📦 文件结构

```
calibration/
├── fits_calibration.py      # 主校准模块
├── calibration_config.py    # 配置文件
├── calibrate_example.py     # 使用示例
├── README.md               # 说明文档
└── calibrated_output/      # 输出目录（自动创建）
```

## 🚀 快速开始

### 1. 基本使用

```python
from fits_calibration import FITSCalibrator

# 创建校准器 (完整校准)
calibrator = FITSCalibrator(output_dir="calibrated_output")

# 创建校准器 (跳过平场校正)
calibrator = FITSCalibrator(output_dir="calibrated_output", skip_flat=True)

# 创建校准器 (跳过bias和dark)
calibrator = FITSCalibrator(output_dir="calibrated_output", skip_bias=True, skip_dark=True)

# 创建校准器 (仅执行bias减除)
calibrator = FITSCalibrator(output_dir="calibrated_output", skip_dark=True, skip_flat=True)

# 加载校准帧
calibrator.load_calibration_frames(
    bias_path="E:/fix_data/calibration/gy5/master_bias_bin2.fits",
    dark_path="E:/fix_data/calibration/gy5/master_dark_bin2_30s.fits",
    flat_path="E:/fix_data/calibration/gy5/master_flat_C_bin2.fits"
)

# 校准科学图像
output_path = calibrator.calibrate_image("science_image.fits")
print(f"校准完成: {output_path}")
```

### 2. 运行示例脚本

```bash
cd calibration
# 完整校准
python calibrate_example.py

# 跳过平场校正
python calibrate_example.py --skip-flat

# 跳过bias减除
python calibrate_example.py --skip-bias

# 仅执行flat校正
python calibrate_example.py --skip-bias --skip-dark
```

### 3. 配置验证

```python
from calibration_config import validate_calibration_files

# 验证校准文件
results = validate_calibration_files('gy5')
for frame_type, info in results.items():
    print(f"{frame_type}: {info['exists']}")
```

## 🔧 配置说明

### 校准文件路径配置

在 `calibration_config.py` 中配置校准文件路径：

```python
CALIBRATION_PATHS = {
    'gy5': {
        'bias': 'E:/fix_data/calibration/gy5/master_bias_bin2.fits',
        'dark': 'E:/fix_data/calibration/gy5/master_dark_bin2_30s.fits',
        'flat': 'E:/fix_data/calibration/gy5/master_flat_C_bin2.fits',
        'dark_exposure_time': 30.0  # 暗电流帧曝光时间
    }
}
```

### 校准参数配置

```python
CALIBRATION_PARAMS = {
    'output_dtype': 'float32',        # 输出数据类型
    'sigma_clip_sigma': 3.0,          # sigma裁剪参数
    'flat_normalization_method': 'median',  # flat帧归一化方法
    'min_flat_value': 0.1,           # flat帧最小值阈值
}
```

## 📊 校准流程

### 1. Bias减除
```
校准图像 = 原始图像 - Master Bias
```
- 消除CCD读出噪声
- 去除电子学偏置

### 2. Dark减除
```
校准图像 = 校准图像 - (Master Dark × 曝光时间比例)
```
- 消除热噪声和暗电流
- 按曝光时间自动缩放

### 3. Flat Field校正
```
校准图像 = 校准图像 ÷ 归一化的Master Flat
```
- 校正像素响应不均匀性
- 消除光学系统渐晕效应

## 🎯 使用示例

### 示例1：校准指定文件

```python
from fits_calibration import FITSCalibrator
from calibration_config import get_calibration_config

# 获取配置
config = get_calibration_config('gy5')

# 创建校准器
calibrator = FITSCalibrator()

# 加载校准帧
calibrator.load_calibration_frames(
    bias_path=config['bias'],
    dark_path=config['dark'],
    flat_path=config['flat']
)

# 校准目标文件
science_file = "GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit"
output_path = calibrator.calibrate_image(science_file)
```

### 示例1.1：自定义校准模式

```python
# 跳过平场校正 (仅bias和dark减除)
calibrator = FITSCalibrator(skip_flat=True)

# 跳过bias减除 (仅dark和flat校正)
calibrator = FITSCalibrator(skip_bias=True)

# 仅执行bias减除
calibrator = FITSCalibrator(skip_dark=True, skip_flat=True)

# 仅执行flat校正
calibrator = FITSCalibrator(skip_bias=True, skip_dark=True)

# 加载校准帧 (根据跳过参数自动决定)
calibrator.load_calibration_frames(
    bias_path=config['bias'],
    dark_path=config['dark'],
    flat_path=config['flat']
)

# 校准目标文件
output_path = calibrator.calibrate_image(science_file)
```

### 示例2：批量校准

```python
import glob
from pathlib import Path

# 查找所有FITS文件
fits_files = glob.glob("*.fits") + glob.glob("*.fit")

# 批量校准
for fits_file in fits_files:
    try:
        output_path = calibrator.calibrate_image(fits_file)
        print(f"✓ {fits_file} -> {output_path}")
    except Exception as e:
        print(f"✗ {fits_file}: {e}")
```

## 📝 输出说明

### 输出文件
- **文件名格式**: `原文件名_calibrated.fits`
- **数据类型**: float32（可配置）
- **头部信息**: 包含校准历史记录

### 日志信息
- 校准过程详细记录
- 统计信息和质量指标
- 错误和警告信息

## ⚠️ 注意事项

1. **文件格式**: 确保输入文件为标准FITS格式
2. **校准文件**: 确保bias、dark、flat文件存在且格式正确
3. **曝光时间**: 系统会自动检测曝光时间，如检测失败会使用默认值
4. **内存使用**: 大文件处理时注意内存使用情况
5. **数据类型**: 校准过程使用float64精度，输出可配置为float32

## 🔍 故障排除

### 常见问题

1. **校准文件不存在**
   ```
   解决方案: 检查calibration_config.py中的文件路径
   ```

2. **曝光时间检测失败**
   ```
   解决方案: 检查FITS头部是否包含EXPTIME等关键字
   ```

3. **内存不足**
   ```
   解决方案: 处理大文件时分批处理或增加系统内存
   ```

4. **输出文件损坏**
   ```
   解决方案: 检查磁盘空间和写入权限
   ```

## 📈 性能优化

- 使用numpy数组操作提高计算效率
- 支持不同数据类型以平衡精度和存储空间
- 智能内存管理避免内存溢出
- 并行处理支持（可扩展）

## 🚀 快速使用指南

### 命令行使用

**单文件校准**:
```bash
# 完整校准 (bias + dark + flat)
python calibrate_target_file.py

# 跳过平场校正 (仅bias + dark)
python calibrate_target_file.py --skip-flat

# 跳过bias减除 (仅dark + flat)
python calibrate_target_file.py --skip-bias

# 仅执行bias减除
python calibrate_target_file.py --skip-dark --skip-flat

# 仅执行flat校正
python calibrate_target_file.py --skip-bias --skip-dark
```

**批量校准**:
```bash
# 完整校准
python batch_calibrate.py "输入目录路径"

# 跳过平场校正
python batch_calibrate.py "输入目录路径" --skip-flat

# 跳过bias减除
python batch_calibrate.py "输入目录路径" --skip-bias

# 仅执行bias减除
python batch_calibrate.py "输入目录路径" --skip-dark --skip-flat

# 组合选项
python batch_calibrate.py "输入目录路径" --skip-bias --skip-flat -r --max-files 10
```

**Windows批处理**:
```
# 完整校准
双击 run_calibration.bat

# 跳过平场校正
双击 run_calibration_no_flat.bat

# 仅执行bias减除
双击 run_calibration_bias_only.bat

# 仅执行dark减除
双击 run_calibration_dark_only.bat

# 仅执行flat校正
双击 run_calibration_flat_only.bat
```

### 校准模式选择

- **完整校准**: 执行bias减除 + dark减除 + flat field校正
- **跳过平场**: 仅执行bias减除 + dark减除
- **跳过bias**: 仅执行dark减除 + flat field校正
- **跳过dark**: 仅执行bias减除 + flat field校正
- **单步校准**: 仅执行某一种校准步骤

**适用场景**:
- **跳过平场**: 平场文件质量不佳或快速预处理
- **跳过bias**: 已经过bias校正的数据
- **跳过dark**: 短曝光时间或低噪声CCD
- **单步校准**: 测试特定校准效果或特殊科学需求

## 🤝 贡献

欢迎提交问题报告和功能建议！

---

**Author**: Augment Agent
**Date**: 2025-08-04
**Version**: 1.2.0
