#!/usr/bin/env python3
"""
Main entry point for the Photo Series Detector AI Dataset Curation Tool

This tool analyzes Instagram-scraped images to create high-quality training datasets
for video generation models (like WAN2.2) using Gemini 2.5 Flash for intelligent curation.

Usage:
    python main.py analyze ./pics --api-key YOUR_GEMINI_API_KEY
    python main.py create-dataset --db-path photo_series.db --output-dir training_data
    python main.py stats --db-path photo_series.db
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

# Import our modules
from photo_series_detector import PhotoSeriesDetector, find_image_series
from create_dataset import create_video_training_dataset
from db_stats import show_database_stats
import sqlite3

def load_config():
    """Load configuration from config.json"""
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {
        "gemini_model": "gemini-2.5-flash",
        "database_path": "photo_series.db",
        "min_images_for_series": 2,
        "max_images_for_series": 14,
        "filename_pattern": "instagram"
    }

def get_existing_series_from_db(db_path):
    """Get list of series that have already been analyzed"""
    if not os.path.exists(db_path):
        return set()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT base_name FROM series")
        existing_series = {row[0] for row in cursor.fetchall()}
        conn.close()
        return existing_series
    except Exception as e:
        print(f"⚠️  Warning: Could not read existing series from database: {e}")
        return set()

def check_database_status_and_filter(db_path, series_dict):
    """Check database status and filter out already processed series"""
    if not os.path.exists(db_path):
        print(f"📊 Database Status: New database will be created at {db_path}")
        return series_dict, 0, 0
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get database statistics
        cursor.execute("SELECT COUNT(*) FROM series")
        total_analyzed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM series WHERE is_series = 1")
        confirmed_series = cursor.fetchone()[0]
        
        # Get existing series base names
        cursor.execute("SELECT base_name FROM series")
        existing_series = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        print(f"📊 Database Status:")
        print(f"   📈 Total series analyzed: {total_analyzed}")
        print(f"   ✅ Confirmed photo series: {confirmed_series}")
        print(f"   📁 Series in database: {len(existing_series)}")
        
        # Filter out already processed series
        new_series_dict = {}
        skipped_count = 0
        
        for base_name, image_paths in series_dict.items():
            if base_name in existing_series:
                skipped_count += 1
            else:
                new_series_dict[base_name] = image_paths
        
        print(f"   🔍 Found {len(series_dict)} total series in directory")
        print(f"   ⏭️  Skipping {skipped_count} already processed series")
        print(f"   🆕 New series to process: {len(new_series_dict)}")
        
        return new_series_dict, total_analyzed, confirmed_series
        
    except Exception as e:
        print(f"⚠️  Warning: Could not read database status: {e}")
        print("   Proceeding with all series...")
        return series_dict, 0, 0

def analyze_images(args):
    """Analyze images for photo series detection"""
    config = load_config()
    
    # Validate inputs
    if not os.path.isdir(args.directory):
        print(f"❌ Error: Directory '{args.directory}' does not exist.")
        return False
    
    # Handle API key from multiple sources
    api_key = args.api_key
    if not api_key:
        # Try to get from environment variable
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY')
        if not api_key:
            print("❌ Error: Gemini API key is required!")
            print("   Use one of these methods:")
            print("   1. --api-key YOUR_KEY")
            print("   2. Set GEMINI_API_KEY environment variable")
            print("   3. Set GOOGLE_AI_API_KEY environment variable")
            return False
    
    db_path = args.db_path or config["database_path"]
    
    print(f"🔍 Scanning directory '{args.directory}' for image series...")
    print(f"📊 Database: {db_path}")
    print(f"🤖 Using model: {config['gemini_model']}")
    
    # Find image series based on Instagram naming patterns
    series_dict = find_image_series(args.directory)
    
    if not series_dict:
        print("❌ No image series found with Instagram naming patterns.")
        print("   Expected format: YYYY_MM_DD_HH_MM_SS_username_caption_XX.jpg")
        return False
    
    # Check database status and filter out already processed series
    series_dict, existing_total, existing_confirmed = check_database_status_and_filter(db_path, series_dict)
    
    if not series_dict:
        print("✅ All series in this directory have already been processed!")
        print(f"💡 Current database contains {existing_total} analyzed series ({existing_confirmed} confirmed)")
        print("   Use 'python main.py stats' to see detailed statistics")
        return True
    
    # Sort series by number of images (largest first) - this is now the default
    if args.sort_by_size:
        sorted_series = sorted(series_dict.items(), key=lambda x: len(x[1]), reverse=True)
        print(f"📊 Sorting {len(sorted_series)} series by image count (largest first)")
    else:
        sorted_series = list(series_dict.items())
    
    # Limit number of series for testing if specified
    if args.test_limit and args.test_limit > 0:
        sorted_series = sorted_series[:args.test_limit]
        print(f"🧪 Testing mode: Processing only first {len(sorted_series)} series")
    
    print(f"✅ Found {len(sorted_series)} series to process")
    
    # Show series preview
    print("\n📋 Series Preview:")
    for i, (base_name, image_paths) in enumerate(sorted_series[:10], 1):  # Show first 10
        print(f"   {i:2d}. {base_name[:60]}... ({len(image_paths)} images)")
    if len(sorted_series) > 10:
        print(f"   ... and {len(sorted_series) - 10} more series")
    
    # Initialize detector with improved configuration
    try:
        detector = PhotoSeriesDetector(db_path=db_path, api_key=api_key)
        print(f"✅ Connected to Gemini 2.5 Flash successfully")
    except Exception as e:
        print(f"❌ Error connecting to Gemini API: {e}")
        print("   Please check your API key and internet connection")
        return False
    
    total_images = 0
    total_series = 0
    valid_series = 0
    
    print(f"\n🚀 Starting AI analysis with Gemini 2.5 Flash...")
    
    # Process each series
    for i, (base_name, image_paths) in enumerate(sorted_series, 1):
        print(f"\n[{i}/{len(sorted_series)}] Processing '{base_name[:50]}...'")
        print(f"   📸 {len(image_paths)} images")
        
        # Filter by min/max images
        if len(image_paths) < config["min_images_for_series"]:
            print(f"   ⏭️  Skipping: Too few images (< {config['min_images_for_series']})")
            continue
        
        if len(image_paths) > config["max_images_for_series"]:
            print(f"   ⏭️  Skipping: Too many images (> {config['max_images_for_series']})")
            continue
        
        # Get directory of first image
        directory = os.path.dirname(image_paths[0])
        
        try:
            # Analyze series with Gemini
            raw_response, parsed_response = detector.analyze_series_with_gemini(image_paths)
            
            # Check if it's a valid series
            is_series = parsed_response.get("is_series", False)
            confidence = parsed_response.get("confidence", 0.0)
            
            # Save to database
            detector.save_series_to_db(base_name, directory, image_paths, raw_response, parsed_response)
            
            total_images += len(image_paths)
            total_series += 1
            
            if is_series:
                valid_series += 1
                print(f"   ✅ Valid series detected! (confidence: {confidence:.2f})")
                
                # Show subset information
                included_images = parsed_response.get("images", [])
                excluded_images = parsed_response.get("excluded_images", [])
                
                if excluded_images:
                    print(f"   📸 Subset Selection: {len(included_images)} of {len(image_paths)} images included")
                    print(f"   🚫 Excluded: {', '.join(excluded_images[:3])}{'...' if len(excluded_images) > 3 else ''}")
                else:
                    print(f"   📸 All {len(included_images)} images included in series")
                
                if "series_caption" in parsed_response and parsed_response["series_caption"]:
                    caption = parsed_response["series_caption"]
                    print(f"   🎬 Video Caption: \"{caption}\"")
            else:
                print(f"   ❌ Not a valid series")
                if "reason" in parsed_response:
                    reason = parsed_response["reason"][:100] + "..." if len(parsed_response["reason"]) > 100 else parsed_response["reason"]
                    print(f"   💭 Reason: {reason}")
        
        except Exception as e:
            print(f"   ⚠️  Error analyzing series: {e}")
            continue
    
    # Log analysis
    detector.log_analysis(args.directory, total_images, total_series)
    
    # Print summary
    print(f"\n📊 Analysis Complete!")
    print(f"   🔍 New series processed: {total_series}")
    print(f"   ✅ New valid series found: {valid_series}")
    print(f"   📸 New images analyzed: {total_images}")
    print(f"   💾 Results saved to: {db_path}")
    
    # Show updated database totals
    if existing_total > 0:
        final_total = existing_total + total_series
        final_confirmed = existing_confirmed + valid_series
        print(f"\n📈 Updated Database Totals:")
        print(f"   📊 Total series in database: {final_total}")
        print(f"   ✅ Total confirmed series: {final_confirmed}")
    
    if valid_series > 0:
        print(f"\n💡 Next steps:")
        print(f"   1. Visual review: python main.py review --db-path {db_path}")
        print(f"   2. Show stats: python main.py stats --db-path {db_path}")
        print(f"   3. Create dataset: python main.py create-dataset --db-path {db_path}")
    
    return True

def create_training_dataset(args):
    """Create training dataset from analyzed series"""
    config = load_config()
    db_path = args.db_path or config["database_path"]
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file '{db_path}' not found.")
        print("   Run 'python main.py analyze' first to create the database.")
        return False
    
    output_dir = args.output_dir or "training_data"
    min_length = args.min_length or config["min_images_for_series"]
    
    print(f"📦 Creating training dataset...")
    print(f"   📊 Database: {db_path}")
    print(f"   📁 Output directory: {output_dir}")
    print(f"   📏 Minimum sequence length: {min_length}")
    
    try:
        create_video_training_dataset(db_path, output_dir, min_length)
        print(f"✅ Training dataset created successfully in '{output_dir}'")
        return True
    except Exception as e:
        print(f"❌ Error creating dataset: {e}")
        return False

def show_stats(args):
    """Show database statistics"""
    config = load_config()
    db_path = args.db_path or config["database_path"]
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file '{db_path}' not found.")
        print("   Run 'python main.py analyze' first to create the database.")
        return False
    
    print(f"📊 Database Statistics for: {db_path}")
    show_database_stats(db_path)
    return True

def visual_review(args):
    """Launch visual reviewer for analyzed series"""
    config = load_config()
    db_path = args.db_path or config["database_path"]
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file '{db_path}' not found.")
        print("   Run 'python main.py analyze' first to create the database.")
        return False
    
    print(f"🎨 Launching visual reviewer for: {db_path}")
    
    try:
        # Import and run visual reviewer
        from visual_reviewer import SeriesViewer
        viewer = SeriesViewer(db_path)
        viewer.run()
        return True
    except ImportError as e:
        print(f"❌ Error: Missing required packages for visual reviewer")
        print("   Please install: pip install pillow")
        print(f"   Details: {e}")
        return False
    except Exception as e:
        print(f"❌ Error launching visual reviewer: {e}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI Dataset Curation Tool for Video Generation Training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze images in pics directory
  python main.py analyze ./pics --api-key YOUR_GEMINI_API_KEY
  
  # Visual review of analyzed results (recommended!)
  python main.py review
  
  # Show database statistics
  python main.py stats
  
  # Create training dataset from analyzed results
  python main.py create-dataset --output-dir my_training_data
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze images for photo series')
    analyze_parser.add_argument('directory', help='Directory containing images to analyze')
    analyze_parser.add_argument('--api-key', help='Google AI API key for Gemini access (or set GEMINI_API_KEY env var)')
    analyze_parser.add_argument('--db-path', help='Path to SQLite database file')
    analyze_parser.add_argument('--test-limit', type=int, default=0, 
                                help='For testing: limit to N series (0 = no limit, default)')
    analyze_parser.add_argument('--sort-by-size', action='store_true', default=True,
                                help='Sort series by image count (largest first) - DEFAULT')
    analyze_parser.add_argument('--no-sort', dest='sort_by_size', action='store_false',
                                help='Disable sorting, process in random order')
    
    # Create dataset command
    dataset_parser = subparsers.add_parser('create-dataset', help='Create training dataset from analyzed series')
    dataset_parser.add_argument('--db-path', help='Path to SQLite database file')
    dataset_parser.add_argument('--output-dir', help='Output directory for training dataset')
    dataset_parser.add_argument('--min-length', type=int, help='Minimum number of images per series')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    stats_parser.add_argument('--db-path', help='Path to SQLite database file')
    
    # Visual review command
    review_parser = subparsers.add_parser('review', help='Visual review of analyzed photo series')
    review_parser.add_argument('--db-path', help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🎬 Photo Series Detector - AI Dataset Curation Tool")
    print("   For training video generation models with curated Instagram data\n")
    
    # Execute command
    success = False
    if args.command == 'analyze':
        success = analyze_images(args)
    elif args.command == 'create-dataset':
        success = create_training_dataset(args)
    elif args.command == 'stats':
        success = show_stats(args)
    elif args.command == 'review':
        success = visual_review(args)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
