import cv2
import numpy as np
import os
from astropy.io import fits
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

def load_fit_image(filepath):
    """加载 .fit 文件并返回原始数据"""
    try:
        with fits.open(filepath) as hdul:
            original_data = hdul[0].data
            header = hdul[0].header

        # 确保数据是适合OpenCV处理的格式
        # OpenCV可以直接处理float32和uint16等格式
        if original_data.dtype == np.uint16:
            # 保持uint16格式
            cv_image = original_data.copy()
        elif original_data.dtype == np.float64:
            # 转换为float32以节省内存
            cv_image = original_data.astype(np.float32)
        else:
            # 其他格式转换为float32
            cv_image = original_data.astype(np.float32)

        return original_data, cv_image, header
    except Exception as e:
        print(f"加载 .fit 文件时出错: {e}")
        return None, None, None

def save_fits_image(data, header, filepath):
    """保存数据为 .fits 文件"""
    try:
        hdu = fits.PrimaryHDU(data, header=header)
        hdu.writeto(filepath, overwrite=True)
        print(f"FITS文件已保存: {filepath}")
    except Exception as e:
        print(f"保存 FITS 文件时出错: {e}")

def adaptive_median_demo():
    """自适应中值滤波演示"""
    
    # 查找 .fit 文件
    fit_files = [f for f in os.listdir('.') if f.endswith('.fit')]
    
    if not fit_files:
        print("未找到 .fit 文件")
        return
    
    # 使用第一个找到的 .fit 文件
    input_file = fit_files[0]
    print(f"处理文件: {input_file}")
    
    # 加载图像
    original_data, cv_img, header = load_fit_image(input_file)

    if cv_img is None:
        print("无法加载图像")
        return

    print(f"原始图像尺寸: {cv_img.shape}")
    print(f"原始数据类型: {original_data.dtype}")
    print(f"OpenCV处理数据类型: {cv_img.dtype}")
    print(f"原始数据范围: {original_data.min():.2f} - {original_data.max():.2f}")

    # 直接在原始数据上应用中值滤波
    ksize = 3  # 使用更小的核大小

    def safe_median_blur(img, ksize):
        """安全的中值滤波，处理不同数据类型和核大小限制"""
        try:
            # 首先尝试直接滤波
            return cv2.medianBlur(img, ksize), img.dtype, "直接处理"
        except cv2.error as e:
            print(f"  直接处理失败: {e}")

            # 如果是uint16且核大小较大，转换为uint8处理
            if img.dtype == np.uint16 and ksize > 5:
                print(f"  uint16大核大小，转换为uint8处理")
                temp_img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                temp_filtered = cv2.medianBlur(temp_img, ksize)
                filtered = temp_filtered.astype(np.float32) * (img.max() - img.min()) / 255.0 + img.min()
                return filtered.astype(img.dtype), img.dtype, "uint16->uint8转换"

            # 对于其他情况，转换为uint8处理
            elif img.dtype != np.uint8:
                print(f"  转换为uint8处理")
                temp_img = cv2.normalize(img.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                temp_filtered = cv2.medianBlur(temp_img, ksize)
                filtered = temp_filtered.astype(np.float32) * (img.max() - img.min()) / 255.0 + img.min()
                return filtered.astype(img.dtype), img.dtype, "转换为uint8"

            else:
                raise e

    print(f"应用中值滤波 (ksize={ksize})")
    print(f"数据类型: {cv_img.dtype}, 数据范围: {cv_img.min():.2f} - {cv_img.max():.2f}")

    try:
        # 尝试使用 adaptiveMedianBlur (如果存在)
        filtered_data = cv2.adaptiveMedianBlur(cv_img, ksize=ksize)
        method = "adaptiveMedianBlur"
    except AttributeError:
        print("adaptiveMedianBlur 不可用，使用标准中值滤波")
        filtered_data, result_dtype, method = safe_median_blur(cv_img, ksize)
    except cv2.error:
        print("adaptiveMedianBlur 失败，使用标准中值滤波")
        filtered_data, result_dtype, method = safe_median_blur(cv_img, ksize)

    print(f"滤波方法: {method}")
    print(f"滤波后数据类型: {filtered_data.dtype}")
    print(f"滤波后范围: {filtered_data.min():.2f} - {filtered_data.max():.2f}")

    # 创建输出文件名
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}_filtered.fits"

    # 保存滤波后的FITS图像
    save_fits_image(filtered_data, header, output_file)
    
    print(f"滤波后数据范围: {filtered_data.min():.2f} - {filtered_data.max():.2f}")
    print("处理完成")

if __name__ == "__main__":
    adaptive_median_demo()
