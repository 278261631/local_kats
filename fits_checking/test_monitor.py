import os
import shutil
import time  # 添加时间模块


def copy_test_files():
    """复制测试文件从input目录到output目录"""
    src_dir = r'E:\fix_data\debug_fits_input'
    dst_dir = r'E:\fix_data\debug_fits_output'
    
    # 创建目标目录（如果不存在）
    os.makedirs(dst_dir, exist_ok=True)
    
    # 复制所有文件
    for filename in os.listdir(src_dir):
        src_file = os.path.join(src_dir, filename)
        if os.path.isfile(src_file):
            shutil.copy(src_file, dst_dir)
            print(f'已复制: {filename}')
            time.sleep(0.5)  # 添加0.5秒延迟控制速率

# 示例调用
if __name__ == '__main__':
    copy_test_files()