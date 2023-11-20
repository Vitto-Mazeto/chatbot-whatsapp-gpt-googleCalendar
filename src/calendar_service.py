import os.path
import datetime as dt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json


class GoogleCalendarService:
    def __init__(self, user_number):
        self.SCOPES = ['https://www.googleapis.com/auth/calendar']
        self.tokens_path = 'data\\tokens.json'
        self.credentials_json_path = 'data\\credentials.json'
        self.calendar_id = 'primary'
        self.user_number = user_number

    def _connect_credentials(self):
        creds = None

        # Carregar os tokens do JSON se existirem
        if os.path.exists(self.credentials_json_path):
            with open(self.tokens_path, 'r') as json_file:
                credentials_data = json.load(json_file)

            # Verificar se o número do usuário está no JSON
            user_credentials = credentials_data.get(
                str(self.user_number), None)
            if user_credentials:
                user_credentials_dict = json.loads(user_credentials)
                creds = Credentials.from_authorized_user_info(
                    user_credentials_dict, self.SCOPES)

                # Se as credenciais existentes estiverem expiradas, tente atualizá-las
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())

        # Se as credenciais não existem ou não são válidas, crie-as
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_json_path, self.SCOPES)
            creds = flow.run_local_server(port=0)

            # Adicione ou atualize as credenciais no JSON
            credentials_data[str(self.user_number)] = creds.to_json()

            # Salve as alterações de volta ao arquivo JSON
            with open(self.tokens_path, 'w') as json_file:
                json.dump(credentials_data, json_file)

        return creds

    def create_event(self, summary, start, end, attendees=None, description=None, location=None):
        creds = self._connect_credentials()

        if attendees:
            attendees = [
                {'email': attendee} for attendee in attendees
            ]

        try:
            service = build('calendar', 'v3', credentials=creds,
                            cache_discovery=False)
            print('Conexão com o Google Calendar feita com sucesso!')

            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start,
                    'timeZone': 'America/Sao_Paulo',
                },
                'end': {
                    'dateTime': end,
                    'timeZone': 'America/Sao_Paulo',
                },
                'attendees': attendees,
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }

            event = service.events().insert(calendarId=self.calendar_id, body=event).execute()
            print('Evento criado com sucesso: %s' % (event.get('htmlLink')))
            return f'Evento criado com sucesso: {event.get("htmlLink")}'

        except HttpError as e:
            print('Erro ao conectar com o Google Calendar:', e)
            print('Detalhes:', e.content)
            return f'Erro ao conectar com o Google Calendar: {e.content}'

    def get_next_events(self, events):
        creds = self._connect_credentials()

        try:
            service = build('calendar', 'v3', credentials=creds)
            print('Conexão com o Google Calendar feita com sucesso!')

            now = dt.datetime.utcnow().isoformat() + 'Z'

            print(f'Obtendo os próximos {events} eventos')
            events_result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=now,
                maxResults=events,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            return events

        except HttpError as e:
            print('Erro ao conectar com o Google Calendar:', e)

    def format_next_events(self, events):
        events_string = '📅 Próximos Eventos 📅\n'

        for event in events:
            summary = event.get('summary', 'Sem título')
            start_datetime = event['start'].get('dateTime')
            end_datetime = event['end'].get('dateTime')
            location = event.get('location', None)
            description = event.get('description', None)
            attendees = event.get('attendees', None)

            # Separando data e hora
            start_date, start_time = (
                start_datetime.split('T') if start_datetime else (None, None)
            )
            end_date, end_time = (
                end_datetime.split('T') if end_datetime else (None, None)
            )

            # Formatando a data para "DD/MM/YYYY"
            formatted_start_date = (
                start_date.replace('-', '/').split('/')[::-1]
                if start_date
                else None
            )
            formatted_end_date = (
                end_date.replace('-', '/').split('/')[::-1]
                if end_date and end_date != start_date
                else None
            )

            # Formatando o horário para "HH:MM"
            formatted_start_time = (
                start_time.split(
                    '+')[0].split('-')[0][:5] if start_time else None
            )
            formatted_end_time = (
                end_time.split('+')[0].split('-')[0][:5] if end_time else None
            )

            # Montando a string do evento com informações não nulas
            event_info = f'📌 Título: {summary}\n'
            event_info += (
                f'📅 Data: {"/".join(formatted_start_date)}\n'
                if formatted_start_date
                else ''
            )
            event_info += f'🕒 Hora de Início: {formatted_start_time}\n' if formatted_start_time else ''
            event_info += (
                f'📅 Data de Término: {"/".join(formatted_end_date)}\n'
                if formatted_end_date
                else ''
            )
            event_info += f'🕒 Hora de Término: {formatted_end_time}\n' if formatted_end_time else ''
            event_info += f'📍 Localização: {location}\n' if location else ''
            event_info += f'📝 Descrição: {description}\n' if description else ''
            event_info += f'👥 Participantes: {attendees}\n\n' if attendees else ''

            events_string += '\n' + event_info

        return events_string
