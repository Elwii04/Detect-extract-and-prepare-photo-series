# Photo Series Detector - Project Summary

## What We've Built

A comprehensive **dataset curation tool** for creating high-quality training data for video generation models (like WAN2.2) with LoRA adapters.

## Core Functionality

1. **Photo Series Detection**
   - Automatically identifies image groups from Instagram-style filenames
   - Groups images like `usernameID_caption_01.jpg`, `usernameID_caption_02.jpg`, etc.

2. **AI-Powered Verification & Curation**
   - Uses **Gemini 2.5 Flash** as an intelligent dataset curator
   - AI understands the complete context: training video generation models
   - Filters out invalid series with strict quality controls
   - Orders images chronologically for optimal training sequences
   - Generates varied, descriptive captions specifically for video generation

3. **Enhanced Caption Generation**
   - Creates training-ready captions with video sequence terminology
   - Varied language: "sequence of photos", "photo session", "consecutive shots"
   - Context-aware descriptions perfect for video generation prompts
   - Examples: "photo session capturing model in various poses", "sequence of photos showing influencer in multiple positions"

## Why This Matters

### The Problem
Training video generation models requires high-quality sequential data where:
- The same subject is shown across frames
- Changes are subtle (poses, angles, expressions)
- No drastic scene changes or subject swaps

### The Solution
This tool transforms scattered Instagram photos into "1fps videos" - sequences of the same subject in different poses/angles, perfect for teaching video models temporal consistency.

## Technical Implementation

### Database Schema
- **series**: Metadata about each potential series
- **series_images**: Ordered image paths for valid series
- **analysis_log**: Processing history

### Key Features
- SQLite database for easy querying
- Gemini 2.5 Flash for intelligent analysis
- Single general captions (not per-image descriptions)
- Verified chronological ordering
- Invalid series filtering

## Output for Training

Each valid series becomes a training sample:
```
Prompt: "sequence of photos showing woman posing in different positions for photoshoot"
Frames: 
  - frame_001_woman_pose_01.jpg (standing straight)
  - frame_002_woman_pose_02.jpg (tilting head)  
  - frame_003_woman_pose_03.jpg (hand on hip)
```

Alternative caption styles:
```
"photo session capturing model in various poses"
"consecutive shots of influencer demonstrating different expressions"
"progression of photos featuring athlete in multiple stances"
```

This represents temporal sequences perfect for training video generation models with contextual understanding.

## Usage Workflow

1. Run detection on image directory
2. Review database for valid series
3. Export training dataset
4. Use with your WAN2.2 LoRA training pipeline

## Next Steps

The system is ready to process your Instagram image collection and create a curated dataset for your video generation model training.