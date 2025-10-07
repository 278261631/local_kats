import os
import subprocess
import time
import win32com.client
from pathlib import Path
from astropy.io import fits
import numpy as np
import shutil

def convert_fits_bitpix(fits_file):
    """
    检查FITS文件的BITPIX值，如果是-64则转换为-32

    参数:
        fits_file: FITS文件路径

    返回:
        转换后的文件路径（如果需要转换）或原文件路径
    """
    try:
        with fits.open(fits_file, mode='readonly') as hdul:
            header = hdul[0].header
            bitpix = header.get('BITPIX', None)

            if bitpix == -64:
                print(f"  检测到BITPIX=-64，需要转换为-32")

                # 创建临时文件名
                base_name = os.path.splitext(fits_file)[0]
                temp_file = base_name + "_converted_bitpix32.fits"

                # 读取数据
                data = hdul[0].data
                header_copy = hdul[0].header.copy()

                # 转换数据类型为float32
                data_float32 = data.astype(np.float32)

                # 更新header
                header_copy['BITPIX'] = -32
                header_copy['COMMENT'] = 'Converted from BITPIX=-64 to -32 for MaxIm DL'

                # 保存新文件
                fits.writeto(temp_file, data_float32, header_copy, overwrite=True)

                print(f"  已转换并保存为: {os.path.basename(temp_file)}")
                return temp_file
            else:
                print(f"  BITPIX={bitpix}，无需转换")
                return fits_file

    except Exception as e:
        print(f"  警告: 检查BITPIX时出错 - {e}")
        return fits_file

def open_maxim_animate(maxim_path, image_folder):
    """
    使用MaxIm DL打开指定文件夹中的图像文件并启用animate功能

    参数:
        maxim_path: MaxIm DL可执行文件路径
        image_folder: 包含图像文件的文件夹路径
    """
    
    # 检查MaxIm DL是否存在
    if not os.path.exists(maxim_path):
        print(f"错误: MaxIm DL未找到: {maxim_path}")
        return False
    
    # 检查图像文件夹是否存在
    if not os.path.exists(image_folder):
        print(f"错误: 图像文件夹未找到: {image_folder}")
        return False
    
    # 获取文件夹中的所有图像文件
    image_extensions = ['.fit', '.fits', '.fts', '.bmp', '.jpg', '.jpeg', '.png', '.tif', '.tiff']
    image_files = []
    
    for file in os.listdir(image_folder):
        file_path = os.path.join(image_folder, file)
        if os.path.isfile(file_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                image_files.append(file_path)
    
    if not image_files:
        print(f"错误: 在文件夹中未找到图像文件: {image_folder}")
        return False
    
    # 按文件名排序
    image_files.sort()

    print(f"找到 {len(image_files)} 个图像文件:")
    for img in image_files:
        print(f"  - {os.path.basename(img)}")

    # 检查并转换FITS文件的BITPIX
    print("\n检查FITS文件...")
    converted_files = []
    for img_file in image_files:
        ext = os.path.splitext(img_file)[1].lower()
        if ext in ['.fit', '.fits', '.fts']:
            print(f"\n处理: {os.path.basename(img_file)}")
            converted_file = convert_fits_bitpix(img_file)
            converted_files.append(converted_file)
        else:
            converted_files.append(img_file)

    # 使用转换后的文件列表
    image_files = converted_files
    
    try:
        # 启动MaxIm DL
        print("\n启动MaxIm DL...")
        subprocess.Popen([maxim_path])

        # 等待MaxIm DL启动
        print("等待MaxIm DL启动...")
        time.sleep(8)

        # 连接到MaxIm DL COM对象
        print("连接到MaxIm DL...")
        maxim = win32com.client.Dispatch("MaxIm.Application")

        print("MaxIm DL已连接")

        # 打开三个文件
        print(f"\n开始打开 {len(image_files)} 个文件...")

        # 创建第一个Document对象并打开第一个文件
        doc = win32com.client.Dispatch("MaxIm.Document")
        print(f"[1/{len(image_files)}] 打开: {os.path.basename(image_files[0])}")
        doc.OpenFile(image_files[0])
        time.sleep(2)

        # 对于后续文件，使用Application的NewDocument方法或直接打开
        for i in range(1, len(image_files)):
            img_file = image_files[i]
            print(f"[{i+1}/{len(image_files)}] 打开: {os.path.basename(img_file)}")

            try:
                # 尝试通过Application打开新文件
                maxim.OpenDocument(img_file)
            except:
                # 如果失败，尝试使用Document的Load方法
                try:
                    new_doc = win32com.client.Dispatch("MaxIm.Document")
                    new_doc.OpenFile(img_file)
                except Exception as e:
                    print(f"  警告: 无法打开文件 - {e}")
                    continue

            time.sleep(2)

        print("\n完成! MaxIm DL已打开所有文件")

        return True

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n提示: 请确保已安装pywin32库")
        print("安装命令: pip install pywin32")
        return False

def main():
    # MaxIm DL路径
    maxim_path = r"C:\maxdl621\MaxIm_DL.exe"
    
    # 图像文件夹路径
    image_folder = r"E:\fix_data\output\test"
    
    print("=" * 60)
    print("MaxIm DL Animate 启动器")
    print("=" * 60)
    print(f"MaxIm DL路径: {maxim_path}")
    print(f"图像文件夹: {image_folder}")
    print("=" * 60)
    
    # 执行打开操作
    success = open_maxim_animate(maxim_path, image_folder)
    
    if success:
        print("\n程序执行成功!")
    else:
        print("\n程序执行失败!")

if __name__ == "__main__":
    main()

