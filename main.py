import os
import json
import sqlite3
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']
JSON_RULES_FILE = 'rules.json'
DATABASE_FILE = 'emails.db'


class EmailProcessor:
	def __init__(self):
		self.conn = sqlite3.connect(DATABASE_FILE)
		self.cursor = self.conn.cursor()
		self.service = self._authenticate_gmail()
		self.create_emails_table()

	def _authenticate_gmail(self):
		creds = None
		if os.path.exists('token.json'):
			creds = Credentials.from_authorized_user_file('token.json')
		if not creds or not creds.valid:
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			else:
				flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
				creds = flow.run_local_server(port=0)
			with open('token.json', 'w') as token:
				token.write(creds.to_json())

		return build('gmail', 'v1', credentials=creds)

	def fetch_emails(self, max_results=20):
		result = self.service.users().messages().list(userId='me', maxResults=max_results).execute()
		messages = result.get('messages', [])
		return messages

	def load_rules_from_json(self):
		with open(JSON_RULES_FILE) as f:
			rules = json.load(f)
		return rules

	def create_emails_table(self):
		self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                message_id TEXT,
                snippet TEXT
            )
        ''')
		self.conn.commit()

	def process_emails_based_on_rules(self):
		rules = self.load_rules_from_json()
		for rule in rules:
			field = rule['Field']
			predicate = rule['Predicate']
			value = rule['Value']
			condition_type = rule['Condition']
			actions = rule['Actions']

			query = self.construct_query(field, predicate, value)
			self.cursor.execute(query)
			emails_to_process = self.cursor.fetchall()

			if condition_type == 'All':
				if all(email for email in emails_to_process):
					self.apply_actions(actions, emails_to_process)
			elif condition_type == 'Any':
				if any(email for email in emails_to_process):
					self.apply_actions(actions, emails_to_process)

	def construct_query(self, field, predicate, value):
		if field == 'From':
			if predicate == 'Contains':
				return f"SELECT * FROM emails WHERE message_id LIKE '%{value}%'"
			elif predicate == 'Does not Contain':
				return f"SELECT * FROM emails WHERE message_id NOT LIKE '%{value}%'"
			elif predicate == 'Equals':
				return f"SELECT * FROM emails WHERE message_id = '{value}'"
			elif predicate == 'Does not equal':
				return f"SELECT * FROM emails WHERE message_id != '{value}'"

	def apply_actions(self, actions, emails):
		for email in emails:
			if 'Mark as Read' in actions:
				self.mark_as_read(email['message_id'])
			if 'Move Message' in actions:
				self.move_message(email['message_id'], rule['Destination'])

	def mark_as_read(self, message_id):
		self.service.users().messages().modify(userId='me', id=message_id,
		                                       body={'removeLabelIds': ['UNREAD']}).execute()

	def move_message(self, message_id, destination):
		self.service.users().messages().modify(userId='me', id=message_id,
		                                       body={'addLabelIds': [destination]}).execute()

	def __del__(self):
		self.cursor.close()
		self.conn.close()


def main():
	email_processor = EmailProcessor()
	emails = email_processor.fetch_emails()
	email_processor.process_emails_based_on_rules()


if __name__ == "__main__":
	main()