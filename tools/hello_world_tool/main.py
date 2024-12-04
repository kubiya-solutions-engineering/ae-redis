import argparse
import redis
import json
import os
from typing import Optional


def connect_to_redis() -> redis.Redis:
    """Establish connection to Redis using environment variables"""
    host = os.getenv('REDIS_HOST')
    port = int(os.getenv('REDIS_PORT', '6379'))
    
    if not host:
        raise ValueError("REDIS_HOST environment variable is not set")
    
    return redis.Redis(
        host=host,
        port=port,
        ssl=True,  # Enable SSL for encrypted connection
        decode_responses=True
    )


def store_request_data(
    redis_client: redis.Redis,
    request_id: str,
    user_name: str,
    message: str,
    priority: Optional[int] = 1
) -> bool:
    """Store request data in Redis"""
    try:
        data = {
            "request_id": request_id,
            "user_name": user_name,
            "message": message,
            "priority": priority
        }
        # Store as a hash
        redis_client.hset(f"request:{request_id}", mapping=data)
        # Set expiration for 24 hours
        redis_client.expire(f"request:{request_id}", 86400)
        return True
    except Exception as e:
        print(f"Error storing data: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store request data in Redis")
    parser.add_argument("request_id", help="Unique request identifier")
    parser.add_argument("user_name", help="Name of the user")
    parser.add_argument("message", help="Message to store")
    parser.add_argument("--priority", type=int, default=1, help="Request priority (default: 1)")

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
            args.priority
        )

        if success:
            print(f"Successfully stored request {args.request_id} in Redis")
        else:
            print(f"Failed to store request {args.request_id} in Redis")
            exit(1)
    except ValueError as e:
        print(f"Configuration error: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        exit(1)
