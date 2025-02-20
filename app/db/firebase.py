import os
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings

logger = logging.getLogger("firebase")

def initialize_firebase():
    try:
        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        
        if not os.path.exists(cred_path):
            logger.warning(f"Firebase credentials file not found at: {cred_path}")
            return None

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        return None

db = initialize_firebase()