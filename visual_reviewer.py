#!/usr/bin/env python3
"""
Visual Image Series Reviewer for Photo Series Detector

This tool provides a visual interface to review and modify AI-detected photo series,
allowing you to edit inclusion/exclusion status, reorder images, and manage series.

Usage:
    python visual_reviewer.py --db-path photo_series.db
    
Controls:
    ← → Arrow keys: Navigate between series
    ↑ ↓ Arrow keys: Navigate between images in current series  
    ESC/Q: Quit (with save prompt if changes exist)
    I: Show image info
    SPACE/T: Toggle current image inclusion
    S: Save all changes to database
    R: Reset changes for current series
    DELETE: Delete current series completely
    
Mouse Controls:
    Click image: Toggle inclusion status (red/green)
    Ctrl+Click+Drag: Reorder images (for included images only)
    
Buttons:
    🗑️ Delete Series: Remove series from database permanently
    💾 Save Changes: Save all modifications to database  
    ↺ Reset Changes: Reset current series to original state
"""

import sqlite3
import json
import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    print("❌ Required packages missing. Installing...")
    print("Please run: pip install pillow")
    sys.exit(1)

class SeriesViewer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.series_data = []
        self.current_series_idx = 0
        self.current_image_idx = 0
        self.modified_series = set()  # Track which series have been modified
        
        # Load data from database
        self.load_series_data()
        
        # Initialize GUI
        self.root = tk.Tk()
        self.root.title("Photo Series Visual Reviewer")
        self.root.geometry("1200x800")
        self.root.configure(bg='#2b2b2b')
        
        # Bind keyboard events
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.focus_set()
        
        self.setup_gui()
        self.update_display()
    
    def load_series_data(self):
        """Load all series data from database"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database file not found: {self.db_path}")
            sys.exit(1)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all valid series with their details
        cursor.execute("""
            SELECT s.id, s.base_name, s.directory, s.is_series, 
                   s.gemini_parsed_response, s.series_caption, s.image_count
            FROM series s
            WHERE s.is_series = 1
            ORDER BY s.image_count DESC
        """)
        
        for row in cursor.fetchall():
            series_id, base_name, directory, is_series, parsed_json, caption, image_count = row
            
            try:
                parsed_response = json.loads(parsed_json)
                
                # Get all original images in the series
                original_images = self.get_original_images(directory, base_name)
                
                # Get included images with order
                included_images = parsed_response.get("images", [])
                excluded_images = parsed_response.get("excluded_images", [])
                confidence = parsed_response.get("confidence", 0.0)
                reason = parsed_response.get("reason", "")
                
                series_info = {
                    'id': series_id,
                    'base_name': base_name,
                    'directory': directory,
                    'caption': caption,
                    'confidence': confidence,
                    'reason': reason,
                    'original_images': original_images,
                    'included_images': included_images,
                    'excluded_images': excluded_images,
                    'total_count': len(original_images)
                }
                
                # Debug output
                print(f"   Series: {base_name}")
                print(f"   Directory: {directory}")
                print(f"   Original images: {len(original_images)}")
                print(f"   AI included: {[img['path'] for img in included_images]}")
                if original_images:
                    print(f"   Sample actual file: {os.path.basename(original_images[0])}")
                
                self.series_data.append(series_info)
                
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse JSON for series: {base_name}")
                continue
        
        conn.close()
        
        if not self.series_data:
            print("❌ No valid series found in database")
            sys.exit(1)
        
        print(f"✅ Loaded {len(self.series_data)} series for review")
    
    def get_original_images(self, directory: str, base_name: str) -> List[str]:
        """Get all original images for a series by scanning directory"""
        # Handle relative paths
        if directory.startswith('./'):
            directory = os.path.abspath(directory)
        
        if not os.path.exists(directory):
            print(f"   Warning: Directory does not exist: {directory}")
            return []
        
        images = []
        # Extract the actual base pattern from the series name
        # Remove trailing ... and get the meaningful part
        base_pattern = base_name.replace('...', '').strip()
        
        # For the first series, we need to extract just the timestamp + username part
        # Example: "2025_08_28_15_24_04_nakedcphDN__m" -> find common prefix
        
        print(f"   Searching in: {directory}")
        print(f"   Full base_name: {base_name}")
        print(f"   Pattern: {base_pattern}")
        
        # Try different patterns to find matching files
        patterns_to_try = []
        
        # Pattern 1: Use the base pattern as-is
        patterns_to_try.append(base_pattern)
        
        # Pattern 2: Extract timestamp + username (before DN)
        if 'DN' in base_pattern:
            timestamp_user = base_pattern.split('DN')[0] + 'DN'
            patterns_to_try.append(timestamp_user)
        
        # Pattern 3: Just the timestamp part (first 19 chars for YYYY_MM_DD_HH_MM_SS)
        if len(base_pattern) >= 19:
            timestamp = base_pattern[:19]
            patterns_to_try.append(timestamp)
        
        for pattern in patterns_to_try:
            print(f"   Trying pattern: {pattern}")
            for file in os.listdir(directory):
                if (file.lower().endswith(('.jpg', '.jpeg', '.png')) and 
                    pattern in file):
                    full_path = os.path.join(directory, file)
                    if full_path not in images:  # Avoid duplicates
                        images.append(full_path)
            
            if images:
                print(f"   Found {len(images)} files with pattern: {pattern}")
                break
                
        print(f"   Total found: {len(images)} matching files")
        if images:
            print(f"   Sample: {os.path.basename(images[0])}")
        
        # Sort by filename number to ensure consistent ordering
        def extract_number(path):
            filename = os.path.basename(path)
            name_without_ext = filename.rsplit('.', 1)[0]
            parts = name_without_ext.split('_')
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    return int(parts[i])
            return 0
        
        return sorted(images, key=extract_number)
    
    def delete_current_series(self):
        """Delete the current series from the database"""
        if not self.series_data:
            return
        
        current_series = self.series_data[self.current_series_idx]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Delete Series", 
            f"Are you sure you want to delete the series:\n\n"
            f"'{current_series['base_name']}'\n\n"
            f"This will permanently remove it from the database and cannot be undone.",
            icon='warning'
        )
        
        if result:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Delete the series from database
                cursor.execute("DELETE FROM series WHERE id = ?", (current_series['id'],))
                conn.commit()
                conn.close()
                
                # Remove from local data
                self.series_data.pop(self.current_series_idx)
                self.modified_series.discard(self.current_series_idx)
                
                # Adjust current index
                if self.current_series_idx >= len(self.series_data) and self.series_data:
                    self.current_series_idx = len(self.series_data) - 1
                elif not self.series_data:
                    self.current_series_idx = 0
                
                self.current_image_idx = 0
                
                if self.series_data:
                    self.update_display()
                    messagebox.showinfo("Deleted", "Series deleted successfully!")
                else:
                    messagebox.showinfo("No More Series", "No more series to review.")
                    self.root.quit()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete series: {str(e)}")
    
    def toggle_image_inclusion(self, img_idx: int):
        """Toggle whether an image is included in the series"""
        if not self.series_data:
            return
        
        current_series = self.series_data[self.current_series_idx]
        images = self.get_current_images()
        
        if 0 <= img_idx < len(images):
            img_path, current_status = images[img_idx]
            filename = os.path.basename(img_path)
            
            # Mark this series as modified
            self.modified_series.add(self.current_series_idx)
            
            if current_status:  # Currently included, remove it
                # Remove from included images
                current_series['included_images'] = [
                    img for img in current_series['included_images'] 
                    if img['path'] != filename
                ]
                # Add to excluded images if not already there
                if filename not in current_series['excluded_images']:
                    current_series['excluded_images'].append(filename)
                    
            else:  # Currently excluded, include it
                # Remove from excluded images
                current_series['excluded_images'] = [
                    img for img in current_series['excluded_images'] 
                    if img != filename
                ]
                # Add to included images with next order number
                max_order = max([img.get('order', 0) for img in current_series['included_images']], default=0)
                current_series['included_images'].append({
                    'path': filename,
                    'order': max_order + 1
                })
            
            self.update_display()
    
    def move_image(self, from_idx: int, to_idx: int):
        """Move an image from one position to another in the included list"""
        if not self.series_data:
            return
        
        current_series = self.series_data[self.current_series_idx]
        images = self.get_current_images()
        
        if not (0 <= from_idx < len(images) and 0 <= to_idx < len(images)):
            return
        
        from_img_path, from_status = images[from_idx]
        to_img_path, to_status = images[to_idx]
        
        # Only allow reordering among included images
        if not (from_status and to_status):
            return
        
        from_filename = os.path.basename(from_img_path)
        to_filename = os.path.basename(to_img_path)
        
        # Mark this series as modified
        self.modified_series.add(self.current_series_idx)
        
        # Find the images in the included list
        included_images = current_series['included_images']
        from_img = None
        to_img = None
        
        for img in included_images:
            if img['path'] == from_filename:
                from_img = img
            elif img['path'] == to_filename:
                to_img = img
        
        if from_img and to_img:
            # Swap their order values
            from_img['order'], to_img['order'] = to_img['order'], from_img['order']
            self.update_display()
    
    def save_changes(self):
        """Save all changes back to the database"""
        if not self.modified_series:
            messagebox.showinfo("No Changes", "No changes to save.")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            saved_count = 0
            for series_idx in self.modified_series:
                if series_idx < len(self.series_data):
                    series = self.series_data[series_idx]
                    
                    # Reconstruct the parsed response
                    parsed_response = {
                        "images": series['included_images'],
                        "excluded_images": series['excluded_images'],
                        "confidence": series['confidence'],
                        "reason": series['reason']
                    }
                    
                    # Update the database
                    cursor.execute("""
                        UPDATE series 
                        SET gemini_parsed_response = ?, image_count = ?
                        WHERE id = ?
                    """, (
                        json.dumps(parsed_response),
                        len(series['included_images']),
                        series['id']
                    ))
                    saved_count += 1
            
            conn.commit()
            conn.close()
            
            # Clear modified series
            self.modified_series.clear()
            
            messagebox.showinfo("Saved", f"Successfully saved changes to {saved_count} series!")
            self.update_display()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {str(e)}")
    
    def reset_changes(self):
        """Reset changes for the current series"""
        if self.current_series_idx not in self.modified_series:
            messagebox.showinfo("No Changes", "No changes to reset for this series.")
            return
        
        result = messagebox.askyesno(
            "Reset Changes", 
            "Are you sure you want to reset all changes for this series?\n\n"
            "This will reload the original data from the database.",
            icon='warning'
        )
        
        if result:
            # Reload this series from database
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                current_series = self.series_data[self.current_series_idx]
                cursor.execute("""
                    SELECT gemini_parsed_response 
                    FROM series 
                    WHERE id = ?
                """, (current_series['id'],))
                
                row = cursor.fetchone()
                if row:
                    parsed_response = json.loads(row[0])
                    
                    # Reset the series data
                    current_series['included_images'] = parsed_response.get("images", [])
                    current_series['excluded_images'] = parsed_response.get("excluded_images", [])
                    current_series['confidence'] = parsed_response.get("confidence", 0.0)
                    current_series['reason'] = parsed_response.get("reason", "")
                    
                    # Remove from modified set
                    self.modified_series.discard(self.current_series_idx)
                    
                    self.update_display()
                    messagebox.showinfo("Reset", "Series changes have been reset!")
                
                conn.close()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset changes: {str(e)}")
    
    def on_drag(self, event):
        """Handle drag motion for reordering"""
        if not self.dragging:
            return
        
        # Visual feedback could be added here
        # For now, just track the movement
        pass
    
    def on_drag_end(self, event):
        """Handle end of drag operation"""
        if not self.dragging:
            return
        
        self.dragging = False
        
        # Calculate drop position
        x = self.canvas.canvasx(event.x)
        drop_idx = self.get_image_at_position(x)
        
        if drop_idx is not None and drop_idx != self.drag_image_idx:
            print(f"Moving image from {self.drag_image_idx} to {drop_idx}")
            self.move_image(self.drag_image_idx, drop_idx)
        
        self.drag_image_idx = None
    
    def get_image_at_position(self, x: float) -> Optional[int]:
        """Get the image index at a given x position"""
        for start_x, end_x, idx in self.image_positions:
            if start_x <= x <= end_x:
                return idx
        return None
    
    def setup_gui(self):
        """Setup the GUI layout"""
        # Top frame for series info
        self.info_frame = tk.Frame(self.root, bg='#2b2b2b', height=160)
        self.info_frame.pack(fill='x', padx=10, pady=5)
        self.info_frame.pack_propagate(False)
        
        # Series title
        self.title_label = tk.Label(self.info_frame, text="", font=('Arial', 14, 'bold'), 
                                   fg='white', bg='#2b2b2b', wraplength=1100)
        self.title_label.pack(pady=5)
        
        # Series stats
        self.stats_label = tk.Label(self.info_frame, text="", font=('Arial', 10), 
                                   fg='#cccccc', bg='#2b2b2b')
        self.stats_label.pack()
        
        # Caption
        self.caption_label = tk.Label(self.info_frame, text="", font=('Arial', 11, 'italic'), 
                                     fg='#4CAF50', bg='#2b2b2b', wraplength=1100)
        self.caption_label.pack(pady=2)
        
        # Button frame for actions
        self.button_frame = tk.Frame(self.info_frame, bg='#2b2b2b')
        self.button_frame.pack(pady=5)
        
        # Delete series button
        self.delete_btn = tk.Button(self.button_frame, text="🗑️ Delete Series", 
                                   command=self.delete_current_series,
                                   bg='#F44336', fg='white', font=('Arial', 10, 'bold'),
                                   padx=10, pady=5)
        self.delete_btn.pack(side='left', padx=5)
        
        # Save changes button
        self.save_btn = tk.Button(self.button_frame, text="💾 Save Changes", 
                                 command=self.save_changes,
                                 bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'),
                                 padx=10, pady=5)
        self.save_btn.pack(side='left', padx=5)
        
        # Reset changes button
        self.reset_btn = tk.Button(self.button_frame, text="↺ Reset Changes", 
                                  command=self.reset_changes,
                                  bg='#FF9800', fg='white', font=('Arial', 10, 'bold'),
                                  padx=10, pady=5)
        self.reset_btn.pack(side='left', padx=5)
        
        # Controls info
        self.controls_label = tk.Label(self.info_frame, 
                                      text="← → Series | ↑ ↓ Images | Click to Toggle | Ctrl+Drag to Reorder | Del Delete | S Save | R Reset | ESC Quit", 
                                      font=('Arial', 9), fg='#888888', bg='#2b2b2b')
        self.controls_label.pack(pady=2)
        
        # Main image frame
        self.image_frame = tk.Frame(self.root, bg='#2b2b2b')
        self.image_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Image canvas with scrollbar
        self.canvas = tk.Canvas(self.image_frame, bg='#1e1e1e', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.image_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="top", fill="both", expand=True)
        self.scrollbar.pack(side="bottom", fill="x")
        
        # Variables for drag and drop
        self.dragging = False
        self.drag_start_x = 0
        self.drag_image_idx = None
        self.image_positions = []  # Store image positions for drag/drop
        
        # Bind canvas events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
    
    def add_border_to_image(self, img: Image.Image, is_included: bool, is_selected: bool = False) -> Image.Image:
        """Add colored border to image based on inclusion status"""
        # Create a copy of the image
        bordered_img = img.copy()
        draw = ImageDraw.Draw(bordered_img)
        
        width, height = bordered_img.size
        border_width = 8 if is_selected else 4
        
        # Choose color based on status
        if is_included:
            color = '#00FF00' if is_selected else '#4CAF50'  # Green
        else:
            color = '#FF0000' if is_selected else '#F44336'  # Red
        
        # Draw border
        for i in range(border_width):
            draw.rectangle([i, i, width-1-i, height-1-i], outline=color, width=1)
        
        return bordered_img
    
    def update_display(self):
        """Update the display with current series"""
        if not self.series_data:
            return
        
        current_series = self.series_data[self.current_series_idx]
        
        # Update info labels
        title = f"[{self.current_series_idx + 1}/{len(self.series_data)}] {current_series['base_name']}"
        if self.current_series_idx in self.modified_series:
            title += " 🔄 MODIFIED"
        self.title_label.config(text=title)
        
        included_count = len(current_series['included_images'])
        total_count = current_series['total_count']
        confidence = current_series['confidence']
        
        stats = f"✅ {included_count}/{total_count} images included | Confidence: {confidence:.1%}"
        if self.modified_series:
            stats += f" | 🔄 {len(self.modified_series)} series modified"
        self.stats_label.config(text=stats)
        
        caption = f"🎬 \"{current_series['caption']}\""
        self.caption_label.config(text=caption)
        
        # Clear canvas
        self.canvas.delete("all")
        # Clear image references to prevent memory leaks
        self.canvas.image_refs = []
        self.image_positions = []  # Reset image positions
        
        # Display images horizontally
        x_offset = 10
        max_height = 320  # Reduced by ~20% (was 400, now 320)
        
        # Get original images and sort them by filename number
        actual_images = current_series['original_images']
        
        # Sort by filename number for reference
        def extract_number(path):
            filename = os.path.basename(path)
            name_without_ext = filename.rsplit('.', 1)[0]
            parts = name_without_ext.split('_')
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    return int(parts[i])
            return 0
        
        # Create AI order mapping using full filenames
        ai_order_map = {}
        for img_info in current_series['included_images']:
            ai_filename = img_info['path']
            ai_order = img_info.get('order', 0)
            ai_order_map[ai_filename] = ai_order
        
        # Get set of included filenames
        included_filenames = {img['path'] for img in current_series['included_images']}
        
        # Create display order: AI-selected images in AI order first, then excluded images in filename order
        display_images = []
        
        # First, add included images sorted by AI order
        included_images_with_order = []
        for img_path in actual_images:
            filename = os.path.basename(img_path)
            if filename in included_filenames:
                ai_order = ai_order_map.get(filename, 0)
                included_images_with_order.append((img_path, ai_order, True))
        
        # Sort by AI order
        included_images_with_order.sort(key=lambda x: x[1])
        display_images.extend(included_images_with_order)
        
        # Then, add excluded images sorted by filename number
        excluded_images = []
        for img_path in actual_images:
            filename = os.path.basename(img_path)
            if filename not in included_filenames:
                excluded_images.append((img_path, extract_number(img_path), False))
        
        # Sort excluded by filename number
        excluded_images.sort(key=lambda x: x[1])
        display_images.extend(excluded_images)
        
        # Display images in the new order: AI-selected first, then excluded
        for i, (img_path, order_value, is_included) in enumerate(display_images):
            if os.path.exists(img_path):
                try:
                    # Get filename and number
                    filename = os.path.basename(img_path)
                    file_number = extract_number(img_path)
                    
                    # Find AI's intended order for this image if included
                    ai_order = ai_order_map.get(filename, 0) if is_included else 0
                    
                    # Load and resize image (make 15% smaller)
                    img = Image.open(img_path)
                    
                    # Calculate size maintaining aspect ratio
                    width, height = img.size
                    if height > max_height:
                        ratio = max_height / height
                        new_width = int(width * ratio)
                        img = img.resize((new_width, max_height), Image.Resampling.LANCZOS)
                    
                    # Add border
                    is_selected = (i == self.current_image_idx)
                    bordered_img = self.add_border_to_image(img, is_included, is_selected)
                    
                    # Convert to PhotoImage
                    photo = ImageTk.PhotoImage(bordered_img)
                    
                    # Add to canvas (moved down to make room for numbers)
                    item_id = self.canvas.create_image(x_offset, 30, anchor="nw", image=photo)
                    self.canvas.image_refs = getattr(self.canvas, 'image_refs', [])
                    self.canvas.image_refs.append(photo)  # Keep reference
                    
                    # Add clear numbering and status
                    text_color = '#4CAF50' if is_included else '#F44336'
                    if is_selected:
                        text_color = '#FFFF00'  # Yellow for selected
                    
                    # Show original number and AI order
                    status_text = f"#{file_number:02d}"
                    if is_included and ai_order > 0:
                        status_text += f" → AI:{ai_order}"
                    
                    # Add number above image
                    self.canvas.create_text(x_offset + bordered_img.width//2, 
                                          10, 
                                          text=status_text, fill=text_color, 
                                          font=('Arial', 10, 'bold' if is_selected else 'normal'),
                                          anchor="n")
                    
                    # Add filename below image (smaller)
                    short_filename = filename[:25] + "..." if len(filename) > 25 else filename
                    self.canvas.create_text(x_offset + bordered_img.width//2, 
                                          bordered_img.height + 50, 
                                          text=short_filename, fill=text_color, 
                                          font=('Arial', 7),
                                          anchor="n")
                    
                    # Store image info for clicking
                    self.canvas.tag_bind(item_id, "<Button-1>", 
                                       lambda e, idx=i: self.on_image_click(idx, e))
                    
                    # Store position info for drag and drop
                    self.canvas.itemconfig(item_id, tags=f"image_{i}")
                    self.image_positions.append((x_offset, x_offset + bordered_img.width, i))
                    
                    x_offset += bordered_img.width + 10  # Reduced spacing
                    
                except Exception as e:
                    print(f"Error loading image {img_path}: {e}")
        
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Scroll to selected image
        if display_images:
            self.scroll_to_selected()
    
    def scroll_to_selected(self):
        """Scroll canvas to show selected image"""
        bbox = self.canvas.bbox("all")
        if bbox:
            canvas_width = self.canvas.winfo_width()
            total_width = bbox[2] - bbox[0]
            
            if total_width > canvas_width:
                # Calculate scroll position
                selected_pos = self.current_image_idx / len(self.get_current_images())
                scroll_pos = max(0, min(1, selected_pos - 0.2))  # Center with some offset
                self.canvas.xview_moveto(scroll_pos)
    
    def get_current_images(self) -> List[Tuple[str, bool]]:
        """Get list of current images with inclusion status in AI-selected order first, then excluded"""
        if not self.series_data:
            return []
        
        current_series = self.series_data[self.current_series_idx]
        included_filenames = {img['path'] for img in current_series['included_images']}
        
        # Get original images
        actual_images = current_series['original_images']
        
        # Sort by filename number for reference
        def extract_number(path):
            filename = os.path.basename(path)
            name_without_ext = filename.rsplit('.', 1)[0]
            parts = name_without_ext.split('_')
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    return int(parts[i])
            return 0
        
        # Create AI order mapping
        ai_order_map = {}
        for img_info in current_series['included_images']:
            ai_filename = img_info['path']
            ai_order = img_info.get('order', 0)
            ai_order_map[ai_filename] = ai_order
        
        # Create display order: AI-selected images in AI order first, then excluded images
        display_images = []
        
        # First, add included images sorted by AI order
        included_images_with_order = []
        for img_path in actual_images:
            filename = os.path.basename(img_path)
            if filename in included_filenames:
                ai_order = ai_order_map.get(filename, 0)
                included_images_with_order.append((img_path, ai_order))
        
        # Sort by AI order and add to display list
        included_images_with_order.sort(key=lambda x: x[1])
        for img_path, _ in included_images_with_order:
            display_images.append((img_path, True))
        
        # Then, add excluded images sorted by filename number
        excluded_images = []
        for img_path in actual_images:
            filename = os.path.basename(img_path)
            if filename not in included_filenames:
                excluded_images.append((img_path, extract_number(img_path)))
        
        # Sort excluded by filename number and add to display list
        excluded_images.sort(key=lambda x: x[1])
        for img_path, _ in excluded_images:
            display_images.append((img_path, False))
        
        return display_images
    
    def on_image_click(self, idx: int, event):
        """Handle clicking on an image"""
        # Check if this is the start of a drag operation (Ctrl key for reordering)
        if event.state & 0x0004:  # Ctrl key held (more reliable than Shift)
            # Start drag operation for reordering (only for included images)
            images = self.get_current_images()
            if 0 <= idx < len(images):
                img_path, is_included = images[idx]
                if is_included:  # Only allow dragging included images
                    self.dragging = True
                    self.drag_start_x = event.x
                    self.drag_image_idx = idx
                    self.current_image_idx = idx
                    print(f"Started drag for image {idx}")
                else:
                    print("Can only reorder included (green) images")
        else:
            # Toggle inclusion status
            self.toggle_image_inclusion(idx)
            self.current_image_idx = idx
    
    def select_image(self, idx: int):
        """Select an image by index"""
        images = self.get_current_images()
        if 0 <= idx < len(images):
            self.current_image_idx = idx
            self.update_display()
    
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        self.root.focus_set()  # Ensure keyboard focus
    
    def on_canvas_configure(self, event):
        """Handle canvas resize"""
        pass
    
    def on_key_press(self, event):
        """Handle keyboard navigation"""
        if event.keysym == 'Escape' or event.keysym.lower() == 'q':
            # Check for unsaved changes
            if self.modified_series:
                result = messagebox.askyesnocancel(
                    "Unsaved Changes",
                    f"You have unsaved changes in {len(self.modified_series)} series.\n\n"
                    "Do you want to save before exiting?",
                    icon='warning'
                )
                if result is True:  # Yes, save
                    self.save_changes()
                    self.root.quit()
                elif result is False:  # No, don't save
                    self.root.quit()
                # Cancel - do nothing
            else:
                self.root.quit()
        
        elif event.keysym == 'Left':
            # Previous series
            if self.current_series_idx > 0:
                self.current_series_idx -= 1
                self.current_image_idx = 0
                self.update_display()
        
        elif event.keysym == 'Right':
            # Next series
            if self.current_series_idx < len(self.series_data) - 1:
                self.current_series_idx += 1
                self.current_image_idx = 0
                self.update_display()
        
        elif event.keysym == 'Up':
            # Previous image
            images = self.get_current_images()
            if self.current_image_idx > 0:
                self.current_image_idx -= 1
                self.update_display()
        
        elif event.keysym == 'Down':
            # Next image
            images = self.get_current_images()
            if self.current_image_idx < len(images) - 1:
                self.current_image_idx += 1
                self.update_display()
        
        elif event.keysym.lower() == 'i':
            # Show detailed info
            self.show_image_info()
        
        elif event.keysym == 'space':
            # Toggle inclusion of current image
            self.toggle_image_inclusion(self.current_image_idx)
        
        elif event.keysym.lower() == 's':
            # Save changes
            self.save_changes()
        
        elif event.keysym.lower() == 'r':
            # Reset changes
            self.reset_changes()
        
        elif event.keysym == 'Delete':
            # Delete current series
            self.delete_current_series()
        
        elif event.keysym.lower() == 't':
            # Toggle current image inclusion
            self.toggle_image_inclusion(self.current_image_idx)
    
    def show_image_info(self):
        """Show detailed information about current series and image"""
        current_series = self.series_data[self.current_series_idx]
        images = self.get_current_images()
        
        if images:
            current_img_path, is_included = images[self.current_image_idx]
            current_filename = os.path.basename(current_img_path)
            
            info = f"""Series Information:
Base Name: {current_series['base_name']}
Directory: {current_series['directory']}
Caption: {current_series['caption']}
Confidence: {current_series['confidence']:.1%}
Reason: {current_series['reason'][:200]}...

Current Image:
Filename: {current_filename}
Status: {'✅ INCLUDED' if is_included else '❌ EXCLUDED'}
Path: {current_img_path}

Navigation:
← → Navigate series
↑ ↓ Navigate images
ESC Quit"""
            
            messagebox.showinfo("Series Info", info)
    
    def run(self):
        """Start the GUI main loop"""
        if not self.series_data:
            print("❌ No series data to display")
            return
        
        print(f"🎨 Starting visual reviewer with {len(self.series_data)} series...")
        print("Use arrow keys to navigate, ESC to quit")
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='Visual Photo Series Reviewer')
    parser.add_argument('--db-path', default='photo_series.db', 
                       help='Path to SQLite database file (default: photo_series.db)')
    
    args = parser.parse_args()
    
    viewer = SeriesViewer(args.db_path)
    viewer.run()

if __name__ == '__main__':
    main()
