import argparse
import redis
import json
import os
import logging
import uuid
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
        # Log connection attempt
        logger.info(f"Attempting to connect to Redis at {host}:{port}")
        
        # Add connection timeout to avoid hanging
        client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=5.0,  # 5 second timeout
            socket_connect_timeout=5.0
        )
        
        # Test the connection with timeout
        try:
            client.ping()
        except redis.TimeoutError:
            logger.error(f"Connection timeout while connecting to Redis at {host}:{port}")
            raise RedisConnectionError(f"Connection timeout while connecting to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            if "name resolution" in str(e).lower():
                logger.error(f"DNS resolution failed for Redis host '{host}'. Please verify the hostname is correct.")
                raise RedisConnectionError(f"DNS resolution failed for Redis host '{host}'. Please verify the hostname is correct.")
            raise
            
        logger.info(f"Successfully connected to Redis at {host}:{port}")
        return client
        
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while connecting to Redis: {str(e)}")
        raise RedisConnectionError(f"Unexpected error while connecting to Redis: {str(e)}")


def generate_unique_request_id(redis_client: redis.Redis) -> str:
    """Generate a unique request ID and ensure it doesn't exist in Redis"""
    max_attempts = 5
    for _ in range(max_attempts):
        # Generate a random UUID4 and take first 8 characters
        request_id = str(uuid.uuid4())[:8]
        
        # Check if this ID already exists
        if not redis_client.exists(f"request:{request_id}"):
            logger.info(f"Generated unique request ID: {request_id}")
            return request_id
    
    # If we couldn't generate a unique ID after max attempts
    raise ValueError("Could not generate unique request ID after multiple attempts")


def store_request_data(
    redis_client: redis.Redis,
    user_name: str,
    message: str,
) -> tuple[str, bool]:
    """Store request data in Redis with auto-generated request ID"""
    try:
        if not user_name or not message:
            logger.error("Missing required parameters")
            raise ValueError("user_name and message are required")

        # Generate unique request ID
        request_id = generate_unique_request_id(redis_client)

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
        return request_id, True
    except redis.RedisError as e:
        logger.error(f"Redis error while storing data: {str(e)}")
        return None, False
    except Exception as e:
        logger.error(f"Unexpected error while storing data: {str(e)}")
        return None, False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store request data in Redis")
    parser.add_argument("user_name", help="Name of the user")
    parser.add_argument("message", help="Message to store")

    args = parser.parse_args()

    try:
        # Connect to Redis using environment variables
        redis_client = connect_to_redis()

        # Store the data
        request_id, success = store_request_data(
            redis_client,
            args.user_name,
            args.message,
        )

        if success:
            logger.info(f"Successfully stored request {request_id} in Redis")
            # Print the request ID so it can be captured by the tool
            print(request_id)
        else:
            logger.error("Failed to store request in Redis")
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
