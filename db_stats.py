"""
Utility script to view database statistics for video training dataset
"""

import sqlite3
import argparse
import json

def show_database_stats(db_path):
    """
    Show statistics about the photo series database
    
    Args:
        db_path (str): Path to SQLite database file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== VIDEO TRAINING DATASET STATISTICS ===\n")
    
    # Overall statistics
    cursor.execute("SELECT COUNT(*) FROM series")
    total_series = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM series WHERE is_series = 1")
    confirmed_series = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM series_images")
    total_images = cursor.fetchone()[0]
    
    print(f"Total series analyzed: {total_series}")
    print(f"Confirmed photo series: {confirmed_series}")
    print(f"Total images in series: {total_images}")
    
    if total_series > 0:
        # Average images per series
        cursor.execute("SELECT AVG(image_count) FROM series WHERE is_series = 1")
        avg_images = cursor.fetchone()[0]
        print(f"Average images per valid series: {avg_images:.1f}")
        
        # Series size distribution
        print("\nSeries size distribution:")
        cursor.execute("""
            SELECT image_count, COUNT(*) as count
            FROM series 
            WHERE is_series = 1
            GROUP BY image_count
            ORDER BY image_count
        """)
        
        size_data = cursor.fetchall()
        for size, count in size_data:
            print(f"  {size} images: {count} series")

def show_top_series(db_path, limit=10):
    """
    Show top series with their captions
    
    Args:
        db_path (str): Path to SQLite database file
        limit (int): Number of top series to show
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n=== TOP {limit} VALID SERIES FOR VIDEO TRAINING ===\n")
    
    cursor.execute("""
        SELECT base_name, series_caption, image_count
        FROM series
        WHERE is_series = 1
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    series_data = cursor.fetchall()
    
    for i, (name, caption, count) in enumerate(series_data, 1):
        print(f"{i:2d}. {name} ({count} images)")
        if caption:
            print(f"    Caption: {caption}")
        print()

def main():
    parser = argparse.ArgumentParser(description="View video training dataset statistics")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    parser.add_argument("--top", type=int, metavar="N",
                        help="Show top N series")
    
    args = parser.parse_args()
    
    # Show database statistics
    show_database_stats(args.db_path)
    
    # Show top series if requested
    if args.top:
        show_top_series(args.db_path, args.top)

if __name__ == "__main__":
    main()