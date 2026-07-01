"""
picture processing tool module
Support pictureofFormat conversion, compression, thumbnail picturegenerate and other functions
"""

import base64
import io

from PIL import ExifTags, Image

from yuxi.utils import logger


class ImageProcessor:
    """Image processing class"""

    # Supported image formats
    SUPPORTED_FORMATS = {"JPEG", "PNG", "WebP", "GIF", "BMP"}

    # Maximum file size (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024

    # Thumbnail size
    THUMBNAIL_SIZE = (200, 200)

    def process_image(self, image_data: bytes, original_filename: str = "") -> dict:
        """
        Handle upload ofpicture

        Args:
            image_data: picturetwo hexadecimal data
            original_filename: original file name

        Returns:
            dict: Dictionary containing processing results
        """
        try:
            # Verify image format
            img_format, _ = self._validate_image_format(image_data)
            if img_format not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Định dạng hình ảnh không được hỗ trợ: {img_format}")

            # Load images
            with Image.open(io.BytesIO(image_data)) as img:
                # Handle EXIF ​​orientation information
                img = self._fix_image_orientation(img)

                # Generate thumbnails
                thumbnail_data = self._generate_thumbnail(img)

                # Compress main image (if needed)
                processed_data, final_format = self._compress_image(img, img_format)

                # Convert to base64
                base64_data = base64.b64encode(processed_data).decode("utf-8")
                base64_thumbnail = base64.b64encode(thumbnail_data).decode("utf-8")

                # Get picture information
                width, height = img.size
                mime_type = f"image/{final_format.lower()}"

                return {
                    "success": True,
                    "image_content": base64_data,
                    "thumbnail_content": base64_thumbnail,
                    "width": width,
                    "height": height,
                    "format": final_format,
                    "mime_type": mime_type,
                    "size_bytes": len(processed_data),
                    "original_filename": original_filename,
                }

        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _validate_image_format(self, image_data: bytes) -> tuple[str, str]:
        """Verify image format and return format information"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return img.format, img.mode
        except Exception as e:
            raise ValueError(f"Định dạng hình ảnh không hợp lệ: {str(e)}")

    def _fix_image_orientation(self, img: Image.Image) -> Image.Image:
        """Correct image orientation based on EXIF ​​information"""
        try:
            if hasattr(img, "_getexif"):
                exif = img._getexif()
                if exif is not None:
                    for tag, value in exif.items():
                        if tag in ExifTags.TAGS and ExifTags.TAGS[tag] == "Orientation":
                            if value == 3:
                                img = img.rotate(180, expand=True)
                            elif value == 6:
                                img = img.rotate(270, expand=True)
                            elif value == 8:
                                img = img.rotate(90, expand=True)
                            break
        except Exception as e:
            logger.warning(f"Failed to correct image orientation, use original orientation: {str(e)}")

        return img

    def _generate_thumbnail(self, img: Image.Image) -> bytes:
        """Generate thumbnails"""
        try:
            thumbnail = self._convert_to_rgb_for_export(img)

            # Generate thumbnails, maintaining aspect ratio
            thumbnail.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Convert to JPEG format
            with io.BytesIO() as output:
                thumbnail.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {str(e)}")
            # If the thumbnail generation fails, a 1x1 transparent image is returned.
            with io.BytesIO() as output:
                empty_img = Image.new("RGB", (1, 1), color="white")
                empty_img.save(output, format="JPEG", quality=85)
                return output.getvalue()

    def _convert_to_rgb_for_export(self, img: Image.Image) -> Image.Image:
        """Convert to RGB, and combine transparent pixels on a white background to prevent hidden colors from becoming visible pixels."""
        if img.mode == "RGB":
            return img.copy()

        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if not has_alpha:
            return img.convert("RGB")

        rgba_img = img.convert("RGBA")
        background = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
        background.alpha_composite(rgba_img)
        return background.convert("RGB")

    def _compress_image(self, img: Image.Image, original_format: str) -> tuple[bytes, str]:
        """
        Compress the picture if it exceeds the size limit

        Args:
            img: PIL Image object
            original_format: original Format

        Returns:
            Tuple[bytes, str]: (Compressed image data, final format)
        """
        processed_img = self._convert_to_rgb_for_export(img)

        # Try to keep the original format, but prefer JPEG (better compression)
        target_format = "JPEG" if original_format != "PNG" else "PNG"

        # Initial quality settings
        quality = 85

        with io.BytesIO() as output:
            # Save first time to check size
            processed_img.save(output, format=target_format, quality=quality, optimize=True)
            compressed_data = output.getvalue()

            # If the file size is appropriate, return directly
            if len(compressed_data) <= self.MAX_FILE_SIZE:
                return compressed_data, target_format

            # If the file is too large, gradually reduce the quality
            while len(compressed_data) > self.MAX_FILE_SIZE and quality > 10:
                quality -= 10
                output.seek(0)
                output.truncate(0)
                processed_img.save(output, format=target_format, quality=quality, optimize=True)
                compressed_data = output.getvalue()

            # If it's still too big with the lowest quality, try reducing the size
            if len(compressed_data) > self.MAX_FILE_SIZE:
                # gradually reduce size
                scale_factor = 0.9
                while len(compressed_data) > self.MAX_FILE_SIZE and scale_factor > 0.3:
                    new_width = int(processed_img.width * scale_factor)
                    new_height = int(processed_img.height * scale_factor)
                    resized_img = processed_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    output.seek(0)
                    output.truncate(0)
                    resized_img.save(output, format=target_format, quality=85, optimize=True)
                    compressed_data = output.getvalue()

                    scale_factor -= 0.1

            return compressed_data, target_format


# global instance
image_processor = ImageProcessor()


def process_uploaded_image(image_data: bytes, filename: str = "") -> dict:
    """
    Handle upload ofpicture (convenience function)

    Args:
        image_data: picturetwo hexadecimal data
        filename: file name

    Returns:
        dict: Processing results
    """
    return image_processor.process_image(image_data, filename)
