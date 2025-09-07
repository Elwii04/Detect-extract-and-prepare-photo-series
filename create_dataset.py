"""
Script to create training datasets for video generation models from photo series
"""

import sqlite3
import argparse
import os
import shutil
import json
import glob
from typing import List, Dict

try:
    import cv2
    import numpy as np
    from PIL import Image
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("⚠️  OpenCV not available. Video creation will be skipped.")
    print("   Install with: pip install opencv-python pillow")
    OPENCV_AVAILABLE = False
    print("⚠️  OpenCV not available. Video creation will be skipped.")
    print("   Install with: pip install opencv-python pillow")

def create_video_from_images(image_paths: List[str], output_path: str, fps: int = 30) -> bool:
    """
    Create a high-quality lossless video from a sequence of images
    
    Args:
        image_paths (List[str]): List of image file paths in order
        output_path (str): Path for output video file
        fps (int): Frames per second for the video
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not OPENCV_AVAILABLE:
        print("   ⚠️  Skipping video creation - OpenCV not available")
        return False
    
    if not image_paths:
        print("   ⚠️  No images provided for video creation")
        return False
    
    try:
        # Read first image to get dimensions
        first_img = cv2.imread(image_paths[0])
        if first_img is None:
            print(f"   ❌ Could not read first image: {image_paths[0]}")
            return False
        
        height, width, layers = first_img.shape
        
        # Create both AVI (lossless) and MP4 (compressed) versions
        base_path = os.path.splitext(output_path)[0]
        avi_path = f"{base_path}.avi"
        mp4_path = f"{base_path}.mp4"
        
        # Create AVI with lossless MJPEG codec
        fourcc_avi = cv2.VideoWriter_fourcc(*'MJPG')
        avi_writer = cv2.VideoWriter(avi_path, fourcc_avi, fps, (width, height))
        
        # Create MP4 with H.264 codec
        fourcc_mp4 = cv2.VideoWriter_fourcc(*'mp4v')
        mp4_writer = cv2.VideoWriter(mp4_path, fourcc_mp4, fps, (width, height))
        
        if not avi_writer.isOpened() or not mp4_writer.isOpened():
            print(f"   ❌ Could not open video writers")
            return False
        
        print(f"   🎬 Creating videos: {os.path.basename(base_path)} ({len(image_paths)} frames, {fps}fps)")
        
        # Add each image as a frame to both videos
        for i, img_path in enumerate(image_paths):
            img = cv2.imread(img_path)
            if img is None:
                print(f"   ⚠️  Could not read image: {img_path}")
                continue
            
            # Resize image if dimensions don't match
            if img.shape[:2] != (height, width):
                img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
            
            avi_writer.write(img)
            mp4_writer.write(img)
        
        # Release video writers
        avi_writer.release()
        mp4_writer.release()
        
        print(f"   ✅ Videos created: {os.path.basename(avi_path)} & {os.path.basename(mp4_path)}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error creating videos: {e}")
        return False

def create_caption_file(caption: str, output_path: str) -> bool:
    """
    Create a text file containing the video caption
    
    Args:
        caption (str): The caption text
        output_path (str): Path for output text file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(caption)
        print(f"   📝 Caption file created: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"   ❌ Error creating caption file: {e}")
        return False

def create_video_training_dataset(db_path: str, output_dir: str, min_length: int = 3):
    """
    Create training dataset for video generation models
    
    Args:
        db_path (str): Path to SQLite database file
        output_dir (str): Directory to create training dataset in
        min_length (int): Minimum number of images per series
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all valid series for training
    cursor.execute("""
        SELECT id, base_name, series_caption, image_count
        FROM series
        WHERE is_series = 1 
        AND image_count >= ?
        ORDER BY image_count DESC
    """, (min_length,))
    
    series_data = cursor.fetchall()
    
    if not series_data:
        print(f"No valid series found with at least {min_length} images.")
        return
    
    print(f"Found {len(series_data)} valid series for video training:")
    
    # Create training data structure
    training_data = []
    
    for series_id, base_name, series_caption, image_count in series_data:
        print(f"  - {base_name} ({image_count} images)")
        
        # Get ordered images for this series
        cursor.execute("""
            SELECT image_path, order_in_series
            FROM series_images
            WHERE series_id = ?
            ORDER BY order_in_series
        """, (series_id,))
        
        image_data = cursor.fetchall()
        
        # Verify all images exist and fix paths
        valid_images = []
        for image_path, order in image_data:
            # Try the stored path first
            if os.path.exists(image_path):
                valid_images.append((image_path, order))
            else:
                # If stored path doesn't exist, try to find in pics directory
                image_filename = os.path.basename(image_path)
                
                # Handle truncated filenames with ...
                if "..." in image_filename:
                    # Extract the prefix before ... and suffix after ...
                    parts = image_filename.split("...")
                    if len(parts) >= 2:
                        prefix = parts[0]
                        suffix = parts[-1]
                        # Find matching files using glob pattern
                        pattern = os.path.join("pics", f"{prefix}*{suffix}")
                        matching_files = glob.glob(pattern)
                        if matching_files:
                            # Use the first match
                            pics_path = os.path.abspath(matching_files[0])
                            valid_images.append((pics_path, order))
                            print(f"    Matched: {os.path.basename(matching_files[0])}")
                            continue
                
                # Try direct path match
                pics_path = os.path.abspath(os.path.join("pics", image_filename))
                if os.path.exists(pics_path):
                    valid_images.append((pics_path, order))
                    print(f"    Fixed path: {image_filename}")
                else:
                    print(f"    Warning: Missing image {image_filename}")
        
        # Only include series where all images exist
        if len(valid_images) == len(image_data) and len(valid_images) >= min_length:
            # Create a clean filename base (handle truncated base_name)
            clean_base_name = base_name.replace("...", "").replace("/", "_").replace("\\", "_")
            if len(clean_base_name) > 100:  # Limit filename length
                clean_base_name = clean_base_name[:100]
            
            # Copy images to output directory with series prefix
            image_paths = []
            for image_path, order in valid_images:
                try:
                    # Copy image with proper naming
                    filename = os.path.basename(image_path)
                    new_filename = f"{clean_base_name}_frame_{order:03d}_{filename}"
                    dst_path = os.path.join(output_dir, new_filename)
                    
                    shutil.copy2(image_path, dst_path)
                    image_paths.append(dst_path)
                except Exception as e:
                    print(f"    Error copying {image_path}: {e}")
            
            if image_paths:
                # Create videos from images (both AVI and MP4)
                video_base_path = os.path.join(output_dir, clean_base_name)
                video_created = create_video_from_images(image_paths, video_base_path, fps=30)
                
                # Create caption file
                caption_filename = f"{clean_base_name}.txt"
                caption_path = os.path.join(output_dir, caption_filename)
                caption_created = False
                if series_caption:
                    caption_created = create_caption_file(series_caption, caption_path)
                else:
                    print(f"   ⚠️  No caption available for {clean_base_name}")
                
                # Create metadata file
                metadata_filename = f"{clean_base_name}_metadata.json"
                metadata_path = os.path.join(output_dir, metadata_filename)
                
                metadata = {
                    "series_id": clean_base_name,
                    "original_base_name": base_name,
                    "frame_count": len(image_paths),
                    "caption": series_caption,
                    "frame_sequence": [os.path.basename(path) for path in image_paths],
                    "video_avi_file": f"{clean_base_name}.avi" if video_created else None,
                    "video_mp4_file": f"{clean_base_name}.mp4" if video_created else None,
                    "caption_file": caption_filename if caption_created else None,
                    "metadata_file": metadata_filename
                }
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            else:
                # No images found - initialize variables
                video_created = False
                caption_created = False
                clean_base_name = base_name
            
            # Add to training data
            training_data.append({
                "series_id": clean_base_name,
                "original_base_name": base_name,
                "caption": series_caption,
                "frame_count": len(image_paths),
                "series_directory": output_dir
            })
    
    # Create overall dataset manifest
    manifest = {
        "dataset_name": "Photo Series Video Training Dataset",
        "total_series": len(training_data),
        "series": training_data
    }
    
    manifest_path = os.path.join(output_dir, "dataset_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎬 Video training dataset created successfully!")
    print(f"📁 Output directory: {output_dir}")
    print(f"📊 Total series included: {len(training_data)}")
    print(f"📋 Manifest file: {manifest_path}")
    print(f"\n✅ Each series contains:")
    print(f"   🎥 High-quality lossless video (.avi)")
    print(f"   🎬 Compressed video (.mp4)")
    print(f"   📝 Caption text file (.txt)")
    print(f"   🖼️  Individual frame images") 
    print(f"   📄 Metadata file (_metadata.json)")
    print(f"\n💡 All files are in a single directory - no subfolders!")
    
    if OPENCV_AVAILABLE:
        print(f"💡 AVI files use MJPEG codec (lossless), MP4 files use H.264 (compressed)")
    else:
        print(f"\n⚠️  Install OpenCV to enable video creation: pip install opencv-python")

def export_training_prompts(db_path: str, output_file: str):
    """
    Export training prompts for all valid series
    
    Args:
        db_path (str): Path to SQLite database file
        output_file (str): Path to output JSON file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all valid series with their captions
    cursor.execute("""
        SELECT base_name, series_caption, image_count
        FROM series
        WHERE is_series = 1
        ORDER BY image_count DESC
    """)
    
    series_data = cursor.fetchall()
    
    # Format as training prompts
    training_prompts = []
    for base_name, series_caption, image_count in series_data:
        if series_caption:  # Only include series with captions
            training_prompts.append({
                "id": base_name,
                "prompt": series_caption,
                "frame_count": image_count
            })
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(training_prompts, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(training_prompts)} training prompts to {output_file}")
    
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Create video training dataset from photo series")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    parser.add_argument("--output-dir", default="./video_training_data",
                        help="Directory to create training dataset in (default: ./video_training_data)")
    parser.add_argument("--min-length", type=int, default=3,
                        help="Minimum number of images per series (default: 3)")
    parser.add_argument("--export-prompts", metavar="FILE",
                        help="Export training prompts to JSON file")
    
    args = parser.parse_args()
    
    if args.export_prompts:
        export_training_prompts(args.db_path, args.export_prompts)
    else:
        create_video_training_dataset(
            db_path=args.db_path,
            output_dir=args.output_dir,
            min_length=args.min_length
        )

if __name__ == "__main__":
    main()