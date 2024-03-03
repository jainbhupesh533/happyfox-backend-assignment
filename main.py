import base64
import os
import json
import pickle
import sqlite3
from typing import List

from dateutil.parser import parse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']
JSON_RULES_FILE = 'rules.json'
DATABASE_FILE = 'mail.db'


class DatabaseService:
	def __init__(self) -> None:
		self.conn = sqlite3.connect(DATABASE_FILE)
		self.cursor = self.conn.cursor()

	def create_table(self):
			self.cursor.execute("""
	            CREATE TABLE IF NOT EXISTS `mail` (
	                `id` integer PRIMARY KEY,
	                `FROM` text NOT NULL,
	                `Date` datetime  NOT NULL,
	                `Subject` text NOT NULL,
	                `To` text NOT NULL,
	                `Content` text NOT NULL
	            );
	        """)

			return True

	def insert_data(self, row_info):
		sql = ''' INSERT INTO `mail` (`id` ,`FROM`,`Date`,`Subject`,`To`,`Content`)
                VALUES(?,?,?,?,?,?) '''
		self.cursor.execute(sql, row_info)
		self.conn.commit()
		return True

	def get_data(self, ):
		self.cursor.execute("SELECT * FROM `mail`")
		rows = self.cursor.fetchall()
		return rows

	def drop_table(self):
		dropTableStatement = "DROP TABLE IF  EXISTS `mail`"
		self.cursor.execute(dropTableStatement)
		return True
	def __del__(self):
		self.drop_table()
		self.cursor.close()
		self.conn.close()


class EmailProcessor:
	def __init__(self):
		self.service, self.user_id, self.label_ids, self.status = self._authenticate_gmail()
		self.db_service = DatabaseService()
		self.db_service.create_table()

	def _authenticate_gmail(self):
		status = True
		creds = None
		if os.path.exists('token.pickle'):
			with open('token.pickle', 'rb') as token:
				creds = pickle.load(token)
		# If there are no (valid) credentials available, let the user log in.
		if not creds or not creds.valid:
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			else:
				flow = InstalledAppFlow.from_client_secrets_file(
					'credentials.json', SCOPES)
				creds = flow.run_local_server(port=0)
			# Save the credentials for the next run
			with open('token.pickle', 'wb') as token:
				pickle.dump(creds, token)

		service = build('gmail', 'v1', credentials=creds)
		print(service)
		# Call the Gmail API
		results = service.users().labels().list(userId='me').execute()
		labels = results.get('labels', [])
		print(labels)
		if not labels:
			print('No labels found.')
			status = False

		user_id = 'me'
		label_ids = ["INBOX"]

		return service, user_id, label_ids, status

	def fetch_emails(self, max_results=10):
		result = self.service.users().messages().list(userId=self.user_id, labelIds=self.label_ids,
		                                              maxResults=max_results).execute()
		messages = result.get('messages', [])

		emails = []
		if messages:
			for message in messages:
				msg_id = message['id']
				full_msg = self.service.users().messages().get(userId=self.user_id, id=msg_id).execute()
				emails.append(full_msg)
		return emails

	def load_rules_from_json(self):
		with open(JSON_RULES_FILE) as f:
			rules = json.load(f)
		return rules

	def save_emails_to_database(self, emails):
		count=0
		for email in emails:
			row_data = []
			message_id = email['id']
			sender = self.get_email_header(email, 'From')
			recipients = self.get_email_header(email, 'To')
			subject = self.get_email_header(email, 'Subject')
			date = self.get_email_header(email, 'Date')
			count += 1
			row_data.extend((count, sender, date, subject, recipients, message_id))
			try:
				self.db_service.insert_data(tuple(row_data))
			except Exception as e:
				print(f"Error inserting email: {e}")

	def get_email_header(self, email, header_name):
		headers = email['payload']['headers']
		for header in headers:
			if header['name'] == 'Date':
				return parse(header['value'])
			elif header['name'] == header_name:
				return header['value']
		return ''

	def process_emails_based_on_rules(self):
		rules = self.load_rules_from_json()
		emails = self.db_service.get_data()
		for email in emails:
			for rule in rules:
				field = rule['Field']
				predicate = rule['Predicate']
				value = rule['Value']
				actions = rule['Actions']
				condition_type = rule.get('Condition', 'All')  # Default to 'All' if not specified

				if condition_type == 'All':
					if self.email_matches_rule(email, field, predicate, value):
						self.apply_actions(actions, email)
						break  # Once actions are applied for this email, break out of the loop
				elif condition_type == 'Any':
					if self.email_matches_rule(email, field, predicate, value):
						self.apply_actions(actions, email)
						break  # Once actions are applied for this email, break out of the loop

	def email_matches_rule(self, email, field, predicate, value):
		if field == 'Subject':
			subject = email[3]  # Subject is at index 3 in the email tuple
			return self.apply_predicate(subject, predicate, value)
		elif field == 'Sender':
			sender = email[1]  # Sender is at index 1 in the email tuple
			return self.apply_predicate(sender, predicate, value)
		# Add conditions for other fields as needed
		return False

	def apply_predicate(self, field_value, predicate, value):
		if predicate == 'contains':
			return value in field_value
		elif predicate == 'not equals':
			return value != field_value
		# Add more predicate conditions as needed
		return False

	def apply_actions(self, actions, email):
		message_id = email[0]  # Message ID is at index 0 in the email tuple
		if 'mark as read' in actions:
			self.mark_as_read(message_id)
		if 'move message' in actions:
			self.move_message(message_id)

	def mark_as_read(self, message_id):
		self.service.users().messages().modify(userId='me', id=message_id,
		                                       body={'removeLabelIds': ['UNREAD']}).execute()

	def move_message(self, message_id):
		# Example: Move to the 'Processed' label
		self.service.users().messages().modify(userId='me', id=message_id,
		                                       body={'addLabelIds': ['Label_Identifier']}).execute()


def main():
	print('Connection Estabilishing----')
	email_processor = EmailProcessor()
	print('User Authenticated')
	# Step 1: Fetch all emails
	if email_processor.status:
		emails = email_processor.fetch_emails(5)
		# Step 2: Save emails in the database
		email_processor.save_emails_to_database(emails)
		print('Saved Mails in DB')
		# Step 3: Process emails based on rules
		email_processor.process_emails_based_on_rules()
		print('Processed mails on DB based on rules')
	print('closing the program')


if __name__ == "__main__":
	main()