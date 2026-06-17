import sys
import signal
from loguru import logger
from src.queue.consumer import GradingConsumer

consumer_instance = None

def signal_handler(sig, frame):
    logger.info("Graceful shutdown requested...")
    if consumer_instance:
        consumer_instance.stop_consuming()
    sys.exit(0)

def main():
    global consumer_instance
    
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, format="{time} {level} {message}", level="INFO")
    
    logger.info("Starting Platform Workers Service...")
    
    # Handle graceful shutdowns
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        consumer_instance = GradingConsumer()
        
        # Warmup phase: Pre-pull common images
        logger.info("Performing warmup: Pre-pulling common Docker images...")
        consumer_instance.executor.pre_pull_images()
        
        consumer_instance.start_consuming()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
