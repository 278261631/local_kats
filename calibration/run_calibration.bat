@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    FITS图像校准工具
echo ========================================
echo.
echo 正在校准目标文件...
echo 目标: GY5_K053-1_No%%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit
echo.

cd /d "%~dp0"
python calibrate_target_file.py

echo.
echo ========================================
echo 按任意键退出...
pause >nul
