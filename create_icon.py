"""
Script to create a simple application icon
Run this once to generate the icon.ico file
"""

from PIL import Image, ImageDraw, ImageFont

def create_icon():
    """Create a simple YAVDownloader icon"""
    # Create a 256x256 image with a gradient background
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a rounded rectangle background (blue gradient)
    for i in range(size):
        # Create gradient from light blue to dark blue
        color_value = int(33 + (200 - 33) * (i / size))
        draw.rectangle([(0, i), (size, i+1)], fill=(33, 150, 243, 255))
    
    # Draw a rounded rectangle
    margin = 20
    draw.rounded_rectangle(
        [(margin, margin), (size-margin, size-margin)],
        radius=30,
        fill=(33, 150, 243, 255),
        outline=(255, 255, 255, 255),
        width=8
    )
    
    # Draw a download arrow symbol
    arrow_color = (255, 255, 255, 255)
    center_x = size // 2
    center_y = size // 2
    
    # Arrow shaft
    shaft_width = 30
    shaft_height = 80
    draw.rectangle(
        [(center_x - shaft_width//2, center_y - shaft_height//2),
         (center_x + shaft_width//2, center_y + shaft_height//2 + 20)],
        fill=arrow_color
    )
    
    # Arrow head (triangle)
    arrow_head_size = 60
    arrow_points = [
        (center_x, center_y + shaft_height//2 + 50),  # Bottom point
        (center_x - arrow_head_size, center_y + shaft_height//2 - 10),  # Left point
        (center_x + arrow_head_size, center_y + shaft_height//2 - 10),  # Right point
    ]
    draw.polygon(arrow_points, fill=arrow_color)
    
    # Draw "YAV" text at the top
    try:
        # Try to use a nice font, fall back to default if not available
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    text = "YAVD"
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (size - text_width) // 2
    text_y = 40
    
    # Draw text with shadow for better visibility
    draw.text((text_x + 2, text_y + 2), text, fill=(0, 0, 0, 128), font=font)
    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
    
    # Save as ICO file with multiple sizes
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save('icon.ico', format='ICO', sizes=icon_sizes)
    print("✓ Icon created successfully: icon.ico")
    
    # Also save as PNG for preview
    img.save('icon.png', format='PNG')
    print("✓ Preview created: icon.png")

if __name__ == "__main__":
    try:
        create_icon()
    except Exception as e:
        print(f"Error creating icon: {e}")
        print("Make sure Pillow is installed: pip install pillow")

