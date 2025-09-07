"""
Script to prepare training data for video generation model from photo series
"""

import sqlite3
import argparse
import os
import json
from typing import List, Dict

def get_training_sequences(db_path: str, min_length: int = 3, max_length: int = 10) -> List[Dict]:
    """
    Get sequences of images that can be used for video generation training.
    
    Args:
        db_path (str): Path to SQLite database file
        min_length (int): Minimum number of images in a sequence
        max_length (int): Maximum number of images in a sequence
        
    Returns:
        List[Dict]: List of sequences with their image paths and metadata
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all confirmed series with appropriate length
    cursor.execute("""
        SELECT id, base_name, gemini_parsed_response
        FROM series
        WHERE is_series = 1 
        AND image_count >= ?
        AND image_count <= ?
        ORDER BY image_count DESC
    """, (min_length, max_length))
    
    series_data = cursor.fetchall()
    
    sequences = []
    for series_id, base_name, parsed_response_json in series_data:
        # Get ordered images for this series
        cursor.execute("""
            SELECT image_path, order_in_series, change_description
            FROM series_images
            WHERE series_id = ?
            ORDER BY order_in_series
        """, (series_id,))
        
        image_data = cursor.fetchall()
        
        # Verify all images exist
        valid_images = []
        for image_path, order, change_desc in image_data:
            if os.path.exists(image_path):
                valid_images.append({
                    "path": image_path,
                    "order": order,
                    "change_description": change_desc
                })
            else:
                print(f"Warning: Missing image {image_path}")
        
        # Only include sequences where all images exist
        if len(valid_images) == len(image_data) and len(valid_images) >= min_length:
            # Get Gemini analysis
            analysis = {}
            if parsed_response_json:
                try:
                    analysis = json.loads(parsed_response_json)
                except json.JSONDecodeError:
                    analysis = {"error": "Could not parse analysis"}
            
            sequences.append({
                "base_name": base_name,
                "images": valid_images,
                "length": len(valid_images),
                "analysis": analysis
            })
    
    conn.close()
    return sequences

def create_video_training_data(sequences: List[Dict], output_dir: str):
    """
    Create training data directory structure for video generation model.
    
    Args:
        sequences (List[Dict]): List of sequences from get_training_sequences
        output_dir (str): Directory to create training data in
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Creating training data for {len(sequences)} sequences...")
    
    # Create sequences directory
    sequences_dir = os.path.join(output_dir, "sequences")
    os.makedirs(sequences_dir, exist_ok=True)
    
    # Copy images and create metadata for each sequence
    for i, sequence in enumerate(sequences):
        # Create sequence directory
        seq_dir = os.path.join(sequences_dir, f"sequence_{i:04d}")
        os.makedirs(seq_dir, exist_ok=True)
        
        # Copy images in order
        for image_info in sequence["images"]:
            try:
                # Copy image
                src_path = image_info["path"]
                filename = os.path.basename(src_path)
                dst_path = os.path.join(seq_dir, f"{image_info['order']:02d}_{filename}")
                
                import shutil
                shutil.copy2(src_path, dst_path)
                
                # Save change description
                if image_info["change_description"]:
                    desc_path = os.path.join(seq_dir, f"{image_info['order']:02d}_description.txt")
                    with open(desc_path, 'w', encoding='utf-8') as f:
                        f.write(image_info["change_description"])
            except Exception as e:
                print(f"Error processing image {src_path}: {e}")
        
        # Save sequence metadata
        metadata = {
            "base_name": sequence["base_name"],
            "length": sequence["length"],
            "analysis": sequence["analysis"]
        }
        
        metadata_path = os.path.join(seq_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Create overall dataset metadata
    dataset_metadata = {
        "total_sequences": len(sequences),
        "sequences": [
            {
                "id": f"sequence_{i:04d}",
                "base_name": seq["base_name"],
                "length": seq["length"]
            }
            for i, seq in enumerate(sequences)
        ]
    }
    
    dataset_metadata_path = os.path.join(output_dir, "dataset_metadata.json")
    with open(dataset_metadata_path, 'w', encoding='utf-8') as f:
        json.dump(dataset_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"Training data created in: {output_dir}")
    print(f"Total sequences: {len(sequences)}")

def main():
    parser = argparse.ArgumentParser(description="Prepare training data for video generation model")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    parser.add_argument("--output-dir", default="./video_training_data",
                        help="Directory to create training data in (default: ./video_training_data)")
    parser.add_argument("--min-length", type=int, default=3,
                        help="Minimum sequence length (default: 3)")
    parser.add_argument("--max-length", type=int, default=10,
                        help="Maximum sequence length (default: 10)")
    
    args = parser.parse_args()
    
    # Get training sequences
    sequences = get_training_sequences(
        db_path=args.db_path,
        min_length=args.min_length,
        max_length=args.max_length
    )
    
    if not sequences:
        print("No valid sequences found for training data.")
        return
    
    print(f"Found {len(sequences)} valid sequences for training:")
    for i, seq in enumerate(sequences):
        print(f"  {i+1:2d}. {seq['base_name']} ({seq['length']} images)")
    
    # Create training data
    create_video_training_data(sequences, args.output_dir)

if __name__ == "__main__":
    main()