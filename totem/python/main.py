#!/usr/bin/env python3
"""
Main entry point for the Totem hardware control application.
"""
import os
import sys
import argparse
import uvicorn

from utils.logger import setup_logger, get_logger

def main():
    """
    Main function to start the Totem hardware control application.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Totem hardware control application')
    parser.add_argument('--host', type=str, default='0.0.0.0', 
                        help='Host to listen on (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, 
                        help='Port to listen on (default: 8000)')
    parser.add_argument('--log-level', type=str, default='info',
                        choices=['debug', 'info', 'warning', 'error', 'critical'],
                        help='Logging level (default: info)')
    parser.add_argument('--reload', action='store_true',
                        help='Enable auto-reload for development')
    
    args = parser.parse_args()
    
    # Set up logging
    log_levels = {
        'debug': 10,
        'info': 20,
        'warning': 30,
        'error': 40,
        'critical': 50
    }
    
    log_level = log_levels.get(args.log_level.lower(), 20)
    logger = setup_logger(level=log_level)
    logger.info(f"Starting Totem hardware control application on {args.host}:{args.port}")
    
    # Start FastAPI server
    uvicorn.run(
        "service.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower()
    )

if __name__ == '__main__':
    main()
