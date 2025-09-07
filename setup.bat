@echo off
echo 🎬 Photo Series Detector - Setup Script
echo =======================================

echo.
echo 📦 Installing Python dependencies...
python -m pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Error installing dependencies
    pause
    exit /b 1
)

echo.
echo 🧪 Running setup test...
python test_setup.py

echo.
echo ✅ Setup complete!
echo.
echo 💡 Next steps:
echo    1. Get your Gemini API key from: https://ai.google.dev/
echo    2. Set environment variable: set GEMINI_API_KEY=YOUR_KEY
echo    3. Test with: python main.py analyze ./pics --test-limit 2
echo.
echo 🚀 Or run directly with: python main.py analyze ./pics --api-key YOUR_KEY
echo.
pause
