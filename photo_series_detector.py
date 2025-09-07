import os
import sqlite3
import argparse
import re
import json
from typing import List, Dict, Tuple
from collections import defaultdict

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

# Use the old Google GenerativeAI SDK which is more stable
try:
    import google.generativeai as genai
except ImportError:
    print("❌ Error: google-generativeai package not found!")
    print("   Install with: pip install google-generativeai")
    exit(1)

class PhotoSeriesDetector:
    def __init__(self, db_path: str, api_key: str):
        """
        Initialize the PhotoSeriesDetector with database connection and Gemini API.
        
        Args:
            db_path (str): Path to SQLite database file.
            api_key (str): Google AI API key for Gemini access.
        """
        self.db_path = db_path
        self.api_key = api_key
        
        # Initialize database
        self.init_database()
        
        # Initialize Gemini with the old SDK (more stable)
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # We'll store thinking results when available
        self.last_thinking_summary = None
        self.last_thinking_tokens = 0
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_name TEXT NOT NULL,
                directory TEXT NOT NULL,
                is_series BOOLEAN NOT NULL,
                gemini_raw_response TEXT,
                gemini_parsed_response TEXT,
                series_caption TEXT,
                image_count INTEGER,
                thinking_summary TEXT,
                thinking_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS series_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                image_path TEXT NOT NULL,
                order_in_series INTEGER,
                FOREIGN KEY (series_id) REFERENCES series (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directory TEXT NOT NULL,
                total_images INTEGER,
                total_series INTEGER,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def image_to_base64(self, image_path: str) -> str:
        """
        Convert an image to base64 string.
        
        Args:
            image_path (str): Path to the image file.
            
        Returns:
            str: Base64 encoded image.
        """
        try:
            with open(image_path, "rb") as image_file:
                import base64
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error converting image to base64: {e}")
            return ""
    
    def analyze_series_with_gemini(self, image_paths: List[str]) -> Tuple[str, Dict]:
        """
        Analyze a series of images using Gemini 2.5 Flash with proper image ID mapping.
        
        Args:
            image_paths (List[str]): List of paths to image files.
            
        Returns:
            Tuple[str, Dict]: Raw response from Gemini and parsed JSON response.
        """
        if len(image_paths) < 2:
            return "", {"is_series": False, "images": [], "excluded_images": [], "reason": "Less than 2 images"}
        
        # Convert images to base64 and create image ID mapping
        image_data = []
        image_id_mapping = {}  # Maps short_id -> full_path
        
        for i, path in enumerate(image_paths):
            base64_image = self.image_to_base64(path)
            if base64_image:
                # Extract short ID from Instagram filename
                filename = os.path.basename(path)
                short_id = self.extract_image_id(filename, i)
                
                image_data.append(base64_image)
                image_id_mapping[short_id] = path
                
                print(f"   Mapped: {short_id} -> {filename}")
        
        if not image_data:
            return "", {"is_series": False, "images": [], "excluded_images": [], "reason": "No valid images found"}
        
        # Create the prompt for Gemini with image ID information
        prompt = self.create_gemini_prompt(image_paths, image_data, image_id_mapping)
        
        try:
            # Send request to Gemini using the old SDK (more stable)
            response = self.model.generate_content(prompt)
            
            # Extract main response text
            raw_response = response.text
            
            # Extract thinking summary and token count if available
            thinking_summary = ""
            thinking_tokens = 0
            
            # Check for usage metadata (if available in response)
            if hasattr(response, 'usage_metadata'):
                if hasattr(response.usage_metadata, 'total_token_count'):
                    thinking_tokens = response.usage_metadata.total_token_count
                    print(f"   🧠 AI used {thinking_tokens} tokens")
            
            # Store thinking results for database
            self.last_thinking_summary = thinking_summary
            self.last_thinking_tokens = thinking_tokens
            
            # Try to parse JSON from response
            parsed_response = self.parse_gemini_response(raw_response)
            
            # Add thinking data to parsed response
            parsed_response["thinking_summary"] = self.last_thinking_summary or ""
            parsed_response["thinking_tokens"] = self.last_thinking_tokens
            
            # Convert short IDs back to full paths in the response
            if parsed_response.get("is_series") and "images" in parsed_response:
                for img_info in parsed_response["images"]:
                    short_id = img_info.get("path", "")
                    if short_id in image_id_mapping:
                        img_info["path"] = os.path.basename(image_id_mapping[short_id])
                        img_info["full_path"] = image_id_mapping[short_id]
            
            return raw_response, parsed_response
        except Exception as e:
            print(f"Error analyzing series with Gemini: {e}")
            error_response = {
                "is_series": False,
                "images": [],
                "excluded_images": [],
                "reason": f"Error analyzing with Gemini: {str(e)}"
            }
            return str(e), error_response
    
    def extract_image_id(self, filename: str, fallback_index: int) -> str:
        """
        Extract a short, meaningful ID from Instagram filename.
        
        Args:
            filename (str): Full Instagram filename
            fallback_index (int): Fallback index if extraction fails
            
        Returns:
            str: Short ID like "_02", "_11", or "img_1"
        """
        # Instagram pattern: ...caption_XX.jpg where XX is the number
        if filename.endswith('.jpg') or filename.endswith('.jpeg'):
            # Find the last underscore before .jpg
            name_without_ext = filename.rsplit('.', 1)[0]
            parts = name_without_ext.split('_')
            
            # Look for a numeric suffix
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    return f"_{parts[i]}"
            
        # Fallback to simple numbering
        return f"img_{fallback_index + 1}"
    
    def create_gemini_prompt(self, image_paths: List[str], image_data: List[str], image_id_mapping: Dict[str, str]) -> List:
        """
        Create a structured prompt for Gemini analysis with proper image ID mapping.
        
        Args:
            image_paths (List[str]): List of paths to image files.
            image_data (List[str]): List of base64 encoded images.
            image_id_mapping (Dict[str, str]): Mapping of short IDs to full paths.
            
        Returns:
            List: Prompt structure for the new Gemini SDK.
        """
        # Create ordered list of IDs to ensure consistent mapping
        ordered_image_info = []
        content_parts = []
        
        # Build ordered list from the image_data and corresponding IDs
        for i, base64_data in enumerate(image_data):
            # Find the corresponding ID for this image position
            corresponding_path = image_paths[i]
            corresponding_id = None
            
            for short_id, full_path in image_id_mapping.items():
                if full_path == corresponding_path:
                    corresponding_id = short_id
                    break
            
            if corresponding_id:
                ordered_image_info.append((i + 1, corresponding_id))
                content_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": base64_data
                    }
                })
        
        # Create explicit image mapping text
        image_mapping_text = "\n".join([f"        Image {pos}: ID {img_id}" for pos, img_id in ordered_image_info])
        image_ids = [img_id for _, img_id in ordered_image_info]
        
        # Create the text prompt - optimized for Instagram photo series analysis with subset detection
        text_prompt = f"""
        You are an AI curator specializing in creating high-quality training datasets for video generation models like WAN2.2. 

        CONTEXT: I'm building a dataset to train a lora for an AI video model to generate a realistic and coherent photo series. The idea is to make use of the video models knowledge of koherent frames and basically make it generate a very low fps video - a photo series. It will be a i2v model, i will give in an image of my character and it will give out my character in different poses. For data i scraped a bunch of instagram posts, they often contain mixed content and not always a nice photo series, your job is to filter the dataset.

        IMAGE IDENTIFICATION: I'm showing you {len(ordered_image_info)} images in sequence. Here's the explicit mapping:
        {image_mapping_text}
        
        IMPORTANT: When referring to images in your response, use EXACTLY these IDs: {', '.join(image_ids)}
        

        YOUR MISSION: Analyze these {len(image_paths)} Instagram images to find the LARGEST COHERENT SUBSET that forms a valid training sequence for video generation AI. You don't need ALL images to be valid - find the best subsequence within this group, there can also be none and it could just be a random post.

        SUBSET DETECTION STRATEGY:
        🔍 Look for the LARGEST group of images (minimum 2) that share:
        ✅ IDENTICAL subject/person 
        ✅ IDENTICAL location/background/setting  
        ✅ IDENTICAL lighting conditions and photo session
        ✅ IDENTICAL or very similar outfit/clothing
        ✅ Natural progression between poses/expressions
        ✅ Same camera distance/framing

        PROCESS:
        1. First, identify all images that belong to the SAME photo session (same person, outfit, location, lighting)
        2. From that group, find the largest subset with NATURAL FLOW between poses
        3. Order the selected images to create the most natural progression, ideally starting with a clear image of the main character so the model sees the character clearly and can later portrait it in different poses.
        4. Only accept if you can find at least 2 coherent images

        ORDERING RULES FOR VIDEO GENERATION:
        🎯 FIRST IMAGE PRIORITY: If the series contains people/characters, the FIRST image must show the main subject clearly. Try to match it so that the first pic is always the image where the character is displayed nearest to the camera and looks straight at it, getting most facial information.
        🏞️ LANDSCAPE PLACEMENT: Any landscape/nature shots (no people) of the place where the character was before should be ordered LAST in the sequence
        📖 STORY FLOW: Character shots should flow naturally, then end with environmental/context shots if present
        💡 RATIONALE: Video generation models work best when starting with clear subject identification

        REJECT IF:
        ❌ No coherent subset of 2+ images exists
        ❌ All images are completely random/unrelated like different background, clothing, subject etc.
        ❌ Cannot find consistent subject, location, or session

        Critical: Its important that you are strict with the selection. Only include images that really show a valid photo series! If there is too much variation in the scene, its a completely different background, person dont include. I mean you can include something like a photoshoot of the same subject in differnt clothing, thats ok since its the same background and same person, then you would describe the photoshoot in the caption. You get the point, the scene musst not completely change!

        CAPTION REQUIREMENTS:
        Write a prompt for the video model to train on that describes what happens in the video/image series. Try to vary your caption and use natural language to decribe what happens. Dont say what changes frame to frame but more like a general description of what is happening. Your caption describes your SELECTED SUBSET (not all images) in 10-35 words:

        SPECIAL ORDERING RULES:
        🎭 CHARACTER PRIORITY: If photos contain a subject character, the FIRST image must always show the main character clearly
        🏞️ LANDSCAPE PLACEMENT: Any landscape/nature shots in the photo series without main subjects should be placed LAST in the sequence
        📝 CAPTION NOTATION: If including landscape shots, mention "with nature shots in final frames" or "ending with landscape views"

        Keep captions 10-35 words, detailed enough for video generation prompts.

        RESPOND in this EXACT JSON format using the provided image IDs:
        {{
            "is_series": true/false,
            "images": [
                {{
                    "path": "{image_ids[0] if image_ids else '_01'}",
                    "order": 1
                }}
            ],
            "excluded_images": ["{image_ids[1] if len(image_ids) > 1 else '_02'}", "{image_ids[2] if len(image_ids) > 2 else '_03'}"],
            "series_caption": "sequence of photos showing [subject] [action/pose description]",
            "reason": "Found [X] out of [Y] images forming coherent sequence. Excluded [Z] images that didn't fit the progression.",
            "confidence": 0.95
        }}

        CRITICAL: Use ONLY the provided image IDs in your response: {', '.join(image_ids)}

        QUALITY STANDARDS: Accept if you can find 3+ coherent images with confidence > 75%. Focus on finding the BEST SUBSET, not requiring perfection from all images.

        Now analyze these Instagram images for my video generation training dataset:
        """
        
        # Combine text prompt and images for the old SDK
        prompt = [text_prompt] + content_parts
        
        return prompt
    
    def parse_gemini_response(self, raw_response: str) -> Dict:
        """
        Parse JSON response from Gemini with improved error handling and validation.
        
        Args:
            raw_response (str): Raw response from Gemini.
            
        Returns:
            Dict: Parsed JSON response with fallback values.
        """
        try:
            # Try to find JSON in the response
            # Look for content between curly braces
            start = raw_response.find('{')
            end = raw_response.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = raw_response[start:end]
                parsed = json.loads(json_str)
                
                # Ensure required fields exist with defaults
                result = {
                    "is_series": parsed.get("is_series", False),
                    "images": parsed.get("images", []),
                    "excluded_images": parsed.get("excluded_images", []),
                    "series_caption": parsed.get("series_caption", ""),
                    "reason": parsed.get("reason", "No reason provided"),
                    "confidence": parsed.get("confidence", 0.0)
                }
                
                # Validate and enhance series_caption if it's a valid series
                if result["is_series"] and result["series_caption"]:
                    caption = result["series_caption"].strip()
                    
                    # Ensure caption includes sequence/series terminology
                    sequence_terms = [
                        "sequence of", "series of", "photo session", "consecutive shots", 
                        "multiple frames", "progression of"
                    ]
                    
                    has_sequence_term = any(term in caption.lower() for term in sequence_terms)
                    
                    if not has_sequence_term:
                        # Add a sequence term if missing
                        if caption.lower().startswith(("woman", "man", "person", "model", "influencer")):
                            caption = f"sequence of photos showing {caption}"
                        else:
                            caption = f"photo session capturing {caption}"
                        
                        result["series_caption"] = caption
                
                return result
            else:
                # If no JSON found, return error response
                return {
                    "is_series": False,
                    "images": [],
                    "excluded_images": [],
                    "series_caption": "",
                    "reason": "Could not find JSON in Gemini response",
                    "confidence": 0.0
                }
        except json.JSONDecodeError as e:
            # If JSON parsing fails, return error response
            return {
                "is_series": False,
                "images": [],
                "excluded_images": [],
                "series_caption": "",
                "reason": f"JSON parsing error: {str(e)}",
                "confidence": 0.0
            }
    
    def save_series_to_db(self, base_name: str, directory: str, image_paths: List[str], 
                         raw_response: str, parsed_response: Dict):
        """
        Save series information to the database.
        
        Args:
            base_name (str): Base name of the series.
            directory (str): Directory containing the series.
            image_paths (List[str]): Paths to images in the series.
            raw_response (str): Raw response from Gemini.
            parsed_response (Dict): Parsed JSON response from Gemini.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract thinking data
        thinking_summary = parsed_response.get("thinking_summary", "")
        thinking_tokens = parsed_response.get("thinking_tokens", 0)
        
        # Insert series information
        is_series = parsed_response.get("is_series", False)
        series_caption = parsed_response.get("series_caption", "")
        cursor.execute('''
            INSERT INTO series (base_name, directory, is_series, gemini_raw_response, gemini_parsed_response, 
                              series_caption, image_count, thinking_summary, thinking_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (base_name, directory, is_series, raw_response, json.dumps(parsed_response), 
              series_caption, len(image_paths), thinking_summary, thinking_tokens))
        
        series_id = cursor.lastrowid
        
        # Insert image information if it's a valid series
        if is_series and "images" in parsed_response:
            for image_info in parsed_response["images"]:
                image_path = image_info.get("path", "")
                order = image_info.get("order", 0)
                
                cursor.execute('''
                    INSERT INTO series_images (series_id, image_path, order_in_series)
                    VALUES (?, ?, ?)
                ''', (series_id, image_path, order))
        
        conn.commit()
        conn.close()
    
    def log_analysis(self, directory: str, total_images: int, total_series: int):
        """
        Log analysis results to the database.
        
        Args:
            directory (str): Directory that was analyzed.
            total_images (int): Total number of images processed.
            total_series (int): Total number of series found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analysis_log (directory, total_images, total_series)
            VALUES (?, ?, ?)
        ''', (directory, total_images, total_series))
        
        conn.commit()
        conn.close()

def find_image_series(directory: str) -> Dict[str, List[str]]:
    """
    Find image series in a directory based on Instagram filename patterns.
    
    Instagram filename pattern:
    YYYY_MM_DD_HH_MM_SS_usernameID_caption_XX.jpg
    
    Args:
        directory (str): Directory to scan for images.
        
    Returns:
        Dict[str, List[str]]: Dictionary mapping base names to lists of image paths.
    """
    # Get all image files in directory and subdirectories
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
    image_paths = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(image_extensions):
                image_paths.append(os.path.join(root, file))
    
    # Group images by base name (everything except the number suffix)
    series_dict = defaultdict(list)
    
    for path in image_paths:
        filename = os.path.basename(path)
        
        # Handle Instagram naming patterns by extracting meaningful base names
        # Pattern examples:
        # 2025_08_28_15_09_21_unfashDN5zem3DKwP______________04.jpg
        # 2025_08_28_15_16_56_jenny.lbxDN50WMMDLFf_vienna_has_my_heart__vienna__dump__wien_12.jpg
        
        # Try to extract base pattern before unique ID and number
        base_name = None
        
        # Pattern 1: DateTime_usernameDNxxxxx_____number.jpg
        match1 = re.match(r'(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_\w+?)DN\w+(__+)(\d+)\.(.+)', filename)
        if match1:
            base_name = match1.group(1) + "DN_series"  # Group by username prefix
        
        # Pattern 2: DateTime_username.xxxDNxxxxxx_caption_number.jpg  
        match2 = re.match(r'(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_[\w.]+?)DN\w+(_[^_]+(?:__[^_]+)*?)_(\d+)\.(.+)', filename)
        if match2:
            base_name = match2.group(1) + "DN_" + match2.group(2)  # Group by username + caption
        
        # Pattern 3: Generic fallback - everything before last _number
        if not base_name:
            match3 = re.match(r'(.+)_(\d+)\.(.+)', filename)
            if match3:
                base_name = match3.group(1)
        
        if base_name:
            series_dict[base_name].append(path)
        else:
            # No number pattern found, use whole filename without extension
            name_without_ext = '.'.join(filename.split('.')[:-1])
            series_dict[name_without_ext].append(path)
    
    # Filter out single images (not series)
    series_dict = {k: v for k, v in series_dict.items() if len(v) > 1}
    
    # Sort images within each series by their numeric suffix for logical ordering
    for base_name, image_paths in series_dict.items():
        def extract_number(path):
            filename = os.path.basename(path)
            # Extract the last number from filename (e.g., "_02.jpg" -> 2)
            name_without_ext = filename.rsplit('.', 1)[0]
            parts = name_without_ext.split('_')
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    return int(parts[i])
            return 0  # fallback for no number found
        
        # Sort by numeric suffix
        series_dict[base_name] = sorted(image_paths, key=extract_number)
    
    return series_dict

def main():
    parser = argparse.ArgumentParser(description="Detect photo series for video generation training using Gemini 2.5 Flash")
    parser.add_argument("directory", help="Root directory containing images to analyze")
    parser.add_argument("--db-path", default="photo_series.db",
                        help="Path to SQLite database file (default: photo_series.db)")
    parser.add_argument("--api-key", 
                        help="Google AI API key for Gemini access (or set GEMINI_API_KEY env var)")
    parser.add_argument("--test-limit", type=int, default=0,
                        help="For testing: limit to N series (0 = no limit)")
    parser.add_argument("--sort-by-size", action="store_true", default=True,
                        help="Sort series by image count (largest first) - DEFAULT")
    parser.add_argument("--no-sort", dest="sort_by_size", action="store_false",
                        help="Disable sorting, process in random order")
    
    args = parser.parse_args()
    
    # Handle API key from multiple sources
    api_key = args.api_key
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY')
        if not api_key:
            print("❌ Error: Gemini API key is required!")
            print("   Use --api-key YOUR_KEY or set GEMINI_API_KEY environment variable")
            return
    
    # Check if directory exists
    if not os.path.isdir(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist.")
        return
    
    print(f"Scanning directory '{args.directory}' for image series...")
    
    # Find image series
    series_dict = find_image_series(args.directory)
    
    if not series_dict:
        print("No image series found.")
        return
    
    # Sort series by number of images (largest first) if requested
    if args.sort_by_size:
        sorted_series = sorted(series_dict.items(), key=lambda x: len(x[1]), reverse=True)
        print(f"📊 Sorting {len(sorted_series)} series by image count (largest first)")
    else:
        sorted_series = list(series_dict.items())
    
    # Limit number of series for testing if specified
    if args.test_limit and args.test_limit > 0:
        sorted_series = sorted_series[:args.test_limit]
        print(f"🧪 Testing mode: Processing only first {args.test_limit} series")
    
    print(f"Found {len(sorted_series)} series to process. Analyzing with Gemini...")
    
    # Show preview
    print("\n📋 Series Preview:")
    for i, (base_name, image_paths) in enumerate(sorted_series[:5], 1):
        print(f"   {i}. {base_name[:60]}... ({len(image_paths)} images)")
    if len(sorted_series) > 5:
        print(f"   ... and {len(sorted_series) - 5} more")
    
    # Initialize detector
    detector = PhotoSeriesDetector(db_path=args.db_path, api_key=api_key)
    
    total_images = 0
    total_series = 0
    
    # Process each series
    for i, (base_name, image_paths) in enumerate(sorted_series, 1):
        print(f"\n[{i}/{len(sorted_series)}] Processing series '{base_name[:50]}...' with {len(image_paths)} images...")
        
        # Get directory of first image as representative directory
        directory = os.path.dirname(image_paths[0])
        
        # Analyze series with Gemini
        raw_response, parsed_response = detector.analyze_series_with_gemini(image_paths)
        
        # Check if it's a valid series
        is_series = parsed_response.get("is_series", False)
        
        # Save to database
        detector.save_series_to_db(base_name, directory, image_paths, raw_response, parsed_response)
        
        total_images += len(image_paths)
        if is_series:
            total_series += 1
        
        print(f"  Series detected: {is_series}")
        if "reason" in parsed_response:
            print(f"  Reason: {parsed_response['reason']}")
        if "series_caption" in parsed_response and parsed_response["series_caption"]:
            print(f"  Caption: {parsed_response['series_caption']}")
    
    # Log analysis
    detector.log_analysis(args.directory, total_images, total_series)
    
    # Print summary
    print("\nAnalysis Results:")
    print(f"Total series processed: {len(sorted_series)}")
    print(f"Confirmed series: {total_series}")
    print(f"Total images analyzed: {total_images}")
    print(f"Results saved to database: {args.db_path}")

if __name__ == "__main__":
    main()