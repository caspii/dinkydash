"""
Image upload and processing utilities.
Handles image validation, saving, and deletion for dashboard icons.
"""
import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app


# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Maximum image dimensions (will resize if larger)
MAX_IMAGE_SIZE = (800, 800)


def allowed_file(filename):
    """
    Check if filename has an allowed extension.

    Args:
        filename (str): Filename to check

    Returns:
        bool: True if extension is allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image(file):
    """
    Validate an uploaded image file.

    Args:
        file (FileStorage): Uploaded file object from Flask request

    Returns:
        tuple: (is_valid, error_message)
            - is_valid (bool): True if valid, False otherwise
            - error_message (str): Error description if invalid, None if valid

    """
    if not file:
        return False, "No file provided"

    if file.filename == '':
        return False, "No file selected"

    if not allowed_file(file.filename):
        return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"

    # Check file size (MAX_CONTENT_LENGTH is enforced by Flask, but we can check here too)
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer

    if file_size > max_size:
        return False, f"File too large. Maximum size: {max_size / (1024 * 1024):.1f}MB"

    # Validate that it's actually an image by trying to open it with PIL
    try:
        img = Image.open(file)
        img.verify()  # Verify it's an image
        file.seek(0)  # Reset file pointer after verify
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

    return True, None


def save_image(file, tenant_id):
    """
    Save an uploaded image file to the uploads directory.

    Creates a unique filename and resizes the image if needed.

    Args:
        file (FileStorage): Uploaded file object from Flask request
        tenant_id (int): Tenant ID for organizing uploads

    Returns:
        str: Relative path to saved image (e.g., "uploads/1/abc123.jpg")

    Raises:
        ValueError: If image validation fails
        IOError: If image cannot be saved
    """
    # Validate image first
    is_valid, error_message = validate_image(file)
    if not is_valid:
        raise ValueError(error_message)

    # Generate unique filename
    ext = secure_filename(file.filename).rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # Create tenant-specific upload directory
    upload_folder = current_app.config['UPLOAD_FOLDER']
    tenant_folder = os.path.join(upload_folder, str(tenant_id))
    os.makedirs(tenant_folder, exist_ok=True)

    # Full path for saving
    file_path = os.path.join(tenant_folder, unique_filename)

    # Open and process image
    try:
        img = Image.open(file)

        # Convert RGBA to RGB if necessary (for JPEG compatibility)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # Resize if too large (maintain aspect ratio)
        img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

        # Save optimized image
        img.save(file_path, optimize=True, quality=85)

    except Exception as e:
        raise IOError(f"Failed to save image: {str(e)}")

    # Return relative path for database storage
    return os.path.join('uploads', str(tenant_id), unique_filename)


def delete_image(image_path):
    """
    Delete an image file from the uploads directory.

    Args:
        image_path (str): Relative path to image (e.g., "uploads/1/abc123.jpg")

    Returns:
        bool: True if deleted successfully, False if file doesn't exist

    Raises:
        IOError: If deletion fails for reasons other than file not existing
    """
    if not image_path:
        return False

    # Build full path
    upload_folder = current_app.config['UPLOAD_FOLDER']
    # Remove 'uploads/' prefix if present since UPLOAD_FOLDER already includes it
    if image_path.startswith('uploads/'):
        image_path = image_path[8:]  # Remove 'uploads/' prefix

    file_path = os.path.join(upload_folder, image_path)

    # Check if file exists
    if not os.path.exists(file_path):
        return False

    # Delete file
    try:
        os.remove(file_path)
        return True
    except Exception as e:
        raise IOError(f"Failed to delete image: {str(e)}")


def get_image_url(image_path):
    """
    Convert a relative image path to a URL path for templates.

    Args:
        image_path (str): Relative path (e.g., "uploads/1/abc123.jpg")

    Returns:
        str: URL path (e.g., "/static/uploads/1/abc123.jpg")
    """
    if not image_path:
        return None

    # Ensure path starts with uploads/
    if not image_path.startswith('uploads/'):
        image_path = f"uploads/{image_path}"

    return f"/static/{image_path}"
