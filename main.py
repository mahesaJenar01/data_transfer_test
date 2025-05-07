import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Import modules from our new structure
from src.api import api_router
from src.utils.ngrok import start_ngrok #
from src.utils.logger import setup_logger #
from src.services.token_service import TokenManager #
from src.api.sse import notify_clients, shutdown_event
from src.services.authentication import create_service #
from src.spreadsheets.use_sheet import update_use_sheet #
from src.services.config_service import MultiConfigCache# 
from src.config.settings import API_HOST, API_PORT, NGROK_ENABLED

# Create logger
logger = setup_logger('main', 'INFO')

# Initialize FastAPI application
app = FastAPI(
    title='Multi-Sheet Data Transfer',
    description='An API that transfers data across multiple spreadsheets.',
    version='2.0.0'
)

# Add shutdown event handler
@app.on_event("shutdown")
async def shutdown_event_handler():
    logger.info("Application shutdown initiated, stopping background tasks")
    shutdown_event.set()
    # Give background tasks a moment to terminate gracefully
    await asyncio.sleep(1)

# Background task for checking expired configurations
async def check_expired_configurations(config_cache, service):
    """Periodically check for and delete expired configurations."""
    try:
        logger.info(f"Starting background task to check for expired configurations")
        while not shutdown_event.is_set():
            try:
                # Wait but allow for cancellation
                await asyncio.wait_for(
                    shutdown_event.wait(), 
                    timeout=config_cache.expiration_minutes * 30
                )
                # If we get here, shutdown was requested
                break
            except asyncio.TimeoutError:
                # Normal timeout - continue with our task
                pass
                
            logger.debug("Checking for expired configurations")
            deleted_configs = config_cache.delete_expired_configs()
            
            if deleted_configs:
                # Get the names of all currently configured sheets
                sheet_configs = config_cache.get_all_sheet_configs()
                sheet_names = [config.get("sheet_name") for config in sheet_configs if config.get("sheet_name")]
                
                # Update the Use sheet with updated sheet names
                update_use_sheet(service, sheet_names=sheet_names)
                
                # Notify clients about the configuration update
                await notify_clients("config_updated", {
                    "deleted_configs": [name for _, name in deleted_configs]
                })
                
                logger.info(f"Deleted {len(deleted_configs)} expired configurations")
            
    except asyncio.CancelledError:
        logger.info("Expired configurations check task cancelled")
    except Exception as e:
        logger.error(f"Error in expired configurations check: {e}")
        if not shutdown_event.is_set():
            # Only restart if we're not shutting down
            logger.info("Restarting expired configurations check task")
            config_cache = MultiConfigCache()
            service = create_service()
            asyncio.create_task(check_expired_configurations(config_cache, service))

@app.on_event("startup")
async def startup_event():
    """Run at startup to initialize necessary components"""
    # Create Google service
    service = create_service()
    if not service:
        logger.error("Failed to create Google service, application cannot start")
        import sys
        sys.exit(1)
        
    # Initialize config cache
    config_cache = MultiConfigCache()
    
    # Get USE_SHEET_ID from environment variables
    use_sheet_id = os.getenv('USE_SHEET_ID')
    if not use_sheet_id:
        logger.error('USE_SHEET_ID not found in environment variables')
        import sys
        sys.exit(1)
        
    # Initialize token manager
    token_manager = TokenManager(service, use_sheet_id)
    
    # Generate authentication tokens
    tokens = token_manager.generate_tokens(count=3, length=12)
    logger.info(f"Generated {len(tokens)} authentication tokens")
    
    # Write tokens to Use Sheet (B3, B4, B5)
    token_manager.write_tokens_to_sheet(tokens)
    
    # Update Use sheet with all sheet names from configurations
    sheet_configs = config_cache.get_all_sheet_configs()
    sheet_names = [config.get("sheet_name") for config in sheet_configs if config.get("sheet_name")]
    if sheet_names:
        update_use_sheet(service, sheet_names=sheet_names)
    
    # Start the background task for checking expired configurations
    asyncio.create_task(check_expired_configurations(config_cache, service))
    
    logger.info("Application startup complete")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include the API routes
app.include_router(api_router)

# Main entry point
if __name__ == '__main__':
    import uvicorn
    
    # Start ngrok tunnel if enabled
    ngrok_tunnel = None
    if NGROK_ENABLED:
        try:
            ngrok_tunnel = start_ngrok()
            
            # Create service to update Use sheet with ngrok URL
            service = create_service()
            if service:
                update_use_sheet(service, api_url=ngrok_tunnel.public_url)
                logger.info(f"Updated use sheet with ngrok URL: {ngrok_tunnel.public_url}")
        except Exception as e:
            logger.error(f"Failed to start ngrok tunnel: {e}")
    
    try:
        # Start the FastAPI application with a shutdown timeout
        uvicorn.run(
            app, 
            host=API_HOST, 
            port=API_PORT, 
            timeout_keep_alive=5, 
            timeout_graceful_shutdown=10
        )
    finally:
        # Clean up the ngrok tunnel when the application exits
        if ngrok_tunnel:
            from pyngrok import ngrok
            ngrok.kill()
            logger.info("Application shutdown complete, ngrok tunnel closed")