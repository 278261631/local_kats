# FITS文件下载工具

## 概述

`data_02_download.py` 是一个用于批量下载FITS文件的工具，它读取由 `data_01_scan.py` 生成的URL列表文件，并将文件下载到指定目录。

## 功能特性

- **批量下载**: 支持从URL列表文件批量下载FITS文件
- **并发下载**: 使用多线程提高下载效率
- **断点续传**: 自动跳过已存在的文件
- **重试机制**: 下载失败时自动重试
- **进度显示**: 实时显示下载进度和统计信息
- **错误处理**: 完善的错误处理和日志记录

## 使用方法

### 基本用法

```bash
python data_02_download.py <URL文件路径>
```

### 示例

```bash
# 使用默认设置下载
python data_02_download.py E:\fix_data\20250714\20250714_urls.txt

# 指定下载目录
python data_02_download.py E:\fix_data\20250714\20250714_urls.txt --download-dir E:\downloads

# 自定义并发线程数
python data_02_download.py E:\fix_data\20250714\20250714_urls.txt --max-workers 8

# 设置重试次数和超时时间
python data_02_download.py E:\fix_data\20250714\20250714_urls.txt --retry-times 5 --timeout 60
```

### 命令行参数

- `url_file`: URL列表文件路径（必需）
- `--download-dir`: 下载目录（可选，默认为URL文件所在目录）
- `--max-workers`: 最大并发线程数（默认4）
- `--retry-times`: 重试次数（默认3）
- `--timeout`: 下载超时时间，单位秒（默认30）



## 输出

- 下载的FITS文件保存在指定的下载目录中
- 控制台显示下载进度和统计信息
- 最终显示下载统计报告

## 测试

### 运行基本测试

```bash
python test_download.py
```

### 使用真实文件测试

```bash
python test_download.py --real
```

## 工作流程

1. **生成URL列表**: 使用 `data_01_scan.py` 扫描并生成URL列表文件
2. **下载文件**: 使用 `data_02_download.py` 从URL列表下载FITS文件

完整示例：

```bash
# 步骤1: 扫描生成URL列表
python data_01_scan.py --time 20250714 --data-path E:\fix_data

# 步骤2: 下载FITS文件
python data_02_download.py E:\fix_data\20250714\20250714_urls.txt
```

## 注意事项

1. **网络连接**: 确保网络连接稳定，下载大文件时可能需要较长时间
2. **磁盘空间**: 确保有足够的磁盘空间存储下载的文件
3. **并发数量**: 根据网络带宽和服务器负载调整并发线程数
4. **超时设置**: 根据文件大小和网络速度调整超时时间
5. **重试机制**: 网络不稳定时可以增加重试次数

## 错误处理

- 网络连接错误会自动重试
- 下载失败的文件会在统计中标记
- 损坏的文件会被自动删除并重新下载
- 已存在的完整文件会被跳过

## 性能优化建议

- 根据网络带宽调整 `--max-workers` 参数
- 对于大文件，可以增加 `--timeout` 值
- 网络不稳定时增加 `--retry-times` 值
- 使用SSD存储可以提高写入速度
