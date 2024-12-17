from . import main
from . import send_to_slack
from . import terraform_plan_tool
from . import terraform_apply_tool
from . import redis_store_example
from . import redis_retrieve_example
import inspect

from kubiya_sdk.tools.models import Tool, Arg, FileSpec
from kubiya_sdk.tools.registry import tool_registry

redis_tool = Tool(
    name="store_request",
    type="docker",
    image="python:3.12",
    description="Stores request data in Redis ElastiCache and returns a unique request ID",
    env=["REDIS_HOST", "REDIS_PORT"],
    args=[
        Arg(name="user_name", description="Name of the user", required=True),
        Arg(name="message", description="Message to store", required=True)
    ],
    content="""
pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/main.py "{{ .user_name }}" "{{ .message }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/main.py",
            content=inspect.getsource(main),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\n",
        ),
    ],
)

slack_tool = Tool(
    name="send_to_slack",
    type="docker",
    image="python:3.12",
    description="Retrieves request data (user name, message) from Redis using the request ID and sends it to Slack",
    env=["REDIS_HOST", "REDIS_PORT"],
    secrets=["SLACK_API_TOKEN"],
    args=[
        Arg(name="request_id", description="Request ID to retrieve user name and message from Redis", required=True)
    ],
    content="""
pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/send_to_slack.py "{{ .request_id }}" "{{ .channel }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/send_to_slack.py",
            content=inspect.getsource(send_to_slack),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\nslack-sdk>=3.0.0\nfuzzywuzzy>=0.18.0\npython-Levenshtein>=0.21.0\n",
        ),
    ],
)

terraform_plan = Tool(
    name="terraform_plan",
    type="docker",
    image="python:3.12",
    description="Generates a Terraform plan for Redis ElastiCache infrastructure and stores it in Redis",
    env=["REDIS_HOST", "REDIS_PORT", "AWS_PROFILE"],
    args=[
        Arg(name="user_name", description="Name of the user requesting the change", required=True),
        Arg(name="environment", description="Target environment (dev, staging, prod)", required=True)
    ],
    content="""
# Install required packages silently
apt-get update > /dev/null 2>&1
apt-get install -y lsb-release gnupg software-properties-common curl > /dev/null 2>&1

# Install Terraform silently
curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null 2>&1
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list > /dev/null 2>&1
apt-get update > /dev/null 2>&1 && apt-get install -y terraform > /dev/null 2>&1

pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/terraform_plan_tool.py "{{ .user_name }}" --environment "{{ .environment }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/terraform_plan_tool.py",
            content=inspect.getsource(terraform_plan_tool),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\nboto3>=1.26.0\n",
        ),
        FileSpec(source="$HOME/.aws/credentials", destination="/root/.aws/credentials"),
        FileSpec(source="$HOME/.aws/config", destination="/root/.aws/config")
    ],
)

terraform_apply = Tool(
    name="terraform_apply",
    type="docker",
    image="python:3.12",
    description="Applies a previously generated Terraform plan using the request ID",
    env=["REDIS_HOST", "REDIS_PORT", "AWS_PROFILE"],
    args=[
        Arg(name="request_id", description="Request ID from the terraform plan", required=True)
    ],
    content="""
# Install required packages
apt-get update && apt-get install -y lsb-release gnupg software-properties-common curl

# Install Terraform
curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list
apt-get update && apt-get install -y terraform

pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/terraform_apply_tool.py "{{ .request_id }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/terraform_apply_tool.py",
            content=inspect.getsource(terraform_apply_tool),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\nboto3>=1.26.0\n",
        ),
        FileSpec(source="$HOME/.aws/credentials", destination="/root/.aws/credentials"),
        FileSpec(source="$HOME/.aws/config", destination="/root/.aws/config")
    ],
)

redis_store_example_tool = Tool(
    name="store_favorites",
    type="docker",
    image="python:3.12",
    description="Stores user's favorite color and animal in Redis and returns a unique request ID",
    env=["REDIS_HOST", "REDIS_PORT", "KUBIYA_USER_EMAIL"],
    args=[
        Arg(name="color", description="User's favorite color", required=True),
        Arg(name="animal", description="User's favorite animal", required=True)
    ],
    content="""
pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/redis_store_example.py --color "{{ .color }}" --animal "{{ .animal }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/redis_store_example.py",
            content=inspect.getsource(redis_store_example),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\n",
        ),
    ],
)

redis_retrieve_example_tool = Tool(
    name="retrieve_favorites",
    type="docker",
    image="python:3.12",
    description="Retrieves user's favorite color and animal from Redis using the request ID",
    env=["REDIS_HOST", "REDIS_PORT"],
    args=[
        Arg(name="request_id", description="Request ID to retrieve the stored favorites", required=True)
    ],
    content="""
pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/redis_retrieve_example.py "{{ .request_id }}"
""",
    with_files=[
        FileSpec(
            destination="/tmp/redis_retrieve_example.py",
            content=inspect.getsource(redis_retrieve_example),
        ),
        FileSpec(
            destination="/tmp/requirements.txt",
            content="redis>=5.0.0\n",
        ),
    ],
)

tool_registry.register("redis_store", redis_tool)
tool_registry.register("slack_sender", slack_tool)
tool_registry.register("terraform_plan", terraform_plan)
tool_registry.register("terraform_apply", terraform_apply)
tool_registry.register("store_favorites", redis_store_example_tool)
tool_registry.register("retrieve_favorites", redis_retrieve_example_tool)