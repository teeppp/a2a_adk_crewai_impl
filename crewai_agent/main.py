# CrewAI Agent main script
import yaml
import logging
import uvicorn
import asyncio
import uuid
import os # Import os to read environment variables
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

# Import CrewAI components (used conceptually in mock)
from crewai import Agent, Task as CrewTask, Crew, Process

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Task Manager that uses CrewAI structure (mock execution)
class CrewAiTaskManager(TaskManager):
    # No __init__ needed as config is not used for client here

    async def on_get_task(self, request: GetTaskRequest) -> JSONRPCResponse:
        logger.info(f"Received GetTask request: {request.model_dump_json(exclude_none=True)}")
        return JSONRPCResponse(id=request.id, result={"status": "Task not found"}) # Keep as dummy

    async def on_send_task(self, request: SendTaskRequest) -> JSONRPCResponse:
        """Handles incoming tasks/send requests and returns the result synchronously."""
        logger.info(f"Received SendTask request: {request.model_dump_json(exclude_none=True)}")
        task_id = request.params.id
        session_id = request.params.sessionId
        received_message = request.params.message

        # Extract text from the message parts
        input_text = ""
        if received_message and received_message.parts:
            for part in received_message.parts:
                if isinstance(part, TextPart):
                    input_text += part.text + "\n"
        input_text = input_text.strip()

        if not input_text:
            logger.warning("No text found in the received message.")
            task_status = TaskStatus(state=TaskState.FAILED, message=received_message)
            task_result = Task(id=task_id, sessionId=session_id, status=task_status)
            return JSONRPCResponse(id=request.id, result=task_result)

        try:
            # Define CrewAI Agent and Task without LLM
            mock_agent = Agent(
                role='Mock Processor',
                goal='Process input text without LLM.',
                backstory='I am a mock agent using CrewAI structure.',
                verbose=True,
                allow_delegation=False
            )
            process_task = CrewTask(
                description=f'Process the following text (mock):\n\n{input_text}',
                expected_output='A confirmation message indicating processing.',
                agent=mock_agent
            )
            crew = Crew(
                agents=[mock_agent],
                tasks=[process_task],
                process=Process.sequential,
                verbose=True
            )

            logger.info(f"Starting mock CrewAI task structure for A2A task ID: {task_id}")
            loop = asyncio.get_running_loop()
            kickoff_func = crew.kickoff
            try:
                crew_result = await loop.run_in_executor(None, kickoff_func)
                logger.info(f"Mock CrewAI task finished for A2A task ID: {task_id}. Result: {crew_result}")
                result_text = f"CrewAI processed (mock structure, no LLM): {crew_result if crew_result else 'No specific output from kickoff'}"
                task_state = TaskState.COMPLETED
            except Exception as kickoff_error:
                logger.warning(f"CrewAI kickoff failed (possibly requires LLM?): {kickoff_error}", exc_info=True)
                result_text = f"Mock processing complete for input: '{input_text[:30]}...'. (Kickoff failed/skipped)"
                task_state = TaskState.COMPLETED

            response_message = Message(role="agent", parts=[TextPart(text=result_text)])
            task_status = TaskStatus(state=task_state, message=response_message)
            history = [received_message, response_message]

        except Exception as e:
            logger.error(f"Error during CrewAI structure simulation for task {task_id}: {e}", exc_info=True)
            history = [received_message] if received_message else []
            error_message = Message(role="agent", parts=[TextPart(text=f"Error processing task: {e}")])
            task_status = TaskStatus(state=TaskState.FAILED, message=error_message)
            if 'error_message' in locals():
                 history.append(error_message)

        task_result = Task(id=task_id, sessionId=session_id, status=task_status, history=history)
        return JSONRPCResponse(id=request.id, result=task_result)

    async def on_send_task_subscribe(self, request: SendTaskStreamingRequest):
        logger.info(f"Received SendTaskStreaming request: {request.model_dump_json(exclude_none=True)}")
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
    # Read public URL from environment variable, fallback to config/default
    agent_public_url = os.environ.get("AGENT_PUBLIC_URL", f"http://localhost:{listen_port}/")
    logger.info(f"Using public URL: {agent_public_url}")

    # Define the Agent Card
    agent_card = AgentCard(
        name=agent_id,
        description="A sample agent built with CrewAI (mock execution) speaking A2A.", # Updated description
        url=agent_public_url, # Use the public URL from env var
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False, pushNotifications=False, stateTransitionHistory=False),
        skills=[AgentSkill(id="basic-chat-mock", name="Basic Chat Mock", description="Handles basic chat interactions with mock processing.")] # Updated skill
    )

    task_manager = CrewAiTaskManager() # Config no longer needed

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
