"""
Batch processing script for analyzing multiple directories of images
"""

import os
import json
import argparse
from photo_series_detector import PhotoSeriesDetector

def process_directory(directory_path, detector, output_dir=None):
    """
    Process a single directory of images
    
    Args:
        directory_path (str): Path to directory containing images
        detector (PhotoSeriesDetector): Initialized detector
        output_dir (str): Directory to save results (optional)
    
    Returns:
        dict: Results of analysis
    """
    # Get all image files in directory
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
    image_paths = [
        os.path.join(directory_path, f) 
        for f in os.listdir(directory_path) 
        if f.lower().endswith(image_extensions)
    ]
    
    if not image_paths:
        print(f"No images found in directory '{directory_path}'.")
        return None
    
    print(f"Processing {len(image_paths)} images in '{directory_path}'...")
    
    # Detect series
    is_series, avg_similarity = detector.detect_series(image_paths)
    
    # Group into potential series
    groups = detector.group_series(image_paths)
    
    # Prepare results
    results = {
        "directory": directory_path,
        "total_images": len(image_paths),
        "is_series": is_series,
        "average_similarity": float(avg_similarity),
        "similarity_threshold": detector.similarity_threshold,
        "groups": [
            {
                "images": group,
                "count": len(group)
            }
            for group in groups
        ],
        "all_images": image_paths
    }
    
    # Save results if output directory specified
    if output_dir:
        # Create output filename based on directory name
        dir_name = os.path.basename(os.path.normpath(directory_path))
        output_filename = f"{dir_name}_results.json"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results saved to: {output_path}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Batch process directories for photo series detection")
    parser.add_argument("directories", nargs="+", help="Directories containing images to analyze")
    parser.add_argument("--threshold", type=float, default=0.85, 
                        help="Similarity threshold for series detection (default: 0.85)")
    parser.add_argument("--output-dir", default=None,
                        help="Directory to save result files (optional)")
    
    args = parser.parse_args()
    
    # Validate directories
    valid_directories = []
    for directory in args.directories:
        if os.path.isdir(directory):
            valid_directories.append(directory)
        else:
            print(f"Warning: Directory '{directory}' does not exist. Skipping.")
    
    if not valid_directories:
        print("No valid directories provided.")
        return
    
    # Create output directory if specified
    if args.output_dir and not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Initialize detector
    detector = PhotoSeriesDetector(similarity_threshold=args.threshold)
    
    # Process each directory
    all_results = []
    for directory in valid_directories:
        try:
            result = process_directory(directory, detector, args.output_dir)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"Error processing directory '{directory}': {e}")
    
    # Create summary report
    if all_results:
        summary = {
            "total_directories_processed": len(all_results),
            "directories_with_series": sum(1 for r in all_results if r["is_series"]),
            "results": all_results
        }
        
        # Print summary
        print("\nBatch Processing Summary:")
        print(f"Total directories processed: {summary['total_directories_processed']}")
        print(f"Directories with photo series: {summary['directories_with_series']}")
        
        # Save summary if output directory specified
        if args.output_dir:
            summary_path = os.path.join(args.output_dir, "batch_summary.json")
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"\nSummary saved to: {summary_path}")

if __name__ == "__main__":
    main()