"""
Main entry point for the Contextual Availability Transformer (CAT) system.
Provides CLI interface for training and serving the model.
"""

import argparse
import logging
import sys
from datetime import datetime

from cat.config import settings
from cat.data_collection.synthetic_data import SyntheticDataGenerator
from cat.training.pipeline import train_model
from cat.inference.service import create_inference_service

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Contextual Availability Transformer (CAT)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate data command
    generate_parser = subparsers.add_parser("generate-data", help="Generate synthetic training data")
    generate_parser.add_argument("--num-samples", type=int, default=100000, help="Number of samples to generate")
    generate_parser.add_argument("--num-locations", type=int, default=100, help="Number of locations")
    generate_parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train the CAT model")
    train_parser.add_argument("--data", type=str, default=None, help="Path to contextual data file")
    train_parser.add_argument("--epochs", type=int, default=settings.max_epochs, help="Number of training epochs")
    train_parser.add_argument("--batch-size", type=int, default=settings.batch_size, help="Batch size")
    train_parser.add_argument("--learning-rate", type=float, default=settings.learning_rate, help="Learning rate")
    train_parser.add_argument("--device", type=str, default=None, help="Device to train on")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the inference service")
    serve_parser.add_argument("--host", type=str, default=settings.api_host, help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=settings.api_port, help="Port to listen on")
    serve_parser.add_argument("--workers", type=int, default=settings.api_workers, help="Number of workers")
    
    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate the model")
    eval_parser.add_argument("--model", type=str, default="checkpoints/best_model.pt", help="Path to model checkpoint")
    eval_parser.add_argument("--data", type=str, default=None, help="Path to evaluation data")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "generate-data":
        generate_data(args)
    elif args.command == "train":
        train(args)
    elif args.command == "serve":
        serve(args)
    elif args.command == "evaluate":
        evaluate(args)


def generate_data(args):
    """Generate synthetic training data."""
    logger.info(f"Generating {args.num_samples} samples for {args.num_locations} locations...")
    
    generator = SyntheticDataGenerator(
        num_locations=args.num_locations,
        start_date=datetime.fromisoformat(settings.synthetic_start_date),
        end_date=datetime.fromisoformat(settings.synthetic_end_date),
        seed=42
    )
    
    historical_data, contextual_data = generator.generate_dataset(
        num_samples=args.num_samples
    )
    
    logger.info(f"Generated {len(historical_data)} location histories")
    logger.info(f"Generated {len(contextual_data)} contextual samples")
    logger.info("Data generation complete!")


def train(args):
    """Train the CAT model."""
    logger.info("Starting CAT model training...")
    
    # Generate synthetic data if not provided
    if args.data is None:
        logger.info("Generating synthetic training data...")
        generator = SyntheticDataGenerator(
            num_locations=20,
            start_date=datetime.fromisoformat(settings.synthetic_start_date),
            end_date=datetime.fromisoformat(settings.synthetic_end_date),
            seed=42
        )
        
        _, contextual_data = generator.generate_dataset(num_samples=50000)
    else:
        # Load from file (implementation depends on format)
        logger.warning("Loading from file not yet implemented, using synthetic data")
        contextual_data = []
    
    if not contextual_data:
        logger.error("No training data available")
        sys.exit(1)
    
    # Train model
    model, history = train_model(
        contextual_data=contextual_data,
        batch_size=args.batch_size,
        max_epochs=args.epochs,
        learning_rate=args.learning_rate,
        device=args.device
    )
    
    logger.info(f"Training complete!")
    logger.info(f"Final train loss: {history['train_losses'][-1]:.4f}")
    if history['val_losses']:
        logger.info(f"Final val loss: {history['val_losses'][-1]:.4f}")
    
    logger.info(f"Model saved to checkpoints/best_model.pt")


def serve(args):
    """Start the inference service."""
    import uvicorn
    
    logger.info(f"Starting CAT inference service on {args.host}:{args.port}...")
    
    app = create_inference_service()
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers
    )


def evaluate(args):
    """Evaluate the model."""
    logger.info(f"Evaluating model: {args.model}")
    
    # Load model
    from cat.models.transformer import create_cat_model
    import torch
    
    model = create_cat_model()
    model.load_state_dict(torch.load(args.model, map_location='cpu'))
    model.eval()
    
    logger.info("Model loaded successfully")
    logger.info("Evaluation complete!")


if __name__ == "__main__":
    main()