import openai
import os
import json
import time
from dotenv import load_dotenv
from calendar_service import GoogleCalendarService


class AssistantService:
    def __init__(self, api_key, calendar_service):
        self.client = openai.Client(api_key=api_key)
        self.calendar_service = calendar_service
        self.assistant_id_file = ".\\data\\assistant_id.txt"
        self.assistant = self._initialize_assistant()

    def _initialize_assistant(self):
        if os.path.exists(self.assistant_id_file):
            with open(self.assistant_id_file, "r") as f:
                assistant_id = f.read().strip()
        else:
            assistant_id = self._create_assistant()
            with open(self.assistant_id_file, "w") as f:
                print('Created Assistant ID: ', assistant_id)
                f.write(assistant_id)

        return self.client.beta.assistants.retrieve(assistant_id)

    def _create_assistant(self):
        print("----- creating assistant -----")
        assistant = self.client.beta.assistants.create(
            name="Assistente Pessoal",
            description="Assistente pessoal de agendamento de reuniões e coleta de informações de próximas reuniões com conexão ao Google Calendar",
            instructions="Seja gentil e respeitoso, agende reuniões e colete informações de reuniões futuras, sua função é também montar as funções que permitam chamar as funções e não falar sobre tópico algum que não seja relacionado a eventos",
            model="gpt-3.5-turbo-1106",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "create_event",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "O título do evento"
                                },
                                "start": {
                                    "type": "string",
                                    "description": "O horário de início do evento"
                                },
                                "end": {
                                    "type": "string",
                                    "description": "O horário de fim do evento"
                                },
                                "attendees": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "Os participantes do evento e.g. ['email@email1.com', 'email@email2.com']. Esse parametro só vai ser preenchido caso seja explicitado algum email na mensagem, se não ele é nulo"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "A descrição do evento"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "O local do evento"
                                }
                            },
                            "required": [
                                "summary",
                                "start",
                                "end"
                            ]
                        },
                        "description": "Uma função que permite criar um evento no Google Calendar"
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_next_events",
                        "description": "Uma função que permite obter os próximos eventos do Google Calendar",
                        "parameters": {
                            "type": "object",
                            "properties": {"events": {"type": "number", "description": "O número de eventos a serem obtidos"}},
                            "required": [],
                        },
                    },
                },
            ],
        )
        return assistant.id

    def create_thread(self):
        print("----- creating thread -----")
        return self.client.beta.threads.create()

    def send_message_and_run_assistant(self, thread, message):
        print("----- sending message and running assistant -----")
        message = self.client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=message)

        print("Running assistant to process the message")

        instructions = f"Seja atencioso e respeitoso, se atente a agendar reuniões e coletar informações de reuniões futuras, sua função é também montar as funções que permitam chamar as funções e não falar sobre tópico algum que não seja relacionado a eventos. Horário e dia atual: {time.strftime('%H:%M:%S %d/%m/%Y')}. Somente coloque atendees caso tenha um email explicitamente escrito no texto, se não, coloque na descrição e no titulo."

        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant.id,
            instructions=instructions)
        return run

    def pool_run_status_response(self, thread, run):
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id)

            if run.status in ['completed', 'failed', 'cancelled']:
                break

            elif run.status == "requires_action":
                self.handle_required_actions(thread, run)

            else:
                print('waiting for the assistant to process')
                time.sleep(2)
        return run

    def pool_run_status_no_response(self, thread, run):
        while True:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id)

            if run.status in ['completed', 'failed', 'cancelled']:
                break

            elif run.status == "requires_action":
                return self.execute_custom_functions(thread, run)

            else:
                print('waiting for the assistant to process')
                time.sleep(2)
        return run

    def collect_required_actions(self, thread, run):
        print('run requires action, preparing to call the required functions')
        required_actions = run.required_action.submit_tool_outputs

    def execute_custom_functions(self, thread, run):
        tool_outputs = []

        required_actions = run.required_action.submit_tool_outputs

        # call the required custom functions and prepare the outputs
        for action in required_actions.tool_calls:
            function_name = action.function.name
            arguments = json.loads(action.function.arguments)
            if function_name == 'create_event':
                output = self.calendar_service.create_event(
                    summary=arguments.get("summary", None),
                    start=arguments.get("start", None),
                    end=arguments.get("end", None),
                    attendees=arguments.get("attendees", None),
                    description=arguments.get("description", None),
                    location=arguments.get("location", None),
                )
            elif function_name == 'get_next_events':
                events = self.calendar_service.get_next_events(
                    events=arguments.get("events", None))
                output = self.calendar_service.format_next_events(events)
            else:
                raise ValueError(f"Unknown function name {function_name}")

            print(
                f"calling custom function {function_name} with arguments {arguments}, output: {output}")
            tool_outputs.append(
                {"tool_call_id": action.id, "function_name": function_name, "output": output})

        return tool_outputs

    def submit_tool_outputs(self, thread, run, tool_outputs):
        # submit the outputs to the assistant
        print("submitting the outputs to the assistant")
        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)
        print("Functions outputs submitted")

    def handle_required_actions(self, thread, run):
        self.collect_required_actions(thread, run)
        tool_outputs = self.execute_custom_functions(thread, run)
        self.submit_tool_outputs(thread, run, tool_outputs)

    def display_final_response(self, thread, run):
        messages = self.client.beta.threads.messages.list(thread_id=thread.id)
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=thread.id, run_id=run.id)

        print("Displaying conversation:")
        for message in messages.data:
            print(
                f"{message.role.capitalize()}: {message.content[0].text.value}")


