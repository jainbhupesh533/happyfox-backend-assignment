import unittest
from unittest.mock import MagicMock
from main import EmailProcessor
import sqlite3
import os


class TestEmailProcessor(unittest.TestCase):
    def setUp(self):
        self.email_processor = EmailProcessor()
        # Create a temporary SQLite database
        self.db_file = 'test_email.db'
        self.conn = sqlite3.connect(self.db_file)
        self.cursor = self.conn.cursor()
        self.create_test_table()

    def create_test_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY,
                message_id TEXT,
                snippet TEXT
            )
        ''')
        self.conn.commit()

    def tearDown(self):
        del self.email_processor
        self.cursor.close()
        self.conn.close()
        # Remove the temporary SQLite database file
        os.remove(self.db_file)

    def test_fetch_emails(self):
        # Mock the service object
        self.email_processor.service.users().messages().list().execute = MagicMock(return_value={'messages': [{'id': '123', 'snippet': 'Test email'}]})
        emails = self.email_processor.fetch_emails()
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]['id'], '123')
        self.assertEqual(emails[0]['snippet'], 'Test email')

    def test_load_rules_from_json(self):
        rules = self.email_processor.load_rules_from_json()
        self.assertIsInstance(rules, list)
        self.assertTrue(all(isinstance(rule, dict) for rule in rules))

    # Add more test cases for other methods like construct_query, process_emails_based_on_rules, apply_actions, mark_as_read, move_message, etc.

if __name__ == '__main__':
    unittest.main()