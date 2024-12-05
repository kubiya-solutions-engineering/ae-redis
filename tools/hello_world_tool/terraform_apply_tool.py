import argparse
import redis
import json
import os
import logging
import subprocess
from typing import Optional, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Use the same default directory as the plan tool
DEFAULT_TERRAFORM_DIR = os.path.join(os.path.dirname(__file__), "terraform")

class RedisConnectionError(Exception):
    """Custom exception for Redis connection errors"""
    pass

class TerraformError(Exception):
    """Custom exception for Terraform execution errors"""
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

def get_plan_data(redis_client: redis.Redis, request_id: str) -> Dict:
    """Retrieve plan data from Redis"""
    plan_data = redis_client.hgetall(f"terraform_plan:{request_id}")
    
    if not plan_data:
        raise ValueError(f"No plan data found for request ID: {request_id}")
    
    return plan_data

def setup_terraform_files(working_dir: str, environment: str) -> None:
    """Recreate Terraform configuration files with the stored environment"""
    from terraform_plan_tool import TERRAFORM_MAIN, TERRAFORM_VARS, TERRAFORM_TFVARS
    
    os.makedirs(working_dir, exist_ok=True)
    
    # Write main.tf
    with open(os.path.join(working_dir, "main.tf"), "w") as f:
        f.write(TERRAFORM_MAIN)
    
    # Write variables.tf
    with open(os.path.join(working_dir, "variables.tf"), "w") as f:
        f.write(TERRAFORM_VARS)
    
    # Write terraform.tfvars with the stored environment
    tfvars_content = TERRAFORM_TFVARS.replace(
        'environment         = "dev"',
        f'environment         = "{environment}"'
    )
    with open(os.path.join(working_dir, "terraform.tfvars"), "w") as f:
        f.write(tfvars_content)

def run_terraform_apply(working_dir: str) -> str:
    """Execute terraform apply"""
    try:
        # Initialize Terraform first
        init_cmd = ["terraform", "init"]
        subprocess.run(init_cmd, cwd=working_dir, check=True, capture_output=True)
        
        # Run terraform apply
        logger.info("Executing Terraform apply...")
        apply_cmd = ["terraform", "apply", "-auto-approve", "-no-color"]
        result = subprocess.run(
            apply_cmd,
            cwd=working_dir,
            check=True,
            capture_output=True,
            text=True
        )
        
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        error_message = f"Terraform command failed: {e.stderr}"
        logger.error(error_message)
        raise TerraformError(error_message)

def execute_terraform_apply(redis_client: redis.Redis, request_id: str) -> bool:
    """Execute Terraform apply using stored plan data"""
    try:
        # Get the stored plan data
        plan_data = get_plan_data(redis_client, request_id)
        
        # Setup Terraform files with the stored environment
        working_dir = DEFAULT_TERRAFORM_DIR
        setup_terraform_files(working_dir, plan_data['environment'])
        
        # Run terraform apply
        apply_output = run_terraform_apply(working_dir)
        
        # Store the apply results in Redis
        apply_data = {
            "apply_output": apply_output,
            "apply_timestamp": str(uuid.uuid1().timestamp()),
            "status": "completed"
        }
        redis_client.hset(f"terraform_plan:{request_id}", mapping=apply_data)
        
        logger.info(f"Successfully applied Terraform changes for request ID: {request_id}")
        return True

    except (redis.RedisError, TerraformError, ValueError) as e:
        logger.error(f"Error during Terraform apply: {str(e)}")
        # Store the error in Redis
        redis_client.hset(
            f"terraform_plan:{request_id}",
            mapping={
                "status": "failed",
                "error": str(e)
            }
        )
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute Terraform apply from stored plan")
    parser.add_argument(
        "request_id",
        help="Request ID from the terraform plan"
    )

    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_client = connect_to_redis()

        # Execute the apply
        success = execute_terraform_apply(redis_client, args.request_id)

        if not success:
            logger.error("Failed to apply Terraform changes")
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