# 🚀 Quick Setup Instructions

## 1. Get Your API Key
1. Go to: https://ai.google.dev/
2. Click "Get API Key" 
3. Sign in with Google account
4. Create a new API key

## 2. Add API Key to .env File
Open the `.env` file in this directory and replace:
```
GEMINI_API_KEY=PUT_YOUR_GEMINI_API_KEY_HERE
```

With your actual key:
```
GEMINI_API_KEY=your_actual_api_key_here
```

## 3. Test Installation
```bash
python test_setup.py
```

## 4. Run Sample Analysis
```bash
# Test with 3 largest series (recommended first run)
python main.py analyze ./pics --test-limit 3

# View results
python main.py stats

# Create training dataset
python main.py create-dataset
```

## 🎯 That's it! 
Your Instagram photos will be analyzed by AI and curated into perfect training sequences for video generation models.
