from desktop_agent.desktop.vision.vision_validator import VisionValidator
from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import TesseractBackend

backend = TesseractBackend()

validator = VisionValidator(
    backend,
)

validator.validate()