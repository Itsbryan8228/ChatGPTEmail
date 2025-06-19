# ChatGPTEmail (ChatGPT Email Bot)

This script that lets you send an email and get a response from ChatGPT using the OpenAI API. It checks a Gmail inbox for new messages, reads the prompt, sends it to OpenAI, and replies back with the result.

## Features

- Whitelist system
- Keeps separate conversations for each sender
- If the subject of the email is "new", it starts a new conversation
- Supports basic file attachments:
  - `.txt`, `.pdf`, `.docx` for reading text
  - `.png`, `.jpg`, `.jpeg`, `.webp` for images
- logs stuff to the console

## Requirements

- Python🤯🤯🤯🤯 (3.8 or newer)
- An OpenAI API key
- Gmail account with 2FA and app password set up

## How to use

Run:
pip install -r requirements.txt

Then:
fill out the .env with your creds.
replace 'youremail@example.com' with your whitelisted email(s)
then run the script✅


also making the subject line 'new' starts a new chat/conversation.


