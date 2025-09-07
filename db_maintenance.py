"""
Database maintenance utility for Gemini-based photo series detector
"""

import sqlite3
import argparse
import os
import json

def clean_missing_images(db_path):
    """
    Remove references to missing images from the database
    
    Args:
        db_path (str): Path to SQLite database file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all image references
    cursor.execute("SELECT id, image_path FROM series_images")
    images = cursor.fetchall()
    
    print(f"Checking {len(images)} image references...")
    
    missing_count = 0
    removed_count = 0
    
    for image_id, image_path in images:
        if not os.path.exists(image_path):
            missing_count += 1
            print(f"Missing image: {image_path}")
            
            # Remove from database
            cursor.execute("DELETE FROM series_images WHERE id = ?", (image_id,))
            removed_count += 1
    
    if missing_count > 0:
        # Also clean up series that might now be empty
        cursor.execute("""
            DELETE FROM series 
            WHERE id NOT IN (SELECT DISTINCT series_id FROM series_images WHERE series_id IS NOT NULL)
        """)
        empty_series_count = cursor.rowcount
        
        conn.commit()
        
        print(f"\nDatabase cleanup complete:")
        print(f"  Missing images found: {missing_count}")
        print(f"  References removed: {removed_count}")
        print(f"  Empty series removed: {empty_series_count}")
    else:
        print("No missing images found. Database is clean.")
    
    conn.close()

def remove_series_by_name(db_path, base_name):
    """
    Remove a series and its images from the database
    
    Args:
        db_path (str): Path to SQLite database file
        base_name (str): Base name of series to remove
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get series IDs
    cursor.execute("SELECT id FROM series WHERE base_name = ?", (base_name,))
    series_ids = [row[0] for row in cursor.fetchall()]
    
    if not series_ids:
        print(f"No series found with base name '{base_name}'")
        conn.close()
        return
    
    # Remove images
    removed_images = 0
    for series_id in series_ids:
        cursor.execute("DELETE FROM series_images WHERE series_id = ?", (series_id,))
        removed_images += cursor.rowcount
    
    # Remove series
    cursor.execute("DELETE FROM series WHERE base_name = ?", (base_name,))
    removed_series = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Removed {removed_series} series and {removed_images} images with base name '{base_name}'")

def list_series(db_path, limit=50):
    """
    List series in the database
    
    Args:
        db_path (str): Path to SQLite database file
        limit (int): Maximum number of series to list
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT base_name, image_count, is_series
        FROM series
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    
    series_data = cursor.fetchall()
    
    print(f"{'Base Name':<30} {'Images':<8} {'Status':<10}")
    print("-" * 50)
    
    for base_name, image_count, is_series in series_data:
        status = "Series" if is_series else "Not Series"
        print(f"{base_name:<30} {image_count:<8} {status:<10}")
    
    conn.close()

def show_series_analysis(db_path, base_name):
    """
    Show the Gemini analysis for a specific series
    
    Args:
        db_path (str): Path to SQLite database file
        base_name (str): Base name of series to analyze
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT is_series, gemini_parsed_response
        FROM series
        WHERE base_name = ?
    """, (base_name,))
    
    row = cursor.fetchone()
    
    if not row:
        print(f"No series found with base name '{base_name}'")
        conn.close()
        return
    
    is_series, parsed_response_json = row
    
    print(f"Series: {base_name}")
    print(f"Is Series: {is_series}")
    
    if parsed_response_json:
        try:
            parsed_response = json.loads(parsed_response_json)
            print("\nGemini Analysis:")
            print(json.dumps(parsed_response, indent=2))
        except json.JSONDecodeError:
            print("\nGemini Analysis: Could not parse response")
    else:
        print("\nGemini Analysis: No response available")
    
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Database maintenance for photo series detector")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    
    subparsers = parser.add_subparsers(dest='command', help='Maintenance commands')
    
    # Clean command
    subparsers.add_parser('clean', help='Remove references to missing images')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove series by base name')
    remove_parser.add_argument('base_name', help='Base name of series to remove')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List series in database')
    list_parser.add_argument('--limit', type=int, default=50,
                            help='Maximum number of series to list (default: 50)')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Show Gemini analysis for a series')
    analyze_parser.add_argument('base_name', help='Base name of series to analyze')
    
    args = parser.parse_args()
    
    if args.command == 'clean':
        clean_missing_images(args.db_path)
    elif args.command == 'remove':
        remove_series_by_name(args.db_path, args.base_name)
    elif args.command == 'list':
        list_series(args.db_path, args.limit)
    elif args.command == 'analyze':
        show_series_analysis(args.db_path, args.base_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()