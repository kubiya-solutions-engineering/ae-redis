import redis
import json
import logging
from typing import Dict, Optional
import argparse
import os

class RedisConnectionError(Exception):
    """Custom exception for Redis connection errors"""
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RedisRetriever:
    def __init__(self):
        host = os.getenv('REDIS_HOST')
        port = int(os.getenv('REDIS_PORT', '6379'))
        
        if not host:
            logger.error("REDIS_HOST environment variable is not set")
            raise RedisConnectionError("REDIS_HOST environment variable is not set")
            
        self.client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
    
    def get_user_data(self, data_id: str) -> Optional[Dict]:
        """
        Retrieve user data from Redis using the data ID
        Returns the data if found, None if not found or error
        """
        try:
            # Get data from Redis
            data = self.client.hgetall(f"user_profile:{data_id}")
            
            if not data:
                logger.warning(f"No data found for ID: {data_id}")
                return None
            
            logger.info(f"Successfully retrieved data for ID: {data_id}")
            return data
            
        except redis.RedisError as e:
            logger.error(f"Failed to retrieve data from Redis: {str(e)}")
            return None
    
    def delete_user_data(self, data_id: str) -> bool:
        """
        Delete user data from Redis using the data ID
        Returns True if successful, False otherwise
        """
        try:
            # Delete data from Redis
            result = self.client.delete(f"user_profile:{data_id}")
            
            if result:
                logger.info(f"Successfully deleted data for ID: {data_id}")
                return True
            
            logger.warning(f"No data found to delete for ID: {data_id}")
            return False
            
        except redis.RedisError as e:
            logger.error(f"Failed to delete data from Redis: {str(e)}")
            return False
    
    def close(self):
        """Close the Redis connection"""
        try:
            self.client.close()
            logger.debug("Redis connection closed")
        except:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve request data from Redis")
    parser.add_argument(
        "request_id",
        help="The request ID to retrieve data for"
    )

    args = parser.parse_args()
    
    # Example usage
    redis_retriever = RedisRetriever()
    
    try:
        # Retrieve request data using the request ID
        request_data = redis_retriever.get_user_data(args.request_id)
        
        if request_data:
            print("\nRetrieved data:")
            print(json.dumps({
                "request_id": args.request_id,
                "data": {
                    "favorite_color": request_data.get("favorite_color"),
                    "favorite_animal": request_data.get("favorite_animal"),
                    "timestamp": request_data.get("timestamp"),
                    "email": request_data.get("email")
                }
            }, indent=2))
            
            # Delete the data after successful retrieval
            if redis_retriever.delete_user_data(args.request_id):
                logger.info(f"Data cleaned up for request ID: {args.request_id}")
            else:
                logger.warning(f"Failed to clean up data for request ID: {args.request_id}")
        else:
            print(json.dumps({
                "error": f"No data found for request ID: {args.request_id}"
            }))
            exit(1)
            
    except RedisConnectionError as e:
        print(json.dumps({
            "error": str(e)
        }))
        exit(1)
    finally:
        redis_retriever.close() 