# Ryan Oelkers DIA (Difference Image Analysis)

基于Ryan Oelkers方法的天文差异图像分析实现，专门用于检测瞬变天体和变星。

## 🌟 概述

差异图像分析(DIA)是天文学中用于时域天文学的重要技术，通过比较参考图像和科学图像来检测瞬变源、变星和其他时变天体。本实现遵循Ryan Oelkers等人在天文学研究中使用的标准DIA方法。

## 🚀 主要功能

### 核心算法
- **图像预处理** - FITS文件加载、背景估计和噪声建模
- **PSF匹配** - 点扩散函数匹配以确保图像质量一致性
- **差异图像生成** - 创建高质量的差异图像
- **瞬变源检测** - 基于信噪比的自动源检测
- **测光分析** - 孔径测光和误差估计
- **统计分析** - 显著性检验和假阳性过滤

### 输出格式
- **FITS差异图像** - 标准天文格式的差异图像
- **源目录** - 检测到的瞬变源详细信息
- **可视化图表** - 多面板比较图
- **处理日志** - 详细的处理记录

## 📦 安装

### 依赖安装
```bash
cd fits_dia/ryanoelkers_dia
pip install -r requirements.txt
```

### 主要依赖
- `astropy` - 天文学数据处理
- `photutils` - 天文测光工具
- `numpy/scipy` - 科学计算
- `opencv-python` - 图像处理
- `matplotlib` - 可视化

## 🎯 使用方法

### 1. 直接处理差异图像（推荐）
```bash
python run_dia.py --difference aligned_comparison_20250715_175203_difference.fits --threshold 3.0
```
直接分析现有的差异图像文件，检测瞬变源。

### 2. 自动处理test_data目录
```bash
python run_dia.py --auto
```
自动处理 `../test_data` 目录中的FITS文件。

### 3. 指定输入文件
```bash
python run_dia.py --reference template.fits --science new_image.fits
```

### 4. 交互式文件选择
```bash
python run_dia.py --directory /path/to/fits/files --interactive
```

### 5. 高级参数
```bash
python run_dia.py --difference diff.fits --threshold 3.0 --output results
```

## 📊 参数说明

### 检测参数
- `--threshold` - 检测阈值（sigma倍数，默认5.0）
- `--no-psf-matching` - 禁用PSF匹配
- `--output` - 指定输出目录

### 文件选择
- `--difference` - 直接处理差异图像文件（推荐）
- `--reference` + `--science` - 直接指定输入文件
- `--auto` - 自动处理test_data目录
- `--directory` - 指定包含FITS文件的目录
- `--interactive` - 交互式选择文件

## 📈 输出结果

### 文件输出
```
ryanoelkers_dia_YYYYMMDD_HHMMSS_difference.fits    # 差异图像
ryanoelkers_dia_YYYYMMDD_HHMMSS_marked.fits        # 带圆圈标记的FITS文件
ryanoelkers_dia_YYYYMMDD_HHMMSS_transients.txt     # 瞬变源目录
ryanoelkers_dia_YYYYMMDD_HHMMSS_visualization.png  # 可视化结果
ryanoelkers_dia.log                                 # 处理日志
```

### 标记FITS文件特性
- **圆圈大小** - 根据SNR值动态调整（3-15像素半径）
- **圆圈亮度** - 正流量源使用高亮圆圈，负流量源使用暗色圆圈
- **FITS头信息** - 包含标记参数和统计信息
- **天文软件兼容** - 可在DS9、FITS Liberator等软件中查看

### 源目录格式
```
# Ryan Oelkers DIA Transient Catalog
# Columns: ID X Y FLUX SNR SIGNIFICANCE APERTURE_FLUX APERTURE_FLUX_ERR
   1   123.456   234.567  1.234e-03    8.5    12.3  2.345e-03  1.234e-04
   2   345.678   456.789  2.345e-03    6.2     9.8  3.456e-03  2.345e-04
```

## 🔬 算法原理

### DIA处理流程
1. **图像加载** - 读取FITS文件和头信息
2. **背景估计** - 使用sigma-clipped统计估计背景
3. **PSF匹配** - 高斯卷积匹配点扩散函数
4. **差异计算** - 创建Science - Reference差异图像
5. **误差建模** - 泊松噪声和背景噪声建模
6. **源检测** - 基于信噪比的DAOStarFinder检测
7. **测光分析** - 孔径测光和误差估计

### 关键特性
- **天文学标准** - 遵循天文学界广泛使用的DIA方法
- **噪声建模** - 考虑泊松噪声和背景噪声
- **统计严格** - 基于信噪比的严格检测标准
- **可扩展性** - 模块化设计，易于扩展和定制

## 🛠️ 技术实现

### 核心类: RyanOelkersDIA
```python
dia = RyanOelkersDIA(
    detection_threshold=5.0,  # 检测阈值
    psf_matching=True         # PSF匹配开关
)

result = dia.process_dia(
    reference_fits='template.fits',
    science_fits='new_image.fits',
    output_dir='results'
)
```

### 配置参数
```python
dia_params = {
    'kernel_size': 21,           # 卷积核大小
    'psf_sigma': 2.0,           # PSF高斯宽度
    'background_box_size': 50,   # 背景估计盒子大小
    'aperture_radius': 5.0,     # 测光孔径半径
    'min_separation': 10,       # 最小源间距
    'fwhm': 4.0,               # 预期FWHM
}
```

## 📝 使用示例

### 基本使用
```bash
# 直接处理差异图像（最常用）
python run_dia.py --difference aligned_comparison_20250715_175203_difference.fits

# 处理test_data目录
python run_dia.py --auto

# 指定文件
python run_dia.py --reference ref.fits --science sci.fits --output results

# 交互式选择
python run_dia.py --directory /data/fits --interactive
```

### 高级使用
```bash
# 低阈值检测更多源
python run_dia.py --difference diff.fits --threshold 2.0

# 指定输出目录
python run_dia.py --difference diff.fits --output results

# 处理并分析结果
python process_existing_difference.py
```

## 🔍 故障排除

### 常见问题
1. **未检测到源** - 尝试降低检测阈值
2. **PSF匹配失败** - 使用`--no-psf-matching`禁用
3. **内存不足** - 处理较小的图像区域
4. **文件格式错误** - 确保输入为标准FITS格式

### 日志分析
检查 `ryanoelkers_dia.log` 文件获取详细的处理信息和错误诊断。

## 📚 参考文献

- Oelkers, R. J., et al. "Stellar Variability and Flare Rates from Dome A" (2016)
- Alard, C. & Lupton, R. H. "A Method for Optimal Image Subtraction" (1998)
- Bramich, D. M. "A new algorithm for difference image analysis" (2008)

## 🤝 贡献

欢迎提交问题报告和改进建议。本实现专注于天文学应用的DIA方法。

## 📄 许可证

本项目遵循开源许可证，用于学术和研究目的。
