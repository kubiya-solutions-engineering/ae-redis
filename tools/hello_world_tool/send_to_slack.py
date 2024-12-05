import argparse
import redis
import os
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import Optional, Dict
from fuzzywuzzy import fuzz

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
        
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise RedisConnectionError(f"Failed to connect to Redis: {str(e)}")


def get_request_data(redis_client: redis.Redis, request_id: str) -> Optional[Dict]:
    """Retrieve request data from Redis"""
    try:
        data = redis_client.hgetall(f"request:{request_id}")
        if not data:
            logger.error(f"No data found for request_id: {request_id}")
            return None
        
        logger.info(f"Successfully retrieved data for request_id: {request_id}")
        return data
    except redis.RedisError as e:
        logger.error(f"Redis error while retrieving data: {str(e)}")
        return None


def create_block_kit_message(message: str, user_name: str) -> list:
    """Create a Block Kit formatted message"""
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": message}
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":speech_balloon: Message sent on behalf of {user_name}"
                }
            ]
        }
    ]


def find_channel(client: WebClient, channel_input: str) -> Optional[str]:
    """Find the correct channel ID from channel name or ID"""
    logger.info(f"Attempting to find channel: {channel_input}")
    
    # If it's already a valid channel ID
    if channel_input.startswith('C') and len(channel_input) == 11:
        return channel_input
    
    # Remove '#' if present
    channel_input = channel_input.lstrip('#')
    
    try:
        for response in client.conversations_list(types="public_channel,private_channel"):
            for channel in response["channels"]:
                if channel["name"] == channel_input:
                    return channel["id"]
                elif fuzz.ratio(channel["name"], channel_input) > 80:
                    logger.info(f"Found close match: {channel['name']}")
                    return channel["id"]
    except SlackApiError as e:
        logger.error(f"Error listing channels: {e}")
    
    return None


def send_slack_message(channel: str, message: str, user_name: str) -> bool:
    """Send message to Slack channel with improved formatting and error handling"""
    slack_token = os.getenv('SLACK_BOT_TOKEN')
    if not slack_token:
        logger.error("SLACK_BOT_TOKEN environment variable is not set")
        raise ValueError("SLACK_BOT_TOKEN environment variable is not set")

    client = WebClient(token=slack_token)
    
    # Hardcode channel to #testing
    channel = "#testing"
    channel_id = find_channel(client, channel)
    if not channel_id:
        logger.error(f"Could not find channel: {channel}")
        return False
    
    try:
        # Create Block Kit message
        blocks = create_block_kit_message(message, user_name)
        fallback_text = f"{message}\n\n_Message sent on behalf of {user_name}_"

        # Try sending with Block Kit first
        try:
            response = client.chat_postMessage(
                channel=channel_id,
                blocks=blocks,
                text=fallback_text
            )
            logger.info(f"Block Kit message sent successfully to {channel}")
        except SlackApiError as block_error:
            logger.warning(f"Failed to send Block Kit message: {block_error}. Falling back to regular message.")
            response = client.chat_postMessage(
                channel=channel_id,
                text=fallback_text
            )
            logger.info(f"Regular message sent successfully to {channel}")
        
        return True
        
    except SlackApiError as e:
        logger.error(f"Failed to send message to Slack: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve request data from Redis and send to Slack")
    parser.add_argument("request_id", help="Request ID to retrieve from Redis")
    parser.add_argument("channel", help="Slack channel to send the message to")

    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_client = connect_to_redis()

        # Get the data
        data = get_request_data(redis_client, args.request_id)
        if not data:
            logger.error("Failed to retrieve data from Redis")
            exit(1)

        # Send to Slack
        success = send_slack_message(
            channel=args.channel,
            message=data['message'],
            user_name=data['user_name']
        )

        if success:
            logger.info(f"Successfully processed request {args.request_id}")
        else:
            logger.error(f"Failed to send message to Slack for request {args.request_id}")
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