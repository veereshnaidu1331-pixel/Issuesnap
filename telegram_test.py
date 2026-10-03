import requests


BOT_TOKEN = "8967321912:AAGk9z1qSJx1INr292EmqdTCEM34-Td-qq8"


url = (
    f"https://api.telegram.org/"
    f"bot8967321912:AAGk9z1qSJx1INr292EmqdTCEM34-Td-qq8/getUpdates"
)


response = requests.get(
    url,
    timeout=10,
)


data = response.json()


if not data.get("ok"):

    print("❌ Telegram API error:")
    print(data)

else:

    if not data["result"]:

        print("❌ No messages found.")
        print(
            "Open your Telegram bot, press Start, "
            "send /start, and run the file again."
        )

    else:

        for update in data["result"]:

            message = update.get(
                "message",
                {}
            )

            chat = message.get(
                "chat",
                {}
            )

            print(
                "Chat ID:",
                chat.get("id")
            )

            print(
                "Message:",
                message.get("text")
            )