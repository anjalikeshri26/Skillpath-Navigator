from app.ai.groq_client import ChatResult


class FakeAI:
    """Scripted stand-in for GroqClient. Replies are consumed in order so tests can assert on call counts."""

    configured = True
    model = "fake-model"
    fast_model = "fake-fast"

    def __init__(self, chat_replies=(), json_replies=()):
        self.chat_replies = list(chat_replies)
        self.json_replies = list(json_replies)
        self.chat_calls, self.json_calls = [], []

    def chat(self, messages, **kwargs):
        self.chat_calls.append(messages)
        return ChatResult(self.chat_replies.pop(0), self.model)

    def chat_json(self, messages, **kwargs):
        self.json_calls.append(messages)
        return self.json_replies.pop(0)
