"""
Script to export database results for video training dataset analysis
"""

import sqlite3
import csv
import argparse
import json

def export_to_csv(db_path, output_dir):
    """
    Export database tables to CSV files
    
    Args:
        db_path (str): Path to SQLite database file
        output_dir (str): Directory to save CSV files
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Export series table
    cursor.execute("SELECT * FROM series")
    series_data = cursor.fetchall()
    
    series_columns = [description[0] for description in cursor.description]
    
    with open(f"{output_dir}/series.csv", 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(series_columns)
        writer.writerows(series_data)
    
    print(f"Exported {len(series_data)} series to {output_dir}/series.csv")
    
    # Export series_images table
    cursor.execute("SELECT * FROM series_images")
    images_data = cursor.fetchall()
    
    images_columns = [description[0] for description in cursor.description]
    
    with open(f"{output_dir}/series_images.csv", 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(images_columns)
        writer.writerows(images_data)
    
    print(f"Exported {len(images_data)} images to {output_dir}/series_images.csv")
    
    conn.close()

def export_valid_series(db_path, output_file):
    """
    Export paths of images in valid series for video training
    
    Args:
        db_path (str): Path to SQLite database file
        output_file (str): Path to output JSON file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all valid series with their ordered images
    cursor.execute("""
        SELECT s.id, s.base_name, s.series_caption, si.image_path, si.order_in_series
        FROM series s
        JOIN series_images si ON s.id = si.series_id
        WHERE s.is_series = 1
        ORDER BY s.base_name, si.order_in_series
    """)
    
    rows = cursor.fetchall()
    
    # Group by series
    series_dict = {}
    for series_id, base_name, caption, image_path, order in rows:
        if base_name not in series_dict:
            series_dict[base_name] = {
                "caption": caption,
                "images": []
            }
        series_dict[base_name]["images"].append({
            "path": image_path,
            "order": order
        })
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(series_dict, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(series_dict)} valid series to {output_file}")
    
    conn.close()

def export_training_metadata(db_path, output_file):
    """
    Export metadata specifically formatted for video training
    
    Args:
        db_path (str): Path to SQLite database file
        output_file (str): Path to output JSON file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all valid series
    cursor.execute("""
        SELECT base_name, series_caption, image_count
        FROM series
        WHERE is_series = 1
        ORDER BY image_count DESC
    """)
    
    series_data = cursor.fetchall()
    
    # Format as training metadata
    training_metadata = []
    for base_name, caption, image_count in series_data:
        training_metadata.append({
            "series_id": base_name,
            "prompt": caption,
            "frame_count": image_count,
            "is_valid": True
        })
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(training_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"Exported training metadata for {len(training_metadata)} series to {output_file}")
    
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Export video training dataset")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    parser.add_argument("--output-dir", default=".",
                        help="Directory to save CSV files (default: current directory)")
    parser.add_argument("--export-series", metavar="FILE",
                        help="Export valid series to JSON file")
    parser.add_argument("--export-metadata", metavar="FILE",
                        help="Export training metadata to JSON file")
    
    args = parser.parse_args()
    
    # Export to CSV
    export_to_csv(args.db_path, args.output_dir)
    
    # Export series if requested
    if args.export_series:
        export_valid_series(args.db_path, args.export_series)
    
    # Export metadata if requested
    if args.export_metadata:
        export_training_metadata(args.db_path, args.export_metadata)

if __name__ == "__main__":
    main()