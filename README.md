# Photo Series Detector for Video Generation Training

<div align="center">

🎬 **AI-Powered Dataset Curation Tool**

*Transform Instagram photo collections into high-quality training sequences for video generation models*

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Gemini 2.5 Flash](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange.svg)](https://ai.google.dev/)

</div>

## 🎯 Overview

**Photo Series Detector** is an intelligent dataset curation tool designed specifically for creating high-quality training data for video generation models (like WAN2.2, AnimateDiff, and similar architectures). It uses Google's Gemini 2.5 Flash AI to automatically identify, verify, and organize sequential photo series from Instagram-style image collections.

### Why This Matters

Video generation models require temporal consistency - the same subject appearing across multiple frames with subtle variations. This tool transforms scattered Instagram photos into "1fps video sequences" perfect for training, where each sequence shows the same person/subject in different poses, angles, or expressions.

## ✨ Key Features

- � **Intelligent Series Detection**: Automatically groups images by Instagram filename patterns
- 🤖 **AI-Powered Verification**: Uses Gemini 2.5 Flash to validate series quality and consistency
- 📝 **Smart Caption Generation**: Creates training-ready captions optimized for video generation
- 🗄️ **SQLite Database**: Efficient storage and querying of analysis results
- 📊 **Comprehensive Statistics**: Detailed insights into your dataset quality
- 🎯 **Training-Ready Export**: Generates datasets compatible with video model training pipelines

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Elwii04/Detect-extract-and-prepare-photo-series.git
cd Detect-extract-and-prepare-photo-series

# Install dependencies
pip install -r requirements.txt
```

### 2. API Key Setup

Get your free API key from [Google AI Studio](https://ai.google.dev) and set it up:

```bash
# Method 1: Environment variable (recommended)
set GEMINI_API_KEY=YOUR_API_KEY_HERE

# Method 2: Use command line parameter
python main.py analyze ./pics --api-key YOUR_API_KEY
```

### 3. Analyze Your Images

```bash
# Analyze all series (sorted by size, largest first)
python main.py analyze ./pics

# Test with only first 5 series for quick validation
python main.py analyze ./pics --test-limit 5

# Process without sorting (random order)
python main.py analyze ./pics --no-sort
```

### 4. Review Results

```bash
# View analysis statistics
python main.py stats

# Create training dataset
python main.py create-dataset --output-dir training_data
```

## 📋 Requirements

- **Python 3.7+**
- **Google AI Studio API key** (free at [ai.google.dev](https://ai.google.dev))
- **Instagram-style images** with proper naming convention

## 🖼️ Supported Image Format

Your Instagram images should follow this naming pattern:
```
YYYY_MM_DD_HH_MM_SS_username_caption_XX.jpg
```

**Examples:**
- `2025_08_28_15_09_21_jenny.lbx_vienna_photos_01.jpg`
- `2025_08_28_15_09_21_jenny.lbx_vienna_photos_02.jpg`
- `2025_08_28_15_09_21_jenny.lbx_vienna_photos_03.jpg`

The tool automatically detects sequences where images share the same timestamp, username, and caption but have different sequence numbers.

## 🎯 How It Works

### 1. **Series Detection**
- Automatically groups images by Instagram filename patterns
- Identifies potential photo series from the same session
- Filters by configurable minimum/maximum sequence lengths

### 2. **AI Verification** 
- Uses **Gemini 2.5 Flash** to intelligently verify image series
- Ensures same subject, consistent lighting, and location
- Filters out invalid series (different people, drastic scene changes)
- Orders images chronologically for optimal training sequences

### 3. **Smart Caption Generation**
- Creates single, descriptive captions per series (not per image)
- Uses video-generation optimized language
- Examples: "sequence of photos showing woman posing in different positions"
- Varies caption style for training diversity

### 4. **Training Dataset Export**
- Generates organized folder structure
- Includes metadata files for each series
- Compatible with popular video generation training pipelines

## 🎮 Command Reference

### `analyze` - Process Images
```bash
python main.py analyze <directory> [options]
```

**Options:**
- `--api-key <key>`: Gemini API key (or set `GEMINI_API_KEY` env var)
- `--test-limit N`: Process only first N series (perfect for testing!)
- `--sort-by-size`: Sort by image count, largest first (default)
- `--no-sort`: Process in random order
- `--db-path <path>`: Custom database location

**Examples:**
```bash
# Quick test with 3 largest series
python main.py analyze ./pics --test-limit 3

# Process all without sorting
python main.py analyze ./pics --no-sort

# Use custom database location
python main.py analyze ./pics --db-path my_analysis.db
```

### `stats` - View Results
```bash
python main.py stats [--db-path database.db]
```
Shows comprehensive analysis statistics and lists all valid series found.

### `create-dataset` - Export Training Data
```bash
python main.py create-dataset [--output-dir output] [--min-length 3]
```
Creates a structured training dataset ready for video generation model training.

## ⚙️ Configuration

Customize behavior by editing `config.json`:

```json
{
    "gemini_model": "gemini-2.5-flash",
    "database_path": "photo_series.db",
    "min_images_for_series": 2,
    "max_images_for_series": 20,
    "filename_pattern": "instagram"
}
```

## 📊 Database Schema

The tool creates a SQLite database with the following structure:

### `series` table
- `id`: Unique identifier
- `base_name`: Series identifier
- `is_series`: Whether images form valid series (AI verified)
- `series_caption`: Descriptive caption for entire sequence
- `gemini_parsed_response`: Full AI analysis details
- `image_count`: Number of images in series

### `series_images` table
- `series_id`: Reference to parent series
- `image_path`: Path to image file
- `order_in_series`: Chronological order (1, 2, 3...)

## 🎯 Perfect for Video Generation Training

This tool specifically addresses the challenges of video generation model training:

- ✅ **Temporal Consistency**: Same subject across all frames
- ✅ **Subtle Variations**: Only pose/angle changes, no scene jumps
- ✅ **Proper Sequencing**: Chronologically ordered frames
- ✅ **Quality Filtering**: AI removes invalid or inconsistent series
- ✅ **Optimized Captions**: Video-generation specific prompts

### Example Output

```
Series Caption: "sequence of photos showing woman posing in different positions for photoshoot"

Frames in chronological order:
1. woman_pose_01.jpg (standing straight)
2. woman_pose_02.jpg (slight head tilt)  
3. woman_pose_03.jpg (hand on hip)
4. woman_pose_04.jpg (looking away)
```

This represents a perfect 4-frame "video" sequence ideal for training video generation models!

## 🔧 Advanced Usage

### Custom Database Operations
```python
import sqlite3

# Connect to generated database
conn = sqlite3.connect('photo_series.db')

# Query valid series
cursor = conn.execute("""
    SELECT series_caption, image_count 
    FROM series 
    WHERE is_series = 1 
    ORDER BY image_count DESC
""")

for caption, count in cursor.fetchall():
    print(f"{count} images: {caption}")
```

### Integration with Training Pipelines

The exported dataset structure is compatible with:
- **AnimateDiff** training scripts
- **WAN2.2** with LoRA adapters  
- **Custom video generation** workflows
- **Diffusers library** training examples

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Google's Gemini 2.5 Flash](https://ai.google.dev/) for intelligent image analysis
- Designed for the video generation AI community
- Inspired by the need for high-quality temporal training data

---

<div align="center">

**Ready to create amazing video generation datasets?** 🚀

[Get Started](#-quick-start) | [View Examples](examples/) | [Report Issues](https://github.com/Elwii04/Detect-extract-and-prepare-photo-series/issues)

</div>