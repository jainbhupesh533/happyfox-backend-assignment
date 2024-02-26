# Happyfox Backend Assignment

Step 1:
Download the gmail credentials for the link and copy the credentials json to the project directory.

Step 2:
Create a virtual environment and run the following command

```
pip install -r requirements.txt
```
Step 3:
Run the following command

```
python main.py
```
This program will get gmail credentials and fetech last 500 emails and store the data in the sqlite format.

Step 4:
Edit the rule.json file. To create the rules to filter the mails.

Step 5:
Run the following command to run the main file

```
python test_email_processors.py
```

Step 6:
Run the following command to run the main file

```
python main.py
```

This program will modify the mails in the gmail account corresponding to the rules.

Database : SQLITE

credentials.json and token.pickle will store the gmail crenditails so we dont need to login each time. In case to login to another email just delete the token.pickle each time.