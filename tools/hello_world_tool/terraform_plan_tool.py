import argparse
import redis
import json
import os
import logging
import uuid
import subprocess
from typing import Optional, Tuple, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add near the top of the file, after the imports
DEFAULT_TERRAFORM_DIR = os.path.join(os.path.dirname(__file__), "terraform")

# Add these constants near the top of the file after DEFAULT_TERRAFORM_DIR
TERRAFORM_MAIN = '''provider "aws" {
  region = var.aws_region
}

resource "aws_elasticache_cluster" "demo_redis" {
  cluster_id           = "demo-redis-${var.environment}"
  engine              = "redis"
  node_type           = var.node_type
  num_cache_nodes     = 1
  parameter_group_name = "default.redis7"
  port                = 6379
  security_group_ids  = [aws_security_group.redis_sg.id]
  
  tags = {
    Environment = var.environment
    Project     = "Demo"
  }
}

resource "aws_security_group" "redis_sg" {
  name        = "demo-redis-sg-${var.environment}"
  description = "Security group for demo Redis cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.environment
    Project     = "Demo"
  }
}'''

TERRAFORM_VARS = '''variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "vpc_id" {
  description = "VPC ID where resources will be created"
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "List of CIDR blocks allowed to connect to Redis"
  type        = list(string)
}'''

TERRAFORM_TFVARS = '''environment         = "dev"
aws_region         = "us-west-2"
node_type          = "cache.t3.micro"
vpc_id             = "vpc-12345678"
allowed_cidr_blocks = ["10.0.0.0/16"]'''

def setup_terraform_files(working_dir: str) -> None:
    """Create Terraform configuration files in the working directory"""
    os.makedirs(working_dir, exist_ok=True)
    
    # Write main.tf
    with open(os.path.join(working_dir, "main.tf"), "w") as f:
        f.write(TERRAFORM_MAIN)
    
    # Write variables.tf
    with open(os.path.join(working_dir, "variables.tf"), "w") as f:
        f.write(TERRAFORM_VARS)
    
    # Write terraform.tfvars
    with open(os.path.join(working_dir, "terraform.tfvars"), "w") as f:
        f.write(TERRAFORM_TFVARS)
    
    logger.info(f"Created Terraform configuration files in {working_dir}")

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


def generate_unique_request_id(redis_client: redis.Redis) -> str:
    """Generate a unique request ID and ensure it doesn't exist in Redis"""
    max_attempts = 5
    for _ in range(max_attempts):
        request_id = str(uuid.uuid4())[:8]
        if not redis_client.exists(f"terraform_plan:{request_id}"):
            logger.info(f"Generated unique request ID: {request_id}")
            return request_id
    
    raise ValueError("Could not generate unique request ID after multiple attempts")


def run_terraform_plan(working_dir: str, vars_file: Optional[str] = None) -> str:
    """Execute terraform plan and return the output"""
    try:
        # Create Terraform files if using default directory
        if working_dir == DEFAULT_TERRAFORM_DIR:
            setup_terraform_files(working_dir)
        
        # Initialize Terraform first
        init_cmd = ["terraform", "init"]
        subprocess.run(init_cmd, cwd=working_dir, check=True, capture_output=True)
        
        # Construct plan command
        plan_cmd = ["terraform", "plan", "-no-color"]
        if vars_file:
            plan_cmd.extend(["-var-file", vars_file])
        
        # Add output to JSON format
        plan_cmd.extend(["-out=tfplan"])
        
        # Run terraform plan
        logger.info("Executing Terraform plan...")
        result = subprocess.run(
            plan_cmd,
            cwd=working_dir,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Capture the human-readable output
        plan_output = result.stdout
        
        # Show plan in JSON format
        show_cmd = ["terraform", "show", "-json", "tfplan"]
        show_result = subprocess.run(
            show_cmd,
            cwd=working_dir,
            check=True,
            capture_output=True,
            text=True
        )
        
        return plan_output, show_result.stdout
        
    except subprocess.CalledProcessError as e:
        error_message = f"Terraform command failed: {e.stderr}"
        logger.error(error_message)
        raise TerraformError(error_message)


def store_terraform_plan(
    redis_client: redis.Redis,
    user_name: str,
    environment: str,
) -> Tuple[str, bool]:
    """Generate and store Terraform plan data in Redis"""
    try:
        if not user_name or not environment:
            raise ValueError("user_name and environment are required")

        # Generate unique request ID
        request_id = generate_unique_request_id(redis_client)

        # Use default working directory
        working_dir = DEFAULT_TERRAFORM_DIR

        # Modify terraform.tfvars content with requested environment
        tfvars_content = TERRAFORM_TFVARS.replace(
            'environment         = "dev"',
            f'environment         = "{environment}"'
        )

        # Ensure directory exists and write files
        os.makedirs(working_dir, exist_ok=True)
        
        # Write all Terraform files with the modified environment
        with open(os.path.join(working_dir, "main.tf"), "w") as f:
            f.write(TERRAFORM_MAIN)
        
        with open(os.path.join(working_dir, "variables.tf"), "w") as f:
            f.write(TERRAFORM_VARS)
        
        with open(os.path.join(working_dir, "terraform.tfvars"), "w") as f:
            f.write(tfvars_content)

        # Run terraform plan
        plan_output, plan_json = run_terraform_plan(working_dir)

        # Prepare data for storage
        data = {
            "request_id": request_id,
            "user_name": user_name,
            "environment": environment,
            "plan_output": plan_output,
            "plan_json": plan_json,
            "timestamp": str(uuid.uuid1().timestamp())
        }
        
        redis_client.hset(f"terraform_plan:{request_id}", mapping=data)
        redis_client.expire(f"terraform_plan:{request_id}", 86400)
        
        logger.info(f"Successfully stored Terraform plan data for request_id: {request_id}")
        return request_id, True

    except (redis.RedisError, TerraformError, ValueError) as e:
        logger.error(f"Error while storing Terraform plan: {str(e)}")
        return None, False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and store Terraform plan")
    parser.add_argument("user_name", help="Name of the user requesting the change")
    parser.add_argument(
        "--environment",
        required=True,
        help="Target environment for the change (e.g., dev, staging, prod)"
    )

    args = parser.parse_args()

    try:
        # Connect to Redis
        redis_client = connect_to_redis()

        # Generate and store the plan
        request_id, success = store_terraform_plan(
            redis_client,
            args.user_name,
            args.environment
        )

        if success:
            logger.info(f"Successfully stored Terraform plan with request ID: {request_id}")
            # Print the request ID for capture by the tool
            print(request_id)
        else:
            logger.error("Failed to store Terraform plan")
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