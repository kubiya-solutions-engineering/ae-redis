from . import main
from . import send_to_slack
import inspect

from kubiya_sdk.tools.models import Tool, Arg, FileSpec
from kubiya_sdk.tools.registry import tool_registry

redis_tool = Tool(
    name="store_request",
    type="docker",
    image="python:3.12",
    description="Stores request data in Redis ElastiCache",
    env=["REDIS_HOST", "REDIS_PORT"],
    args=[
        Arg(name="request_id", description="Unique request identifier", required=True),
        Arg(name="user_name", description="Name of the user", required=True),
        Arg(name="message", description="Message to store", required=True)
    ],
    content="""
pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/main.py "{{ .request_id }}" "{{ .user_name }}" "{{ .message }}"
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
            content="redis>=5.0.0\nslack-sdk>=3.0.0\n",
        ),
    ],
)

tool_registry.register("redis_store", redis_tool)
tool_registry.register("slack_sender", slack_tool)
