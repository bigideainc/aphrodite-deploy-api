import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import settings

logger = logging.getLogger("firebase")

_firebase_app = None
_firestore_client = None

def initialize_firebase():
    global _firebase_app, _firestore_client
    
    # If already initialized, return existing client
    if _firestore_client is not None:
        return _firestore_client

    try:
        cred_path = settings.FIREBASE_CREDENTIALS_PATH

        if not os.path.exists(cred_path):
            logger.warning(f"Firebase credentials file not found at: {cred_path}")
            return None

        # Check if app is already initialized to prevent double initialization
        try:
            firebase_admin.get_app()
        except ValueError:
            # No default app exists, so initialize
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)

        _firestore_client = firestore.client()
        logger.info("Firebase initialized successfully")
        return _firestore_client

    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        return None

# Initialize only once when the module is first imported
db = initialize_firebase()