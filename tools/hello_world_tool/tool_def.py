from . import main

import inspect

from kubiya_sdk.tools.models import Tool, Arg, FileSpec
from kubiya_sdk.tools.registry import tool_registry

redis_tool = Tool(
    name="store_request",
    type="docker",
    image="python:3.12",
    description="Stores request data in Redis ElastiCache",
    args=[
        Arg(name="request_id", description="Unique request identifier", required=True),
        Arg(name="user_name", description="Name of the user", required=True),
        Arg(name="message", description="Message to store", required=True),
        Arg(name="priority", description="Request priority", required=False, default="1"),
    ],
    content="""
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1
. $HOME/.cargo/env

uv venv > /dev/null 2>&1
. .venv/bin/activate > /dev/null 2>&1

uv pip install -r /tmp/requirements.txt > /dev/null 2>&1

python /tmp/main.py "{{ .request_id }}" "{{ .user_name }}" "{{ .message }}" \
    --priority {{ .priority }}
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

tool_registry.register("redis_store", redis_tool)
