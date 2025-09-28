"""Font manager for dynamic font discovery and loading."""

import os
import platform
from typing import Dict, List, Optional, Union
from PIL import ImageFont


class FontManager:
    """Manages dynamic font discovery and loading across different platforms."""

    def __init__(self) -> None:
        self._system_fonts: Optional[Dict[str, List[str]]] = None
        self._font_cache: Dict[int, Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]] = {}

    def _find_system_fonts(self) -> Dict[str, List[str]]:
        """Dynamically find available fonts on the system."""
        # Priority fonts - SourceHanSansSC variants
        priority_font_keywords = ['sourcehansanssc', 'sourcehansc', 'noto']

        chinese_font_keywords = [
            'ping', 'fang', 'hiragino', 'gb', 'heiti', 'song', 'kai',
            'wqy', 'microhei', 'zenhei', 'msyh', 'yahei', 'simsun', 'simhei'
        ]
        english_font_keywords = ['helvetica', 'arial', 'dejavu', 'liberation']

        # Start with local font directory first (highest priority)
        local_font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'font')
        font_dirs = [local_font_dir] if os.path.exists(local_font_dir) else []

        # Add system font directories based on OS
        system = platform.system().lower()
        if system == 'darwin':  # macOS
            font_dirs.extend([
                '/System/Library/Fonts/',
                '/Library/Fonts/',
                '/System/Library/Fonts/Supplemental/',
                os.path.expanduser('~/Library/Fonts/')
            ])
        elif system == 'linux':
            font_dirs.extend([
                '/usr/share/fonts/',
                '/usr/local/share/fonts/',
                '/usr/share/fonts/truetype/',
                os.path.expanduser('~/.fonts/'),
                os.path.expanduser('~/.local/share/fonts/')
            ])
        elif system == 'windows':
            font_dirs.extend([
                'C:/Windows/Fonts/',
                os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts/')
            ])
        else:
            pass  # No additional system directories for unknown OS

        fonts: Dict[str, List[str]] = {'priority': [], 'chinese': [], 'english': []}

        # Recursively search font directories
        for font_dir in font_dirs:
            if not os.path.exists(font_dir):
                continue

            for root, _, files in os.walk(font_dir):
                for file in files:
                    if file.lower().endswith(('.ttf', '.ttc', '.otf')):
                        font_path = os.path.join(root, file)
                        file_lower = file.lower()

                        # Categorize fonts - priority first
                        if any(keyword in file_lower for keyword in priority_font_keywords):
                            fonts['priority'].append(font_path)
                        elif any(keyword in file_lower for keyword in chinese_font_keywords):
                            fonts['chinese'].append(font_path)
                        elif any(keyword in file_lower for keyword in english_font_keywords):
                            fonts['english'].append(font_path)

        return fonts

    def get_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Get font with specified size, trying dynamically discovered fonts."""
        # Check cache first
        if size in self._font_cache:
            return self._font_cache[size]

        # Discover fonts if not done already
        if self._system_fonts is None:
            self._system_fonts = self._find_system_fonts()

        font = self._load_best_font(size)

        # Cache the font
        self._font_cache[size] = font
        return font

    def _load_best_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Load the best available font for the given size."""
        # Highest priority: check for specific SourceHanSansSC-VF.otf in local font directory
        local_font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'font', 'SourceHanSansSC-VF.otf')
        if os.path.exists(local_font_path):
            try:
                # For variable font, set font weight to SemiBold (600) for better readability
                font = ImageFont.truetype(local_font_path, size)
                # Try to set font variation if it's a variable font
                try:
                    # Use numeric weight (600 = SemiBold) for variable font
                    font.set_variation_by_axes([600])  # wght axis value
                except (AttributeError, OSError, ValueError):
                    # If variation setting fails, font will use default weight
                    pass
                return font
            except (OSError, IOError):
                pass

        if self._system_fonts:
            # Second priority: SourceHanSansSC and related high-quality fonts from system
            for font_path in self._system_fonts['priority']:
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

            # Third priority: Other Chinese fonts (for better Unicode support)
            for font_path in self._system_fonts['chinese'][:3]:  # Try first 3 Chinese fonts
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

            # Fourth priority: English fonts as fallback
            for font_path in self._system_fonts['english'][:2]:  # Try first 2 English fonts
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

        # Final fallback: try SourceHanSansSC by common names first
        source_han_fonts = [
            'SourceHanSansSC-Regular.ttf',
            'SourceHanSansSC-Normal.ttf',
            'SourceHanSansSC.ttf',
            'SourceHanSansHC-Regular.ttf',
            'NotoSansCJKsc-Regular.ttf',
            'NotoSansCJK-Regular.ttc'
        ]
        for font_name in source_han_fonts:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue

        # Last resort: try common system font names directly
        common_fonts = ['arial.ttf', 'helvetica.ttf', 'times.ttf']
        for font_name in common_fonts:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue

        # If no TrueType font found, use default
        return ImageFont.load_default()

    def get_available_fonts(self) -> Dict[str, List[str]]:
        """Get dictionary of available fonts categorized by type."""
        if self._system_fonts is None:
            self._system_fonts = self._find_system_fonts()
        return self._system_fonts.copy()

    def clear_cache(self) -> None:
        """Clear the font cache."""
        self._font_cache.clear()

    def is_default_font(self, font: Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]) -> bool:
        """Check if the given font is the default font."""
        # FreeTypeFont instances are TrueType fonts, not default fonts
        if isinstance(font, ImageFont.FreeTypeFont):
            return False

        # Check if it's specifically the default PIL font type
        default_font = ImageFont.load_default()
        return type(font) == type(default_font)