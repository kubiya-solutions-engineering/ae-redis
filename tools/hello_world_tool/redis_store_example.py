import time
import redis
import json
import logging
import uuid
import os
from typing import Dict, Optional
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RedisStore:
    def __init__(self, host: str, port: int = 6379):
        self.client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
    
    def generate_unique_id(self) -> str:
        """Generate a unique ID for storing data"""
        return str(uuid.uuid4())[:8]
    
    def store_user_data(self, user_data: Dict) -> Optional[str]:
        """
        Store user data in Redis with a unique ID
        Returns the ID if successful, None if failed
        """
        try:
            # Generate unique ID
            data_id = self.generate_unique_id()
            
            # Add timestamp and user email from environment
            user_data['timestamp'] = str(int(time.time()))
            user_data['email'] = os.getenv('KUBIYA_USER_EMAIL')
            
            # Store in Redis with 24 hour expiration
            self.client.hset(f"user_profile:{data_id}", mapping=user_data)
            self.client.expire(f"user_profile:{data_id}", 86400)  # 24 hours
            
            logger.info(f"Successfully stored user data with ID: {data_id}")
            return data_id
            
        except redis.RedisError as e:
            logger.error(f"Failed to store data in Redis: {str(e)}")
            return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store request data in Redis")
    parser.add_argument(
        "--color",
        required=True,
        help="Favorite color"
    )
    parser.add_argument(
        "--animal",
        required=True,
        help="Favorite animal"
    )

    args = parser.parse_args()

    # Example usage
    redis_store = RedisStore(host="localhost")
    
    # Example request with two simple arguments
    request = {
        "favorite_color": args.color,
        "favorite_animal": args.animal
    }
    
    # Store the data
    data_id = redis_store.store_user_data(request)
    if data_id:
        # Show what actually got stored in Redis
        stored_data = redis_store.client.hgetall(f"user_profile:{data_id}")
        print(json.dumps({
            "request_id": data_id,
            "stored_data": stored_data
        }))
        # Exit with the request ID
        exit(0)
    else:
        print(json.dumps({
            "error": "Failed to store data in Redis"
        }))
        exit(1)