"""
Configuration uvicorn pour augmenter la limite d'upload
"""

# Configuration pour uvicorn
# Augmente la limite de taille de body HTTP à 100 MB
h11_max_incomplete_event_size = 100 * 1024 * 1024  # 100 MB
