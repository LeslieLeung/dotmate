"""Font manager for dynamic font discovery and loading."""

import os
import platform
from typing import Dict, List, Optional, Union, Tuple
from PIL import ImageFont


class FontManager:
    """Manages dynamic font discovery and loading across different platforms."""

    def __init__(self) -> None:
        self._system_fonts: Optional[Dict[str, List[str]]] = None
        self._font_cache: Dict[Tuple, Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]] = {}

    def _find_system_fonts(self) -> Dict[str, List[str]]:
        """Find available fonts on the system, categorized by priority."""
        priority_font_keywords = ['sourcehansanssc', 'sourcehansc', 'noto']
        chinese_font_keywords = [
            'ping', 'fang', 'hiragino', 'gb', 'heiti', 'song', 'kai',
            'wqy', 'microhei', 'zenhei', 'msyh', 'yahei', 'simsun', 'simhei'
        ]
        english_font_keywords = ['helvetica', 'arial', 'dejavu', 'liberation']

        # Local font resource directory has highest priority
        local_font_dir = os.path.join(os.path.dirname(__file__), 'resource')
        font_dirs = [local_font_dir] if os.path.exists(local_font_dir) else []

        # Add system font directories based on platform
        system = platform.system().lower()
        if system == 'darwin':
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

        fonts: Dict[str, List[str]] = {'priority': [], 'chinese': [], 'english': []}

        # Search font directories recursively
        for font_dir in font_dirs:
            if not os.path.exists(font_dir):
                continue

            for root, _, files in os.walk(font_dir):
                for file in files:
                    if file.lower().endswith(('.ttf', '.ttc', '.otf')):
                        font_path = os.path.join(root, file)
                        file_lower = file.lower()

                        # Categorize fonts by priority
                        if any(keyword in file_lower for keyword in priority_font_keywords):
                            fonts['priority'].append(font_path)
                        elif any(keyword in file_lower for keyword in chinese_font_keywords):
                            fonts['chinese'].append(font_path)
                        elif any(keyword in file_lower for keyword in english_font_keywords):
                            fonts['english'].append(font_path)

        return fonts

    def get_font(
        self, size: int, font_name: Optional[str] = None, font_weight: Optional[int] = None
    ) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Get font with specified parameters.

        Args:
            size: Font size
            font_name: Optional specific font name to load from resource directory
            font_weight: Optional weight for variable fonts (100-900)

        Returns:
            Font object ready to use
        """
        # Create cache key with all parameters
        cache_key = (size, font_name, font_weight)

        # Check cache first
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # Discover fonts if not done already
        if self._system_fonts is None:
            self._system_fonts = self._find_system_fonts()

        # Load font based on whether a specific font is requested
        if font_name:
            font = self._load_specific_font(font_name, size)
        else:
            font = self._load_best_font(size)

        # Apply variable font weight if specified and supported
        if font_weight and hasattr(font, "set_variation_by_axes"):
            try:
                font.set_variation_by_axes([font_weight])
            except (AttributeError, OSError, ValueError):
                pass

        # Cache the font
        self._font_cache[cache_key] = font
        return font

    def _load_best_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Load the best available font with fallback chain."""
        # 1. Try local SourceHanSansSC-VF.otf first
        local_font_path = os.path.join(os.path.dirname(__file__), 'resource', 'SourceHanSansSC-VF.otf')
        if os.path.exists(local_font_path):
            try:
                return ImageFont.truetype(local_font_path, size)
            except (OSError, IOError):
                pass

        if self._system_fonts:
            # 2. Priority fonts (SourceHanSans, Noto)
            for font_path in self._system_fonts['priority']:
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

            # 3. Chinese fonts for Unicode support
            for font_path in self._system_fonts['chinese'][:3]:
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

            # 4. English fonts as fallback
            for font_path in self._system_fonts['english'][:2]:
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue

        # 5. Try common font names by path
        common_fonts = ['SourceHanSansSC-Regular.ttf', 'NotoSansCJKsc-Regular.ttf', 'arial.ttf']
        for font_name in common_fonts:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue

        # 6. Last resort: PIL default font
        return ImageFont.load_default()

    def _load_specific_font(self, font_name: str, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Load a specific font by name from resource directory.

        Args:
            font_name: Font name (without extension) or full filename
            size: Font size

        Returns:
            Font object, falls back to best available font if not found
        """
        local_font_dir = os.path.join(os.path.dirname(__file__), 'resource')

        # Try exact match with common extensions
        for ext in ['.ttf', '.otf', '.ttc']:
            local_font_path = os.path.join(local_font_dir, f"{font_name}{ext}")
            if os.path.exists(local_font_path):
                try:
                    return ImageFont.truetype(local_font_path, size)
                except (OSError, IOError):
                    pass

        # Search in resource directory for partial matches
        if os.path.exists(local_font_dir):
            for file in os.listdir(local_font_dir):
                if file.lower().endswith(('.ttf', '.otf', '.ttc')):
                    file_base = os.path.splitext(file)[0].lower()
                    if font_name.lower() in file_base or file_base in font_name.lower():
                        try:
                            font_path = os.path.join(local_font_dir, file)
                            return ImageFont.truetype(font_path, size)
                        except (OSError, IOError):
                            continue

        # Fallback to best available font instead of default
        return self._load_best_font(size)

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