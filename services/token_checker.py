import aiohttp
import asyncio

# Simple print-based logging for initialization to avoid circular imports
def log_init(message, level="INFO"):
    print(f"[{level}] {message}")

async def is_bot_running(token: str) -> bool:
    """
    Check if a bot with the given token is already running
    by making a request to the Telegram API.
    
    Args:
        token: The Telegram bot token to check
        
    Returns:
        bool: True if the bot is running, False otherwise
    """
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok", False):
                        # Bot exists and token is valid
                        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                        async with session.get(url) as webhook_response:
                            webhook_info = await webhook_response.json()
                            # If webhook URL is set or there are pending updates, bot might be running
                            if webhook_info.get("ok", False):
                                webhook_data = webhook_info.get("result", {})
                                url = webhook_data.get("url", "")
                                pending_updates = webhook_data.get("pending_update_count", 0)
                                
                                if url or pending_updates > 0:
                                    log_init(f"Bot with token ending in ...{token[-5:]} appears to be running (webhook: {bool(url)}, updates: {pending_updates})")
                                    return True
                                
                            # Check if there is an active getUpdates connection
                            # Let's try to fetch updates with a very short timeout
                            # If bot is already polling, this will likely timeout
                            try:
                                updates_url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=1"
                                async with session.get(updates_url, timeout=2) as updates_response:
                                    # If we got a response immediately, it likely means no one is polling
                                    return False
                            except asyncio.TimeoutError:
                                # Timeout likely means another instance is already polling
                                log_init(f"Bot with token ending in ...{token[-5:]} appears to be running (getUpdates timeout)")
                                return True
                    
                    return False
                else:
                    # Invalid token or API error
                    log_init(f"Couldn't verify bot token ending in ...{token[-5:]}: {response.status}", "WARNING")
                    return False
    except Exception as e:
        log_init(f"Error checking bot token: {e}", "ERROR")
        # In case of error, assume token is not in use to allow the bot to start
        return False

async def check_and_select_tokens(primary_token, alternative_token, service_name="main"):
    """
    Check if a bot with the primary token is running and return the alternative
    token if it is, otherwise return the primary token.
    
    Args:
        primary_token: The primary bot token
        alternative_token: The alternative bot token
        service_name: Name of the service for logging (main or info)
        
    Returns:
        str: The token to use
    """
    is_running = await is_bot_running(primary_token)
    
    if is_running:
        log_init(f"Bot {service_name} with primary token is already running, using alternative token")
        return alternative_token
    else:
        log_init(f"Using primary token for {service_name} bot")
        return primary_token