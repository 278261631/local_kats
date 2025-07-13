import os
import shutil
import time  # 添加时间模块
from datetime import datetime


def copy_test_files():
    """复制测试文件从input目录到output目录，使用较慢的速度进行测试"""
    src_dir = r'E:\fix_data\debug_fits_input'
    dst_dir = r'E:\fix_data\debug_fits_output'

    # 创建目标目录（如果不存在）
    os.makedirs(dst_dir, exist_ok=True)

    print(f"开始复制测试文件...")
    print(f"源目录: {src_dir}")
    print(f"目标目录: {dst_dir}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    # 获取所有文件列表
    files = [f for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))]
    total_files = len(files)

    # 复制所有文件
    for i, filename in enumerate(files, 1):
        src_file = os.path.join(src_dir, filename)
        dst_file = os.path.join(dst_dir, filename)

        # 显示进度
        print(f'[{i}/{total_files}] 正在复制: {filename}')

        # 复制文件
        shutil.copy(src_file, dst_file)

        # 显示文件大小信息
        file_size = os.path.getsize(dst_file)
        print(f'    [OK] 复制完成 - 大小: {file_size:,} 字节')
        print(f'    [WAIT] 等待 2.5 秒...')

        time.sleep(2.5)  # 增加延迟到2.5秒，使测试更慢

    print("-" * 50)
    print(f"所有文件复制完成！总计: {total_files} 个文件")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 示例调用
if __name__ == '__main__':
    copy_test_files()