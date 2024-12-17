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

class RedisConnectionError(Exception):
    """Custom exception for Redis connection errors"""
    pass

def connect_to_redis() -> redis.Redis:
    """Establish connection to Redis using environment variables"""
    host = os.getenv('REDIS_HOST')
    port = int(os.getenv('REDIS_PORT', '6379'))
    
    if not host:
        logger.error("REDIS_HOST environment variable is not set")
        raise RedisConnectionError("REDIS_HOST environment variable is not set")
    
    try:
        logger.info(f"Attempting to connect to Redis at {host}:{port}")
        client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
        
        client.ping()
        logger.info(f"Successfully connected to Redis at {host}:{port}")
        return client
        
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")

class RedisStore:
    def __init__(self):
        self.client = connect_to_redis()
    
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
            
            # Store in Redis without expiration
            self.client.hset(f"user_profile:{data_id}", mapping=user_data)
            
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

    try:
        # Create Redis store instance
        redis_store = RedisStore()
        
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
            exit(0)
        else:
            print(json.dumps({
                "error": "Failed to store data in Redis"
            }))
            exit(1)
    
    except RedisConnectionError as e:
        print(json.dumps({
            "error": str(e)
        }))
        exit(1)
    finally:
        try:
            redis_store.client.close()
            logger.debug("Redis connection closed")
        except:
            pass