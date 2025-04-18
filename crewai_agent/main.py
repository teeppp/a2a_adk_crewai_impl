# CrewAI Agent main script
import yaml
import logging
import uvicorn
import asyncio
import uuid
from functools import partial # For running sync kickoff in thread (if used)
# Assuming we can reuse the common server components
from common.server.server import A2AServer
from common.server.task_manager import TaskManager
from common.types import (
    AgentCard, AgentCapabilities, AgentSkill,
    GetTaskRequest, SendTaskRequest, CancelTaskRequest,
    SetTaskPushNotificationRequest, GetTaskPushNotificationRequest,
    TaskResubscriptionRequest, SendTaskStreamingRequest, JSONRPCResponse,
    Task, TaskStatus, TaskState,
    Message, TextPart
)
from common.client.client import A2AClient # Import the client

# Import CrewAI components
from crewai import Agent, Task as CrewTask, Crew, Process
# LLM is not used in this mock implementation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Task Manager that uses CrewAI structure (mock execution) and sends replies
class CrewAiTaskManager(TaskManager):
    def __init__(self, config):
        self.config = config
        self.client = None # Client will be initialized later

    async def on_get_task(self, request: GetTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTask request: {request.model_dump_json(exclude_none=True)}")
        # Implement task retrieval logic if needed, otherwise return not found
        return JSONRPCResponse(id=request.id, result={"status": "Task not found"}) # Keep as dummy for now

    async def _send_reply(self, original_request: SendTaskRequest):
        """Simulates CrewAI processing and sends an independent reply."""
        try:
            received_message = original_request.params.message
            input_text = received_message.parts[0].text if received_message and received_message.parts and isinstance(received_message.parts[0], TextPart) else ""

            # Infinite loop prevention
            if input_text.startswith("CrewAI processed (mock") or input_text.startswith("ADK received:"):
                 logger.info("Received a reply message, not sending another reply to prevent loop.")
                 return

            # --- Simulate CrewAI processing (Mock) ---
            logger.info(f"Simulating CrewAI processing for task {original_request.params.id}")
            # Define CrewAI structure (Agent, Task, Crew) without LLM
            mock_agent = Agent(role='Mock Processor', goal='Process input', backstory='Mock', verbose=False)
            process_task = CrewTask(description=f'Process: {input_text}', expected_output='Confirmation', agent=mock_agent)
            crew = Crew(agents=[mock_agent], tasks=[process_task], process=Process.sequential)
            try:
                # Run kickoff in executor (might do nothing without LLM, or raise error)
                loop = asyncio.get_running_loop()
                kickoff_func = crew.kickoff
                await loop.run_in_executor(None, kickoff_func)
                result_text = f"CrewAI processed (mock structure, no LLM): Input '{input_text[:30]}...'"
            except Exception as kickoff_error:
                logger.warning(f"CrewAI kickoff failed during reply (expected if no LLM): {kickoff_error}")
                result_text = f"CrewAI processed (mock structure, no LLM): Input '{input_text[:30]}...'. (Kickoff skipped/failed)"
            logger.info(f"CrewAI processing simulation finished for task {original_request.params.id}")
            # --- End Mock CrewAI processing ---

            # Prepare reply message
            reply_message_payload = Message(role="user", parts=[TextPart(text=result_text)])
            reply_task_id = f"reply-{uuid.uuid4()}"
            reply_task_params = {
                "id": reply_task_id,
                "message": reply_message_payload.model_dump(exclude_none=True)
            }

            # Get target info (ADK agent)
            target_config = self.config.get("target_agent")
            if not target_config:
                logger.error("Target agent config not found for sending reply.")
                return
            target_url = f"http://{target_config.get('address', 'localhost')}:{target_config.get('port', 8001)}/"

            # Initialize client if needed
            if self.client is None or self.client.url != target_url:
                 self.client = A2AClient(url=target_url)

            logger.info(f"Sending reply message to {target_url}...")
            reply_response = await self.client.send_task(reply_task_params)
            logger.info(f"Received response for reply message: {reply_response.model_dump_json()}")

        except Exception as e:
            logger.error(f"Error sending reply message: {e}", exc_info=True)


    async def on_send_task(self, request: SendTaskRequest) -> JSONRPCResponse:
        """Handles incoming tasks/send requests."""
        logger.info(f"Received SendTask request: {request.model_dump_json(exclude_none=True)}")

        # Schedule the reply sending in the background
        asyncio.create_task(self._send_reply(request))

        # Immediately return an acknowledgement response in the expected Task format
        ack_status = TaskStatus(state=TaskState.SUBMITTED) # Indicate task is received
        ack_task = Task(id=request.params.id, sessionId=request.params.sessionId, status=ack_status)
        return JSONRPCResponse(id=request.id, result=ack_task)

    async def on_send_task_subscribe(self, request: SendTaskStreamingRequest):
        logger.info(f"Received SendTaskStreaming request: {request.model_dump_json(exclude_none=True)}")
        # Dummy response for now, streaming not implemented in mock
        yield JSONRPCResponse(id=request.id, result={"task_id": request.params.id, "status": "Task received, streaming mock not implemented"})

    async def on_cancel_task(self, request: CancelTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received CancelTask request: {request.model_dump_json(exclude_none=True)}")
        return JSONRPCResponse(id=request.id, result={"status": "Cancel request received (mock)"})

    async def on_set_task_push_notification(self, request: SetTaskPushNotificationRequest) -> JSONRPCResponse:
        logger.info(f"Received SetTaskPushNotification request: {request.model_dump_json(exclude_none=True)}")
        return JSONRPCResponse(id=request.id, result={"status": "Push notification setting received (mock)"})

    async def on_get_task_push_notification(self, request: GetTaskPushNotificationRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTaskPushNotification request: {request.model_dump_json(exclude_none=True)}")
        return JSONRPCResponse(id=request.id, result={"push_notification_endpoint": None}) # Keep as dummy

    async def on_resubscribe_to_task(self, request: TaskResubscriptionRequest):
         logger.info(f"Received TaskResubscription request: {request.model_dump_json(exclude_none=True)}")
         # Dummy response for now
         yield JSONRPCResponse(id=request.id, result={"status": "Resubscription mock not implemented"})


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
        description="A sample agent built with CrewAI (mock execution) speaking A2A.", # Updated description
        url=f"http://localhost:{listen_port}/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False, stateTransitionHistory=False),
        skills=[AgentSkill(id="basic-chat-mock", name="Basic Chat Mock", description="Handles basic chat interactions with mock processing.")] # Updated skill
    )

    task_manager = CrewAiTaskManager(config) # Pass config to TaskManager

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
