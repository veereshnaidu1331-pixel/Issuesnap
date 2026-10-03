import asyncio
import time

import streamlit as st
import requests
from google import genai
from google.genai import types
from telegram import Bot

from prompts import (
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
    SUMMARY_REQUEST_PROMPT,
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="IssueSnap",
    page_icon="🐛",
    layout="centered",
)


# ============================================================
# SECRETS
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]


# ============================================================
# GEMINI CLIENT
# ============================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()

MODEL_NAME = "gemini-3.5-flash"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def add_message(role, message_type, content):
    """Store a message in Streamlit session state."""

    st.session_state.messages.append(
        {
            "role": role,
            "type": message_type,
            "content": content,
        }
    )


def render_message(message):
    """Display a stored message in the chat."""

    with st.chat_message(message["role"]):

        if message["type"] == "text":
            st.write(message["content"])

        elif message["type"] == "image":
            st.image(
                message["content"],
                caption="Uploaded screenshot",
                use_container_width=True,
            )


def ask_gemini(parts):
    """Send the user's screenshot or text to Gemini."""

    max_attempts = 3

    for attempt in range(max_attempts):

        try:
            response = st.session_state.chat.send_message(parts)

            return response.text

        except Exception as error:

            error_text = str(error).upper()

            temporary_error = any(
                code in error_text
                for code in [
                    "503",
                    "UNAVAILABLE",
                    "429",
                    "RESOURCE_EXHAUSTED",
                    "500",
                    "502",
                    "504",
                ]
            )

            if temporary_error and attempt < max_attempts - 1:

                time.sleep(2 ** attempt)

                continue

            if temporary_error:

                st.error(
                    "Gemini is temporarily busy. "
                    "Please try again in a moment."
                )

            else:

                st.error(
                    "I couldn't get a response from Gemini. "
                    "Please try again."
                )

            return None


async def send_telegram_message(message):
    """Send a message to the configured Telegram chat."""

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN
    )

    try:

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )

        return True

    finally:

        await bot.shutdown()


def send_to_telegram(message):
    """Send the generated bug report to Telegram."""

    try:

        return asyncio.run(
            send_telegram_message(message)
        )

    except Exception:

        st.error(
            "I couldn't send the bug report to Telegram. "
            "Please check your Telegram bot token and chat ID."
        )

        return False


# ============================================================
# INITIALIZE SESSION STATE
# ============================================================

if "onboarded" not in st.session_state:

    st.session_state.onboarded = False


if "messages" not in st.session_state:

    st.session_state.messages = []


# ============================================================
# ONBOARDING SCREEN
# ============================================================

if not st.session_state.onboarded:

    st.title("🐛 IssueSnap")

    st.caption(
        "Snap the bug. Get the report."
    )

    st.write(
        "IssueSnap analyzes screenshots of software problems, "
        "error messages, and application issues and turns them "
        "into clear bug reports."
    )

    st.write("")

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name",
        )

        submitted = st.form_submit_button(
            "Let's get started 🚀",
            use_container_width=True,
        )

    if submitted:

        if not name.strip():

            st.warning(
                "Please enter your name."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.chat = (
                gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# MAIN APP HEADER
# ============================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)


with header_col:

    st.title("🐛 IssueSnap")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 1
    )

    if st.button(
        "📤 Send Report",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Creating your final bug report..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        if summary:

            st.session_state.latest_summary = summary

            telegram_sent = send_to_telegram(
                summary
            )

            if telegram_sent:

                st.success(
                    "Bug report created and sent to Telegram! 📤"
                )

            else:

                st.warning(
                    "Bug report created, "
                    "but Telegram delivery failed."
                )


st.caption(
    f"Logged in as {st.session_state.name} "
    "· Upload a screenshot or describe your problem"
)


# ============================================================
# DISPLAY PREVIOUS MESSAGES
# ============================================================

if not st.session_state.messages:

    welcome_message = (
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

    add_message(
        "assistant",
        "text",
        welcome_message,
    )


for message in st.session_state.messages:

    render_message(message)


# ============================================================
# DISPLAY GENERATED REPORT
# ============================================================

if "latest_summary" in st.session_state:

    st.divider()

    st.subheader(
        "🐛 Generated Bug Report"
    )

    st.write(
        st.session_state.latest_summary
    )


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Describe the problem or attach a screenshot",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
    ],
)


# ============================================================
# PROCESS USER INPUT
# ============================================================

if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    gemini_parts = []


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes,
        )

        gemini_parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type,
            )
        )


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text,
        )

        gemini_parts.append(
            text
        )


    # --------------------------------------------------------
    # IMAGE ONLY
    # --------------------------------------------------------

    elif photo is not None:

        gemini_parts.append(
            """
Analyze this screenshot as a software issue.

Identify:

1. What appears to be wrong.
2. Any visible error message.
3. Important technical information.
4. The likely cause, if there is enough evidence.
5. Practical next steps.

Do not invent information that is not visible.

Explain the result clearly for a developer or student.
"""
        )


    # --------------------------------------------------------
    # INVALID INPUT
    # --------------------------------------------------------

    if not gemini_parts:

        st.warning(
            "Please attach a screenshot or describe the problem."
        )

        st.stop()


    # --------------------------------------------------------
    # ASK GEMINI
    # --------------------------------------------------------

    with st.spinner(
        "🔍 Analyzing the issue..."
    ):

        answer = ask_gemini(
            gemini_parts
        )


    # --------------------------------------------------------
    # DISPLAY GEMINI RESPONSE
    # --------------------------------------------------------

    if answer:

        add_message(
            "assistant",
            "text",
            answer,
        )

        st.rerun()