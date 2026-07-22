from abc import ABC, abstractmethod

class BaseOrchestrator(ABC):
    """
    Interface definition for input-output conversational orchestrators.
    """
    @abstractmethod
    async def handle_message(self, user_id: int, text: str) -> str:
        """
        Processes message and returns the formatted response.
        """
        pass
