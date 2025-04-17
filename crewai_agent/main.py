# CrewAI Agent main script
# (Implementation will follow in subsequent steps)
import yaml
import logging
import uvicorn
import yaml
import logging
import uvicorn
# Assuming we can reuse the common server components
import yaml
import logging
import uvicorn
import asyncio # Import asyncio
import uuid # Import uuid
# Assuming we can reuse the common server components
from common.server.server import A2AServer
from common.server.task_manager import TaskManager
from common.types import (
    AgentCard, AgentCapabilities, AgentSkill,
    GetTaskRequest, SendTaskRequest, CancelTaskRequest,
    SetTaskPushNotificationRequest, GetTaskPushNotificationRequest,
    TaskResubscriptionRequest, SendTaskStreamingRequest, JSONRPCResponse,
    Task, TaskStatus, TaskState,
    Message, TextPart # Import Message and TextPart
)
from common.client.client import A2AClient # Import the client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy Task Manager for initial setup
class CrewAiTaskManager(TaskManager):
    async def on_get_task(self, request: GetTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTask request: {request.model_dump_json()}")
        return JSONRPCResponse(id=request.id, result={"status": "Task not found"})

    async def on_send_task(self, request: SendTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received SendTask request: {request.model_dump_json(exclude_none=True)}")
        # Here you would typically trigger a CrewAI task
        # For now, create a dummy Task object as the result
        task_id = request.params.id
        session_id = request.params.sessionId
        # Include the received message in the TaskStatus
        task_status = TaskStatus(state=TaskState.SUBMITTED, message=request.params.message)
        # Create the Task object
        task_result = Task(id=task_id, sessionId=session_id, status=task_status)
        return JSONRPCResponse(id=request.id, result=task_result)

    async def on_send_task_subscribe(self, request: SendTaskStreamingRequest):
        logger.info(f"Received SendTaskStreaming request: {request.model_dump_json()}")
        yield JSONRPCResponse(id=request.id, result={"task_id": "dummy-crewai-task-id", "status": "Task received, streaming not implemented"})

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
         yield JSONRPCResponse(id=request.id, result={"status": "Resubscription not implemented"})


def load_config(config_path="crewai_config.yaml"):
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

    target_url = f"http://{target_config.get('address', 'localhost')}:{target_config.get('port', 8001)}/" # Target ADK agent
    client = A2AClient(url=target_url)

    message_payload = Message(
        role="user",
        parts=[TextPart(text="Hello from CrewAI Agent! (Test Message)")]
    )
    task_id = f"task-{uuid.uuid4()}"
    task_params = {
        "id": task_id,
        "message": message_payload.model_dump(exclude_none=True)
    }

    try:
        logger.info(f"Sending test message to {target_url}...")
        response = await client.send_task(task_params)
        logger.info(f"Received response from target agent: {response.model_dump_json()}")
    except Exception as e:
        logger.error(f"Error sending initial message: {e}", exc_info=True)


async def main():
    """Main async function to start the server and send initial message."""
    logger.info("CrewAI Agent starting...")
    config = load_config()

    if not config:
        logger.error("Failed to load configuration. Agent cannot start.")
        return

    agent_id = config.get("agent_id", "default-crewai-agent")
    listen_port = config.get("listen_port", 8002)
    target_config = config.get("target_agent")

    # Define the Agent Card
    agent_card = AgentCard(
        name=agent_id,
        description="A sample agent built with CrewAI speaking A2A.",
        url=f"http://localhost:{listen_port}/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False, stateTransitionHistory=False),
        skills=[AgentSkill(id="basic-chat", name="Basic Chat", description="Handles basic chat interactions.")]
    )

    task_manager = CrewAiTaskManager()

    server = A2AServer(
        host="0.0.0.0",
        port=listen_port,
        agent_card=agent_card,
        task_manager=task_manager
    )

    # Configure and start Uvicorn server
    uvicorn_config = uvicorn.Config(server.app, host="0.0.0.0", port=listen_port, log_level="info")
    uvicorn_server = uvicorn.Server(uvicorn_config)
    server_task = asyncio.create_task(uvicorn_server.serve())

    logger.info(f"A2A server for agent '{agent_id}' starting on port {listen_port}...")

    # Wait for server startup and send message
    await asyncio.sleep(2)
    await send_initial_message(target_config)

    await server_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CrewAI Agent shutting down.")
