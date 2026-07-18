from enum import StrEnum


class AIProvider(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"  # stub only


class CallDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallEndReason(StrEnum):
    HANGUP = "hangup"
    TRANSFER = "transfer"
    ERROR = "error"
    TIMEOUT = "timeout"
    SHUTDOWN = "shutdown"
    ABANDONED = "abandoned"


class SessionStatus(StrEnum):
    CREATED = "created"
    CONNECTING = "connecting"
    ACTIVE = "active"
    TRANSFERRING = "transferring"
    ENDING = "ending"
    ENDED = "ended"
    ERROR = "error"
