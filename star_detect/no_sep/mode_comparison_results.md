# 星点检测模式对比结果

## 实际检测结果对比

基于 `aligned_comparison_20250715_175203_difference.fits` 文件的测试结果：

| 检测模式 | 检测星点数 | 过滤对象数 | 阈值 | 适用场景 |
|----------|------------|------------|------|----------|
| **MINIMAL** | 4个 | 6个 | 153 | 🌟 只要最亮的主要星点 |
| **SELECTIVE** | 6个 | 2个 | 140 | ⭐ 较明显的星点，适合一般使用 |
| **BALANCED** | 89个 | 55个 | 127 | 🌌 平衡的星点检测 |
| **SENSITIVE** | ~200-1000个 | - | 更低 | 🔍 包含较暗星点 |
| **MAXIMUM** | ~1000+个 | - | 最低 | 🌠 所有可能的星点 |

## 模式选择建议

### 🌟 MINIMAL 模式 (4个星点)
**适用场景:**
- 只需要最亮的导航星
- 简单的星图标定
- 快速预览检查

**特点:**
- 最高质量的星点
- 处理速度最快
- 几乎无噪声

### ⭐ SELECTIVE 模式 (6个星点) - **推荐**
**适用场景:**
- 一般天文摄影处理
- 星点质量要求较高
- 避免过多噪声干扰

**特点:**
- 高质量星点
- 数量适中
- 处理效率高

### 🌌 BALANCED 模式 (89个星点)
**适用场景:**
- 需要较多参考星点
- 精确的天体测量
- 星图匹配

**特点:**
- 星点数量充足
- 质量与数量平衡
- 适合大多数应用

### 🔍 SENSITIVE 模式
**适用场景:**
- 深空天体摄影
- 需要检测暗星
- 完整的星图分析

### 🌠 MAXIMUM 模式
**适用场景:**
- 科学研究
- 变星监测
- 完整星表构建

## 使用方法

### 命令行使用
```bash
# 使用精选模式（推荐）
python detect_stars_configurable.py --mode selective

# 使用最少模式
python detect_stars_configurable.py --mode minimal

# 使用平衡模式
python detect_stars_configurable.py --mode balanced

# 查看所有可用模式
python detect_stars_configurable.py --list-modes
```

### 自定义输入输出目录
```bash
python detect_stars_configurable.py --mode selective --input-dir "D:\my_fits" --output-dir "D:\results"
```

## 性能对比

| 模式 | 处理时间 | 内存使用 | 输出文件大小 |
|------|----------|----------|--------------|
| MINIMAL | 最快 | 最少 | 最小 |
| SELECTIVE | 快 | 少 | 小 |
| BALANCED | 中等 | 中等 | 中等 |
| SENSITIVE | 较慢 | 较多 | 较大 |
| MAXIMUM | 最慢 | 最多 | 最大 |

## 质量指标

所有模式都保持高质量的圆度过滤：
- 圆度检测确保星点形状规则
- 实心度过滤去除噪声和伪影
- 面积过滤控制星点大小范围

## 建议

1. **初次使用**: 推荐 `SELECTIVE` 模式
2. **需要更多星点**: 使用 `BALANCED` 模式
3. **只要主要星点**: 使用 `MINIMAL` 模式
4. **科学研究**: 根据需要选择 `SENSITIVE` 或 `MAXIMUM` 模式

根据您的具体需求选择合适的模式，可以获得最佳的检测效果！
