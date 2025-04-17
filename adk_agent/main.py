import yaml
import logging
import uvicorn
import asyncio # Import asyncio for async operations
import uuid # Import uuid for generating task IDs
from common.server.server import A2AServer
from common.server.task_manager import TaskManager
import yaml
import logging
import uvicorn
import asyncio # Import asyncio for async operations
import uuid # Import uuid for generating task IDs
from common.server.server import A2AServer
from common.server.task_manager import TaskManager
from common.types import (
    AgentCard, AgentCapabilities, AgentSkill,
    GetTaskRequest, SendTaskRequest, CancelTaskRequest,
    SetTaskPushNotificationRequest, GetTaskPushNotificationRequest,
    TaskResubscriptionRequest, SendTaskStreamingRequest, JSONRPCResponse,
    Message, TextPart,
    Task, TaskStatus, TaskState # Import Task related types
)
from common.client.client import A2AClient # Import the A2A client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy Task Manager for initial setup
class AdkTaskManager(TaskManager):
    async def on_get_task(self, request: GetTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTask request: {request.model_dump_json()}")
        # Dummy response for now
        return JSONRPCResponse(id=request.id, result={"status": "Task not found"})

    async def on_send_task(self, request: SendTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received SendTask request: {request.model_dump_json(exclude_none=True)}")
        # Create a dummy Task object as the result
        task_id = request.params.id
        session_id = request.params.sessionId
        # Include the received message in the TaskStatus
        task_status = TaskStatus(state=TaskState.SUBMITTED, message=request.params.message)
        task_result = Task(id=task_id, sessionId=session_id, status=task_status)
        return JSONRPCResponse(id=request.id, result=task_result)

    async def on_send_task_subscribe(self, request: SendTaskStreamingRequest):
        logger.info(f"Received SendTaskStreaming request: {request.model_dump_json()}")
        # Dummy response for now
        yield JSONRPCResponse(id=request.id, result={"task_id": "dummy-task-id", "status": "Task received, streaming not implemented"})

    async def on_cancel_task(self, request: CancelTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received CancelTask request: {request.model_dump_json()}")
        return JSONRPCResponse(id=request.id, result={"status": "Cancel request received"})

    async def on_set_task_push_notification(self, request: SetTaskPushNotificationRequest) -> JSONRPCResponse:
        logger.info(f"Received SetTaskPushNotification request: {request.model_dump_json()}")
        return JSONRPCResponse(id=request.id, result={"status": "Push notification setting received"})

    async def on_get_task_push_notification(self, request: GetTaskPushNotificationRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTaskPushNotification request: {request.model_dump_json()}")
        return JSONRPCResponse(id=request.id, result={"push_notification_endpoint": None})

    async def on_resubscribe_to_task(self, request: TaskResubscriptionRequest):
         logger.info(f"Received TaskResubscription request: {request.model_dump_json()}")
         # Dummy response for now
         yield JSONRPCResponse(id=request.id, result={"status": "Resubscription not implemented"})


def load_config(config_path="adk_config.yaml"):
    """Loads agent configuration from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}", exc_info=True)
        return None

async def send_initial_message(target_config):
    """Sends an initial test message to the target agent."""
    if not target_config:
        logger.warning("Target agent configuration not found. Skipping initial message.")
        return

    target_url = f"http://{target_config.get('address', 'localhost')}:{target_config.get('port', 8002)}/"
    client = A2AClient(url=target_url)

    message_payload = Message(
        role="user", # From the perspective of the receiving agent
        parts=[TextPart(text="Hello from ADK Agent! (Test Message)")]
    )
    task_id = f"task-{uuid.uuid4()}" # Generate a unique task ID
    task_params = {
        "id": task_id, # Add the required task ID
        "message": message_payload.model_dump(exclude_none=True)
        # sessionId will be generated by TaskSendParams default factory
    }

    try:
        logger.info(f"Sending test message to {target_url}...")
        response = await client.send_task(task_params)
        logger.info(f"Received response from target agent: {response.model_dump_json()}")
    except Exception as e:
        logger.error(f"Error sending initial message: {e}", exc_info=True)


async def main():
    """Main async function to start the server and send initial message."""
    logger.info("ADK Agent starting...")
    config = load_config()

    if not config:
        logger.error("Failed to load configuration. Agent cannot start.")
        return

    agent_id = config.get("agent_id", "default-adk-agent")
    listen_port = config.get("listen_port", 8001)
    target_config = config.get("target_agent")

    # Define the Agent Card
    agent_card = AgentCard(
        name=agent_id,
        description="A sample agent built with Google ADK speaking A2A.",
        url=f"http://localhost:{listen_port}/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False, stateTransitionHistory=False),
        skills=[AgentSkill(id="basic-chat", name="Basic Chat", description="Handles basic chat interactions.")]
    )

    task_manager = AdkTaskManager()

    server = A2AServer(
        host="0.0.0.0",
        port=listen_port,
        agent_card=agent_card,
        task_manager=task_manager
    )

    # Configure the Uvicorn server
    uvicorn_config = uvicorn.Config(server.app, host="0.0.0.0", port=listen_port, log_level="info") # Renamed config variable
    uvicorn_server = uvicorn.Server(uvicorn_config) # Use renamed variable

    # Start the server in the background using serve()
    server_task = asyncio.create_task(uvicorn_server.serve())

    logger.info(f"A2A server for agent '{agent_id}' starting on port {listen_port}...")
    # Wait briefly to ensure server starts before sending message

    # Wait a moment for the server to start, then send the initial message
    await asyncio.sleep(2)
    await send_initial_message(target_config)

    # Keep the main task running (or handle server shutdown gracefully)
    await server_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ADK Agent shutting down.")
