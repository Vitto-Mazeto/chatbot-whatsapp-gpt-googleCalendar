import os
from dotenv import load_dotenv
from assistant_service import AssistantService
from calendar_service import GoogleCalendarService


def main():
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")

    calendar_service = GoogleCalendarService("11996046537")
    assistant_service = AssistantService(api_key, calendar_service=calendar_service)

    thread = assistant_service.create_thread()

    user_message = "Quais são meus proximos 7 eventos?"

    run = assistant_service.send_message_and_run_assistant(
        thread, user_message)

    showAssistantResponse = False

    if (showAssistantResponse):
        run = assistant_service.pool_run_status_response(thread, run)
        assistant_service.display_final_response(thread, run)
    else:
        tool_outputs = assistant_service.pool_run_status_no_response(
            thread, run)
        for output in tool_outputs:
            print(output['output'])


if __name__ == "__main__":
    main()
