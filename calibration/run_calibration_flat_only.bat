@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    FITS Image Calibration Tool (Flat Only)
echo ========================================
echo.
echo Calibrating target file...
echo Target: GY5_K053-1_No%%20Filter_60S_Bin2_UTC20250628_190147_-15C_.fit
echo Mode: Flat field correction only
echo.

cd /d "%~dp0"
python calibrate_target_file.py --skip-bias --skip-dark

echo.
echo ========================================
echo Press any key to exit...
pause >nul
