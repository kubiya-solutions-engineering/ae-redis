import argparse
import redis
import json
import os
import logging
from typing import Optional

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
        client = redis.Redis(
            host=host,
            port=port,
            ssl=True,  # Enable SSL for encrypted connection
            decode_responses=True
        )
        # Test the connection
        client.ping()
        logger.info(f"Successfully connected to Redis at {host}:{port}")
        return client
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while connecting to Redis: {str(e)}")
        raise RedisConnectionError(f"Unexpected error while connecting to Redis: {str(e)}")


def store_request_data(
    redis_client: redis.Redis,
    request_id: str,
    user_name: str,
    message: str,
) -> bool:
    """Store request data in Redis"""
    try:
        if not request_id or not user_name or not message:
            logger.error("Missing required parameters")
            raise ValueError("request_id, user_name, and message are required")

        data = {
            "request_id": request_id,
            "user_name": user_name,
            "message": message,
        }
        
        logger.info(f"Attempting to store data for request_id: {request_id}")
        # Store as a hash
        redis_client.hset(f"request:{request_id}", mapping=data)
        # Set expiration for 24 hours
        redis_client.expire(f"request:{request_id}", 86400)
        
        logger.info(f"Successfully stored data for request_id: {request_id}")
        return True
    except redis.RedisError as e:
        logger.error(f"Redis error while storing data: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while storing data: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store request data in Redis")
    parser.add_argument("request_id", help="Unique request identifier")
    parser.add_argument("user_name", help="Name of the user")
    parser.add_argument("message", help="Message to store")

    args = parser.parse_args()

    try:
        # Connect to Redis using environment variables
        redis_client = connect_to_redis()

        # Store the data
        success = store_request_data(
            redis_client,
            args.request_id,
            args.user_name,
            args.message,
        )

        if success:
            logger.info(f"Successfully stored request {args.request_id} in Redis")
        else:
            logger.error(f"Failed to store request {args.request_id} in Redis")
            exit(1)
    except RedisConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        exit(1)
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        exit(1)
    finally:
        try:
            redis_client.close()
            logger.debug("Redis connection closed")
        except:
            pass
