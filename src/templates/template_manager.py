"""Template manager for custom yt-dlp command templates"""

import json
from pathlib import Path
from typing import List, Dict, Optional


class TemplateManager:
    """Manages custom yt-dlp command templates"""
    
    # Default preset templates
    DEFAULT_TEMPLATES = [
        {
            'name': 'Best Quality Video (MP4)',
            'description': 'Download best quality video in MP4 format',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" --merge-output-format mp4',
            'is_preset': True
        },
        {
            'name': 'Best Quality Audio (MP3)',
            'description': 'Extract best quality audio as MP3 with thumbnail',
            'command': '-x --audio-format mp3 --audio-quality 0 --embed-thumbnail',
            'is_preset': True
        },
        {
            'name': '1080p Video',
            'description': 'Download video at 1080p resolution',
            'command': '-f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]" --merge-output-format mp4',
            'is_preset': True
        },
        {
            'name': '720p Video',
            'description': 'Download video at 720p resolution',
            'command': '-f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" --merge-output-format mp4',
            'is_preset': True
        },
        {
            'name': 'Download Playlist',
            'description': 'Download entire playlist',
            'command': '--yes-playlist -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"',
            'is_preset': True
        },
        {
            'name': 'Download Subtitles',
            'description': 'Download video with all available subtitles',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" --write-subs --write-auto-subs --sub-lang en,id --embed-subs',
            'is_preset': True
        },
        {
            'name': 'Audio Only (M4A)',
            'description': 'Download audio only in M4A format',
            'command': '-f "bestaudio[ext=m4a]/bestaudio" --extract-audio --audio-format m4a',
            'is_preset': True
        },
        {
            'name': 'Download Thumbnail',
            'description': 'Download video with embedded thumbnail',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" --embed-thumbnail --merge-output-format mp4',
            'is_preset': True
        },
        {
            'name': 'Download with Metadata',
            'description': 'Download with all metadata embedded',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" --embed-metadata --embed-thumbnail --embed-subs',
            'is_preset': True
        },
        {
            'name': 'Fast Download (No Merge)',
            'description': 'Download fastest available format without merging',
            'command': '-f "best"',
            'is_preset': True
        },
        {
            'name': 'Download Age-Restricted',
            'description': 'Download age-restricted videos (requires cookies)',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" --cookies-from-browser chrome',
            'is_preset': True
        },
        {
            'name': 'Download Live Stream',
            'description': 'Download live stream or wait for it to start',
            'command': '-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best" --wait-for-video 60',
            'is_preset': True
        }
    ]
    
    def __init__(self, config_file: str = ".ytdlp_templates.json"):
        """
        Initialize template manager
        
        Args:
            config_file: Name of the templates file (stored in user's home directory)
        """
        self.config_file = Path.home() / config_file
        self.templates = self._load_templates()
    
    def _load_templates(self) -> List[Dict]:
        """
        Load templates from file
        
        Returns:
            List of template dictionaries
        """
        custom_templates = []
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    custom_templates = json.load(f)
            except Exception:
                custom_templates = []
        
        # Combine presets with custom templates
        return self.DEFAULT_TEMPLATES + custom_templates
    
    def _save_custom_templates(self):
        """Save custom templates to file"""
        # Only save non-preset templates
        custom_templates = [t for t in self.templates if not t.get('is_preset', False)]
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(custom_templates, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def get_all_templates(self) -> List[Dict]:
        """
        Get all templates (presets + custom)
        
        Returns:
            List of all templates
        """
        return self.templates
    
    def get_preset_templates(self) -> List[Dict]:
        """
        Get only preset templates
        
        Returns:
            List of preset templates
        """
        return [t for t in self.templates if t.get('is_preset', False)]
    
    def get_custom_templates(self) -> List[Dict]:
        """
        Get only custom templates
        
        Returns:
            List of custom templates
        """
        return [t for t in self.templates if not t.get('is_preset', False)]
    
    def add_template(self, name: str, description: str, command: str) -> bool:
        """
        Add a new custom template
        
        Args:
            name: Template name
            description: Template description
            command: yt-dlp command arguments
            
        Returns:
            True if added successfully, False if name already exists
        """
        # Check if name already exists
        if any(t['name'] == name for t in self.templates):
            return False
        
        new_template = {
            'name': name,
            'description': description,
            'command': command,
            'is_preset': False
        }
        
        self.templates.append(new_template)
        self._save_custom_templates()
        return True
    
    def update_template(self, old_name: str, name: str, description: str, command: str) -> bool:
        """
        Update an existing custom template
        
        Args:
            old_name: Current template name
            name: New template name
            description: New template description
            command: New yt-dlp command arguments
            
        Returns:
            True if updated successfully, False otherwise
        """
        # Find the template
        for i, template in enumerate(self.templates):
            if template['name'] == old_name and not template.get('is_preset', False):
                # Check if new name conflicts with another template
                if name != old_name and any(t['name'] == name for t in self.templates):
                    return False
                
                self.templates[i] = {
                    'name': name,
                    'description': description,
                    'command': command,
                    'is_preset': False
                }
                self._save_custom_templates()
                return True
        
        return False
    
    def delete_template(self, name: str) -> bool:
        """
        Delete a custom template
        
        Args:
            name: Template name to delete
            
        Returns:
            True if deleted successfully, False if not found or is preset
        """
        for i, template in enumerate(self.templates):
            if template['name'] == name and not template.get('is_preset', False):
                del self.templates[i]
                self._save_custom_templates()
                return True
        
        return False
    
    def get_template(self, name: str) -> Optional[Dict]:
        """
        Get a specific template by name
        
        Args:
            name: Template name
            
        Returns:
            Template dictionary or None if not found
        """
        for template in self.templates:
            if template['name'] == name:
                return template
        
        return None

