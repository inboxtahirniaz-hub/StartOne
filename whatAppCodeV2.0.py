import json
import urllib.request
import os
import pymysql

WHATSAPP_TOKEN  = os.environ['WHATSAPP_TOKEN']
PHONE_NUMBER_ID = os.environ['PHONE_NUMBER_ID']
VERIFY_TOKEN    = os.environ['VERIFY_TOKEN']
GEMINI_API_KEY  = os.environ['GEMINI_API_KEY']
DB_HOST         = os.environ['DB_HOST']
DB_USER         = os.environ['DB_USER']
DB_PASSWORD     = os.environ['DB_PASSWORD']


# ── ONLY NEW FUNCTION ADDED ───────────────────
def get_db_info():
    try:
        conn = pymysql.connect(
            host            = DB_HOST,
            user            = DB_USER,
            password        = DB_PASSWORD,
            ssl             = {'ssl': True},
            connect_timeout = 5
        )
        with conn.cursor() as cursor:
            cursor.execute("SHOW DATABASES;")
            databases = cursor.fetchall()
            cursor.execute("SHOW TABLES FROM MasterSchool;")
            tables = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) as total FROM MasterSchool.MasterStudent;")
            count = cursor.fetchone()
        conn.close()

        db_list    = "\n".join([f"  - {db[0]}" for db in databases])
        table_list = "\n".join([f"  - {t[0]}"  for t in tables])

        return (
            f"MySQL Databases\n"
            f"--------------------------------\n"
            f"{db_list}\n\n"
            f"MasterSchool Tables\n"
            f"--------------------------------\n"
            f"{table_list}\n\n"
            f"Total Students: {count[0]}"
        )
    except Exception as e:
        print(f"DB Error: {e}")
        return f"DB Error: {str(e)}"
# ─────────────────────────────────────────────


def ask_gemini(user_message):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"

    payload = json.dumps({
        "contents": [
            {"parts": [{"text": user_message}]}
        ],
        "systemInstruction": {
            "parts": [{"text": "You are a helpful WhatsApp assistant. Keep replies short, friendly, and plain text only. No markdown, no asterisks."}]
        },
        "generationConfig": {
            "maxOutputTokens": 300,
            "temperature": 0.7
        }
    }).encode('utf-8')

    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return "Sorry, I could not process that right now. Please try again!"


def send_whatsapp_message(to_number, message_text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }).encode('utf-8')

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Error sending message: {e}")
        return None


def send_whatsapp_image(to_number, image_url, caption=""):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }).encode('utf-8')

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Error sending image: {e}")
        return None


def lambda_handler(event, context):
    print("Event received:", json.dumps(event))

    method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    if method == 'GET':
        params    = event.get('queryStringParameters', {}) or {}
        mode      = params.get('hub.mode')
        token     = params.get('hub.verify_token')
        challenge = params.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print("Webhook verified!")
            return {'statusCode': 200, 'body': challenge}
        else:
            return {'statusCode': 403, 'body': 'Forbidden'}

    if method == 'POST':
        body = json.loads(event.get('body', '{}'))

        try:
            value = body['entry'][0]['changes'][0]['value']

            if 'messages' not in value:
                return {'statusCode': 200, 'body': 'OK'}

            msg      = value['messages'][0]
            from_num = msg['from']
            msg_type = msg['type']

            if msg_type == 'text':
                incoming_text = msg['text']['body'].strip().lower()
                print(f"Message from {from_num}: {incoming_text}")

                # ── ONLY NEW LINE ADDED ───────────
                if incoming_text in ['database', 'databases', 'db', 'show databases']:
                    reply = get_db_info()
                    send_whatsapp_message(from_num, reply)
                # ─────────────────────────────────

                elif incoming_text in ['photo', 'image', 'send photo', 'send image']:
                    send_whatsapp_image(
                        from_num,
                        image_url="",
                        caption="Here is your photo! 📸"
                    )

                else:
                    reply = ask_gemini(incoming_text)
                    print(f"Gemini reply: {reply}")
                    send_whatsapp_message(from_num, reply)

            else:
                send_whatsapp_message(from_num, "I can only read text messages for now!")

        except (KeyError, IndexError) as e:
            print(f"Error parsing message: {e}")

        return {'statusCode': 200, 'body': 'OK'}

    return {'statusCode': 405, 'body': 'Method Not Allowed'}
