import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from app.middlewares.rate_limit import rate_limit, _user_history

@pytest.mark.asyncio
async def test_rate_limiter_basic() -> None:
    # Set up mock handler
    handler_called = False
    
    @rate_limit
    async def mock_handler(update, context):
        nonlocal handler_called
        handler_called = True
        return "handler_executed"
        
    # Set up mock update & context objects
    update = MagicMock()
    update.effective_user.id = 99999
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    
    # Ensure starting with empty tracking list
    if 99999 in _user_history:
        del _user_history[99999]
        
    # First request: Allowed
    await mock_handler(update, context)
    assert handler_called is True
    
    # Second request: Allowed (since threshold is 2 req/sec)
    handler_called = False
    await mock_handler(update, context)
    assert handler_called is True
    
    # Third request in same second: Blocked
    handler_called = False
    await mock_handler(update, context)
    assert handler_called is False
    update.message.reply_text.assert_called_with("⚠️ Slow down! Please wait a moment.")
