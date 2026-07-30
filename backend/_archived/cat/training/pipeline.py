"""
Training Pipeline for the Contextual Availability Transformer (CAT) system.
Handles data loading, training loop, validation, and model checkpointing.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, Subset
from torch.optim.lr_scheduler import LambdaLR, CosineAnnealingLR
import numpy as np

from ..config import settings
from ..models.transformer import CATModel, ModelConfig, create_cat_model
from ..preprocessing.encoders import TensorPreprocessor
from ..data_collection.synthetic_data import SyntheticDataGenerator
from ..models.schemas import HistoricalAvailabilityData, ContextualData, AvailabilityRecord

logger = logging.getLogger(__name__)


class CATDataset(Dataset):
    """
    Dataset for CAT training.
    
    Stores preprocessed contextual data and target availability values.
    """
    
    def __init__(
        self,
        contextual_data: List[ContextualData],
        preprocessor: TensorPreprocessor = None,
        target_utilization: List[float] = None
    ):
        """
        Initialize the dataset.
        
        Args:
            contextual_data: List of contextual data samples
            preprocessor: TensorPreprocessor for encoding data
            target_utilization: Target availability values (1 - utilization_rate)
        """
        self.contextual_data = contextual_data
        self.preprocessor = preprocessor or TensorPreprocessor()
        self.targets = target_utilization or []
        
        # Precompute all inputs for efficiency
        self.inputs = []
        for ctx in contextual_data:
            try:
                # Extract prediction time from historical data
                if ctx.historical_availability.records:
                    pred_time = ctx.historical_availability.records[-1].timestamp
                else:
                    pred_time = ctx.timestamp
                
                # Encode contextual data
                (
                    event_emb, weather_emb,
                    historical_seq, temporal_enc
                ) = self.preprocessor.preprocess(
                    ctx.event_calendar,
                    ctx.weather,
                    ctx.historical_availability,
                    pred_time
                )
                
                # Create model input
                model_input = self.preprocessor.create_model_input(
                    event_emb, weather_emb, historical_seq, temporal_enc
                )
                
                self.inputs.append(model_input)
                
            except Exception as e:
                logger.warning(f"Failed to preprocess sample: {e}")
                # Use zero tensor as fallback
                self.inputs.append(torch.zeros(self._get_input_dim()))
        
        # Generate targets if not provided
        if not self.targets:
            for ctx in contextual_data:
                if ctx.historical_availability.records:
                    # Target is 1 - utilization (availability)
                    utilization = ctx.historical_availability.records[-1].utilization_rate
                    target = 1.0 - utilization
                else:
                    target = 0.5  # Default
                self.targets.append(target)
    
    def _get_input_dim(self) -> int:
        """Get the expected input dimension."""
        return (
            settings.event_embedding_dim +
            settings.weather_embedding_dim +
            settings.historical_sequence_length * settings.event_embedding_dim +
            settings.temporal_encoding_dim
        )
    
    def __len__(self) -> int:
        """Return the number of samples."""
        return len(self.inputs)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get a single sample.
        
        Args:
            idx: Sample index
            
        Returns:
            Tuple of (input_tensor, target_tensor)
        """
        input_tensor = self.inputs[idx]
        target = torch.tensor(self.targets[idx], dtype=torch.float32)
        return input_tensor, target


class CATDataLoader(DataLoader):
    """
    DataLoader for CAT training with configurable batch size and shuffling.
    """
    
    def __init__(
        self,
        dataset: Dataset,
        batch_size: int = None,
        shuffle: bool = True,
        num_workers: int = 0,
        pin_memory: bool = True,
        drop_last: bool = False,
        seed: int = None
    ):
        """
        Initialize the data loader.
        
        Args:
            dataset: Dataset to load from
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle data
            num_workers: Number of worker processes
            pin_memory: Whether to pin memory for faster GPU transfer
            drop_last: Whether to drop last incomplete batch
            seed: Random seed for reproducibility
        """
        batch_size = batch_size or settings.batch_size
        
        # Set random seed for reproducibility if provided
        if seed is not None:
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed(seed)
        
        super().__init__(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=pin_memory,
            drop_last=drop_last,
            collate_fn=self._collate_fn
        )
    
    def _collate_fn(self, batch: List[Tuple[torch.Tensor, torch.Tensor]]) -> Tuple[torch.Tensor, torch.Tensor]:
        """Custom collate function for handling variable-length sequences."""
        inputs = torch.stack([item[0] for item in batch])
        targets = torch.stack([item[1] for item in batch])
        return inputs, targets


class TrainingPipeline:
    """
    Complete training pipeline for the CAT model.
    
    Handles:
    - Data loading and preprocessing
    - Training loop with gradient accumulation
    - Validation and early stopping
    - Learning rate scheduling
    - Model checkpointing
    - Logging and metrics
    """
    
    def __init__(
        self,
        model: CATModel = None,
        config: ModelConfig = None,
        device: str = None,
        experiment_name: str = None
    ):
        """
        Initialize the training pipeline.
        
        Args:
            model: CATModel instance (or None to create new)
            config: Model configuration
            device: Device to train on ('cuda' or 'cpu')
            experiment_name: Name for experiment tracking
        """
        self.device = torch.device(device or ('cuda' if torch.cuda.is_available() else 'cpu'))
        self.experiment_name = experiment_name or f"cat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create model
        self.model = model or create_cat_model(config)
        self.model.to(self.device)
        
        # Training configuration
        self.learning_rate = settings.learning_rate
        self.weight_decay = settings.weight_decay
        self.max_epochs = settings.max_epochs
        self.early_stopping_patience = settings.early_stopping_patience
        self.warmup_steps = settings.warmup_steps
        self.gradient_accumulation_steps = settings.gradient_accumulation_steps
        
        # Loss function (MSE for regression)
        self.criterion = nn.MSELoss()
        
        # Optimizer
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = self._create_scheduler()
        
        # Preprocessor
        self.preprocessor = TensorPreprocessor(device=str(self.device))
        
        # Training state
        self.current_epoch = 0
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        self.train_losses = []
        self.val_losses = []
        
        # Checkpoint directory
        self.checkpoint_dir = Path("checkpoints") / self.experiment_name
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Training pipeline initialized on device: {self.device}")
    
    def _create_scheduler(self):
        """Create learning rate scheduler with warmup and decay."""
        def lr_lambda(step: int) -> float:
            if step < self.warmup_steps:
                return float(step) / float(max(1, self.warmup_steps))
            else:
                # Cosine decay
                progress = float(step - self.warmup_steps) / float(max(1, 10000 - self.warmup_steps))
                return 0.5 * (1.0 + math.cos(math.pi * progress))
        
        return LambdaLR(self.optimizer, lr_lambda)
    
    def prepare_data(
        self,
        contextual_data: List[ContextualData],
        train_ratio: float = None,
        val_ratio: float = None,
        test_ratio: float = None
    ) -> Tuple[CATDataLoader, CATDataLoader, CATDataLoader]:
        """
        Prepare train/val/test data loaders.
        
        Args:
            contextual_data: List of contextual data samples
            train_ratio: Ratio of training data
            val_ratio: Ratio of validation data
            test_ratio: Ratio of test data
            
        Returns:
            Tuple of (train_loader, val_loader, test_loader)
        """
        train_ratio = train_ratio or settings.train_split_ratio
        val_ratio = val_ratio or settings.val_split_ratio
        test_ratio = test_ratio or settings.test_split_ratio
        
        # Normalize ratios
        total = train_ratio + val_ratio + test_ratio
        train_ratio /= total
        val_ratio /= total
        test_ratio /= total
        
        # Create dataset
        dataset = CATDataset(contextual_data, self.preprocessor)
        
        # Split indices
        n_samples = len(dataset)
        indices = list(range(n_samples))
        
        # Shuffle indices
        np.random.seed(42)
        np.random.shuffle(indices)
        
        # Calculate split points
        train_end = int(n_samples * train_ratio)
        val_end = train_end + int(n_samples * val_ratio)
        
        train_indices = indices[:train_end]
        val_indices = indices[train_end:val_end]
        test_indices = indices[val_end:]
        
        # Create subsets
        train_dataset = Subset(dataset, train_indices)
        val_dataset = Subset(dataset, val_indices)
        test_dataset = Subset(dataset, test_indices)
        
        # Create data loaders
        train_loader = CATDataLoader(train_dataset, shuffle=True)
        val_loader = CATDataLoader(val_dataset, shuffle=False)
        test_loader = CATDataLoader(test_dataset, shuffle=False)
        
        logger.info(f"Data prepared: {len(train_dataset)} train, {len(val_dataset)} val, {len(test_dataset)} test")
        
        return train_loader, val_loader, test_loader
    
    def train_epoch(self, train_loader: CATDataLoader) -> float:
        """
        Train for one epoch.
        
        Args:
            train_loader: Training data loader
            
        Returns:
            Average training loss for the epoch
        """
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        for batch_idx, (inputs, targets) in enumerate(train_loader):
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)
            
            # Forward pass
            outputs = self.model(inputs)
            predictions = outputs["probability"]
            
            # Compute loss
            loss = self.criterion(predictions, targets)
            
            # Scale loss for gradient accumulation
            loss = loss / self.gradient_accumulation_steps
            
            # Backward pass
            loss.backward()
            
            # Gradient accumulation
            if (batch_idx + 1) % self.gradient_accumulation_steps == 0:
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                
                # Optimizer step
                self.optimizer.step()
                self.optimizer.zero_grad()
            
            total_loss += loss.item() * self.gradient_accumulation_steps
            num_batches += 1
        
        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        return avg_loss
    
    def validate(self, val_loader: CATDataLoader) -> Dict[str, float]:
        """
        Validate the model.
        
        Args:
            val_loader: Validation data loader
            
        Returns:
            Dictionary of validation metrics
        """
        self.model.eval()
        total_loss = 0.0
        total_samples = 0
        predictions = []
        targets = []
        
        with torch.no_grad():
            for inputs, target_batch in val_loader:
                inputs = inputs.to(self.device)
                target_batch = target_batch.to(self.device)
                
                # Forward pass
                outputs = self.model(inputs)
                pred = outputs["probability"]
                
                # Compute loss
                loss = self.criterion(pred, target_batch)
                
                total_loss += loss.item() * len(target_batch)
                total_samples += len(target_batch)
                
                predictions.extend(pred.cpu().numpy())
                targets.extend(target_batch.cpu().numpy())
        
        avg_loss = total_loss / total_samples if total_samples > 0 else 0.0
        
        # Compute additional metrics
        predictions = np.array(predictions)
        targets = np.array(targets)
        
        mae = np.mean(np.abs(predictions - targets))
        rmse = np.sqrt(np.mean((predictions - targets) ** 2))
        
        metrics = {
            "val_loss": avg_loss,
            "val_mae": mae,
            "val_rmse": rmse
        }
        
        return metrics
    
    def train(
        self,
        train_loader: CATDataLoader,
        val_loader: CATDataLoader = None,
        checkpoint_interval: int = 10
    ) -> Dict[str, List[float]]:
        """
        Complete training loop.
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader (optional)
            checkpoint_interval: Epochs between checkpoints
            
        Returns:
            Dictionary with training history
        """
        logger.info(f"Starting training for {self.max_epochs} epochs...")
        
        for epoch in range(self.max_epochs):
            self.current_epoch = epoch
            
            # Training
            train_loss = self.train_epoch(train_loader)
            self.train_losses.append(train_loss)
            
            # Learning rate step
            self.scheduler.step()
            current_lr = self.scheduler.get_last_lr()[0]
            
            # Validation
            val_metrics = {}
            if val_loader is not None:
                val_metrics = self.validate(val_loader)
                val_loss = val_metrics["val_loss"]
                self.val_losses.append(val_loss)
                
                # Early stopping check
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.patience_counter = 0
                    
                    # Save best model
                    self.save_checkpoint("best_model.pt")
                    logger.info(f"New best model with val_loss: {val_loss:.4f}")
                else:
                    self.patience_counter += 1
                    
                    if self.patience_counter >= self.early_stopping_patience:
                        logger.info(f"Early stopping at epoch {epoch}")
                        break
            else:
                # Save checkpoint periodically if no validation
                if (epoch + 1) % checkpoint_interval == 0:
                    self.save_checkpoint(f"checkpoint_epoch_{epoch + 1}.pt")
            
            # Log progress
            log_msg = f"Epoch {epoch + 1}/{self.max_epochs} - Train Loss: {train_loss:.4f}"
            if val_loader is not None:
                log_msg += f", Val Loss: {val_metrics['val_loss']:.4f}"
            log_msg += f", LR: {current_lr:.2e}"
            
            logger.info(log_msg)
        
        # Save final model
        self.save_checkpoint("final_model.pt")
        
        # Return training history
        return {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses
        }
    
    def save_checkpoint(self, filename: str) -> None:
        """Save model checkpoint."""
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "scheduler_state_dict": self.scheduler.state_dict(),
            "epoch": self.current_epoch,
            "best_val_loss": self.best_val_loss,
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
            "config": {
                "input_dim": settings.event_embedding_dim + settings.weather_embedding_dim + settings.historical_sequence_length * settings.event_embedding_dim + settings.temporal_encoding_dim,
                "embed_dim": settings.model_dim,
                "num_layers": settings.num_layers,
                "num_heads": settings.num_attention_heads,
                "feedforward_dim": settings.feedforward_dim,
                "dropout": settings.dropout_rate
            }
        }
        
        checkpoint_path = self.checkpoint_dir / filename
        torch.save(checkpoint, checkpoint_path)
        logger.info(f"Checkpoint saved to {checkpoint_path}")
    
    def load_checkpoint(self, path: str) -> None:
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        self.current_epoch = checkpoint["epoch"]
        self.best_val_loss = checkpoint["best_val_loss"]
        self.train_losses = checkpoint.get("train_losses", [])
        self.val_losses = checkpoint.get("val_losses", [])
        
        logger.info(f"Checkpoint loaded from {path}, starting at epoch {self.current_epoch}")


def create_data_loaders(
    contextual_data: List[ContextualData],
    batch_size: int = None,
    train_ratio: float = None,
    val_ratio: float = None,
    test_ratio: float = None,
    shuffle: bool = True
) -> Tuple[CATDataLoader, CATDataLoader, CATDataLoader]:
    """
    Convenience function to create data loaders.
    
    Args:
        contextual_data: List of contextual data samples
        batch_size: Batch size
        train_ratio: Training data ratio
        val_ratio: Validation data ratio
        test_ratio: Test data ratio
        shuffle: Whether to shuffle training data
        
    Returns:
        Tuple of (train_loader, val_loader, test_loader)
    """
    pipeline = TrainingPipeline()
    return pipeline.prepare_data(
        contextual_data,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio
    )


def train_model(
    contextual_data: List[ContextualData],
    model: CATModel = None,
    config: ModelConfig = None,
    batch_size: int = None,
    max_epochs: int = None,
    learning_rate: float = None,
    device: str = None
) -> Tuple[CATModel, Dict[str, List[float]]]:
    """
    Convenience function to train a model on contextual data.
    
    Args:
        contextual_data: List of contextual data samples
        model: CATModel instance (or None to create new)
        config: Model configuration
        batch_size: Training batch size
        max_epochs: Maximum training epochs
        learning_rate: Learning rate
        device: Device to train on
        
    Returns:
        Tuple of (trained_model, training_history)
    """
    # Create pipeline
    pipeline = TrainingPipeline(
        model=model,
        config=config,
        device=device
    )
    
    # Override settings if provided
    if batch_size:
        settings.batch_size = batch_size
    if max_epochs:
        settings.max_epochs = max_epochs
    if learning_rate:
        settings.learning_rate = learning_rate
    
    # Prepare data
    train_loader, val_loader, test_loader = pipeline.prepare_data(contextual_data)
    
    # Train
    history = pipeline.train(train_loader, val_loader)
    
    # Load best model
    best_path = pipeline.checkpoint_dir / "best_model.pt"
    if best_path.exists():
        pipeline.load_checkpoint(str(best_path))
    
    return pipeline.model, history


# Example usage
if __name__ == "__main__":
    import math
    from datetime import datetime, timedelta
    
    print("Training CAT Model...")
    
    # Generate synthetic data for training
    print("Generating synthetic training data...")
    generator = SyntheticDataGenerator(
        num_locations=10,
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2024, 1, 1),
        seed=42
    )
    
    # Generate dataset
    historical_data, contextual_data = generator.generate_dataset(num_samples=10000)
    
    print(f"Generated {len(contextual_data)} contextual samples")
    
    # Train model
    model, history = train_model(
        contextual_data=contextual_data,
        batch_size=32,
        max_epochs=10,
        learning_rate=1e-4,
        device="cpu"
    )
    
    print(f"\nTraining complete!")
    print(f"Final train loss: {history['train_losses'][-1]:.4f}")
    if history['val_losses']:
        print(f"Final val loss: {history['val_losses'][-1]:.4f}")
    
    # Test prediction
    print("\nTesting model prediction...")
    test_input = torch.randn(1, (
        settings.event_embedding_dim +
        settings.weather_embedding_dim +
        settings.historical_sequence_length * settings.event_embedding_dim +
        settings.temporal_encoding_dim
    ))
    
    output = model(test_input)
    print(f"Prediction: {output['probability'].item():.3f}")
    print(f"Confidence: [{output['confidence_lower'].item():.3f}, {output['confidence_upper'].item():.3f}]")