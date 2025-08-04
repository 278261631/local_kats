# FITS图像校准工具 - 快速使用指南

## 🚀 新功能：灵活校准模式

现在支持跳过任意校准步骤（bias/dark/flat），实现完全自定义的校准流程！

## 📋 使用方法

### 1. 单文件校准

**完整校准** (bias + dark + flat):
```bash
python calibrate_target_file.py
```

**跳过平场校正** (仅bias + dark):
```bash
python calibrate_target_file.py --skip-flat
```

**跳过bias减除** (仅dark + flat):
```bash
python calibrate_target_file.py --skip-bias
```

**仅执行bias减除**:
```bash
python calibrate_target_file.py --skip-dark --skip-flat
```

**仅执行flat校正**:
```bash
python calibrate_target_file.py --skip-bias --skip-dark
```

### 2. 批量校准

**完整校准**:
```bash
python batch_calibrate.py "E:\fix_data\test\GY5\20250628\K053"
```

**跳过平场校正**:
```bash
python batch_calibrate.py "E:\fix_data\test\GY5\20250628\K053" --skip-flat
```

**跳过bias减除**:
```bash
python batch_calibrate.py "E:\fix_data\test\GY5\20250628\K053" --skip-bias
```

**仅执行bias减除**:
```bash
python batch_calibrate.py "E:\fix_data\test\GY5\20250628\K053" --skip-dark --skip-flat
```

**更多选项**:
```bash
# 递归搜索 + 跳过bias和flat + 最多处理10个文件
python batch_calibrate.py "输入目录" --skip-bias --skip-flat -r --max-files 10
```

### 3. Windows批处理文件

**完整校准**:
```
双击 run_calibration.bat
```

**跳过平场校正**:
```
双击 run_calibration_no_flat.bat
```

**仅执行bias减除**:
```
双击 run_calibration_bias_only.bat
```

**仅执行dark减除**:
```
双击 run_calibration_dark_only.bat
```

**仅执行flat校正**:
```
双击 run_calibration_flat_only.bat
```

## 🔧 校准模式对比

| 校准步骤 | 完整校准 | 跳过平场 | 跳过bias | 跳过dark | 仅bias | 仅dark | 仅flat |
|---------|---------|---------|---------|---------|--------|--------|--------|
| Bias减除 | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Dark减除 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Flat校正 | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |

## 📊 何时使用不同校准模式？

### 跳过平场校正
- **平场文件质量不佳**: 当master flat存在问题时
- **快速预处理**: 需要快速查看图像内容时
- **特殊科学目标**: 某些分析不需要平场校正时

### 跳过bias减除
- **已校正数据**: 数据已经过bias校正
- **高质量CCD**: 读出噪声极低的情况
- **特殊测试**: 仅测试dark和flat效果

### 跳过dark减除
- **短曝光时间**: 曝光时间很短，热噪声可忽略
- **低温CCD**: 工作温度极低，暗电流很小
- **快速处理**: 优先处理其他校正

### 单步校准
- **测试和调试**: 单独测试某种校正效果
- **特殊科学需求**: 仅需要特定类型的校正
- **问题排查**: 逐步排查校准问题

## 📁 输出文件

校准后的文件保存在 `calibrated_output/` 目录中：
- 文件名格式: `原文件名_calibrated.fits`
- 包含完整的校准历史记录
- 数据类型: float32

## 🎯 目标文件

当前配置的目标文件:
```
E:\fix_data\test\GY5\20250628\K053\GY5_K053-1_No%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit
```

校准文件位置:
```
E:\fix_data\calibration\gy5\
├── master_bias_bin2.fits      (249.9 MB)
├── master_dark_bin2_30s.fits  (249.9 MB)
└── master_flat_C_bin2.fits    (249.9 MB)
```

## ⚡ 快速测试

1. 打开命令行，进入calibration目录
2. 测试不同模式:
   ```bash
   # 完整校准
   python calibrate_target_file.py

   # 跳过平场
   python calibrate_target_file.py --skip-flat

   # 仅bias减除
   python calibrate_target_file.py --skip-dark --skip-flat
   ```
3. 查看输出文件: `calibrated_output/`

## 📞 获取帮助

查看所有可用选项:
```bash
python batch_calibrate.py --help
python calibrate_target_file.py --help
```

## 🎯 常用命令组合

```bash
# 仅执行bias减除 (最快速)
python calibrate_target_file.py --skip-dark --skip-flat

# 仅执行flat校正 (适用于已校正的数据)
python calibrate_target_file.py --skip-bias --skip-dark

# 跳过bias (适用于高质量CCD)
python calibrate_target_file.py --skip-bias

# 批量处理，仅bias和dark
python batch_calibrate.py "目录路径" --skip-flat -r
```

---
**更新日期**: 2025-08-04
**版本**: 1.2.0 (新增完整的灵活校准模式)
