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

	def save_emails_to_database(self, emails):
		for email in emails:
			message_id = email['id']
			snippet = email.get('snippet', '')
			self.cursor.execute('''
                INSERT INTO emails (message_id, snippet)
                VALUES (?, ?)
            ''', (message_id, snippet))
		self.conn.commit()

	def process_emails_based_on_rules(self):
		rules = self.load_rules_from_json()
		self.cursor.execute('SELECT * FROM emails')
		emails = self.cursor.fetchall()
		for email in emails:
			for rule in rules:
				field = rule['Field']
				predicate = rule['Predicate']
				value = rule['Value']
				actions = rule['Actions']
				condition_type = rule.get('Condition', 'All')  # Default to 'All' if not specified

				if condition_type == 'All':
					if all(self.email_matches_rule(email, field, predicate, value) for email in emails):
						self.apply_actions(actions, email)
						break  # Once actions are applied for this email, break out of the loop
				elif condition_type == 'Any':
					if any(self.email_matches_rule(email, field, predicate, value) for email in emails):
						self.apply_actions(actions, email)
						break  # Once actions are applied for this email, break out of the loop

	def email_matches_rule(self, email, field, predicate, value):
		snippet = email[2]  # Snippet is at index 2 in the email tuple
		if predicate == 'Contains':
			return value in snippet
		elif predicate == 'Does not Contain':
			return value not in snippet
		elif predicate == 'Equals':
			return value == snippet
		elif predicate == 'Does not equal':
			return value != snippet
		return False

	def apply_actions(self, actions, email):
		message_id = email[1]  # Message ID is at index 1 in the email tuple
		if 'Mark as Read' in actions:
			self.mark_as_read(message_id)
		if 'Move Message' in actions:
			self.move_message(message_id, email['Destination'])

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

	# Step 1: Fetch all emails
	emails = email_processor.fetch_emails()

	# Step 2: Save emails in the database
	email_processor.save_emails_to_database(emails)

	# Step 3: Process emails based on rules
	email_processor.process_emails_based_on_rules()


if __name__ == "__main__":
	main()