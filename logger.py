#This program will accept a sudo webhook when you configure it as http://host_url:hostport/ where host_url and host_port are defined below. 
#Then the program will parse the request and reformat it for pasting into a discord. If you have a better format message, share it.

#Step 1: To run this program you need to install Python3 and do a pip install of Flask and requests
from flask import Flask, request, jsonify
import requests
from urllib.parse import urlparse, unquote, parse_qs

#Step 2: Update the URL where the program is run. The url could just be your server ip ('5.5.5.5') or a proper web host
host_url  = '3.8.24.124'
#Step 3: Update the port. Pick a port on your server and make sure the inbound firewall rule allows access to the port. For security purposes I recommend you restrict the IP that can access it to your server
host_port = 9055

app = Flask(__name__)

def format_discord_message(params):
    formatted_message = "-----\n"
    for key, values in params.items():
        formatted_message += f"{key}: {', '.join(values)}\n"
    return formatted_message

def send_to_discord_webhook(params):
    #Step 4: Copy the discord hook from your channel and put it here
    webhook_url = "https://discord.com/api/webhooks/1151830238557372517/ynPtb1NjIetGXKpXin6bIOW3W9siwIn98rDsBODfUYw93dW9PhLLekDyrjLBhuwE1dpT"
    #After step 4 you should be able to run the program.

    formatted_message = format_discord_message(params)
    payload = {"content": formatted_message}
    response = requests.post(webhook_url, json=payload)

    print(f"Webhook Response: {response.status_code} {response.content.decode()}")

    if response.status_code == 204:
        return "Parameters sent to Discord webhook successfully"
    else:
        return "Failed to send parameters to Discord webhook"

@app.route('/', methods=['GET'])
def handle_request():
    url = request.url
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # Ensure query_params is not empty
    if not query_params:
        return "Query parameters are empty"

    # Extract the individual query parameters if needed. The try excepts probably are not necessary but I didnt want a bad url to break the program
    try:
        date = query_params.get('date', [''])[0]
    except:
        print("date retrieval failed")
    try:
        steam_id = query_params.get('steamId', [''])[0]
    except:
        print("steamId retrieval failed")
    try:
        char_name = query_params.get('charName', [''])[0]
    except:
        print("charName retrieval failed")
    try:
        act_name = query_params.get('actName', [''])[0]
    except:
        print("actName retrieval failed")
    try:
        event_id = query_params.get('eventId', [''])[0]
    except:  
        print("eventId retrieval failed") 
    try:
        event_category = query_params.get('eventCategory', [''])[0]
    except:
        print("eventCategory retrieval failed")
    try:
        event_type = query_params.get('eventType', [''])[0]
    except:
        print("eventType retrieval failed")
    try:
        params = query_params.get('params', [''])[0]
    except:
        print("params retrieval failed")

    # Print the query_params
    print(f"Query parameters: {query_params}")

    # Send the parameters to Discord webhook
    result = send_to_discord_webhook(query_params)

    return result


if __name__ == '__main__':
    app.run(host=host_url, port=host_port)
