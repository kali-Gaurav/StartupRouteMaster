"""
Training Pipeline for CAT.

This module handles model training:
- Data loading and preprocessing
- Training loop with early stopping
- Learning rate scheduling
- Model checkpointing
- MLflow integration
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
import mlflow
import mlflow.pytorch
from datetime import datetime
import os

from .data_models import AvailabilityRecord, ContextualFactors
from .preprocessing import PreprocessingModule, PreprocessingConfig
from .model import CATModel, ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    batch_size: int = 32
    learning_rate: float = 0.001
    num_epochs: int = 100
    early_stopping_patience: int = 10
    validation_split: float = 0.1
    test_split: float = 0.1
    max_sequence_length: int = 24
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'


class AvailabilityDataset(Dataset):
    """Dataset for availability prediction."""
    
    def __init__(
        self,
        records: List[AvailabilityRecord],
        preprocessing: PreprocessingModule,
        max_length: int = 24,
    ):
        """
        Initialize the dataset.
        
        Args:
            records: List of AvailabilityRecord objects
            preprocessing: PreprocessingModule for encoding
            max_length: Maximum sequence length
        """
        self.records = records
        self.preprocessing = preprocessing
        self.max_length = max_length
        
        # Create a simple preprocessing for training
        self.simple_preprocessing = SimplePreprocessing(max_length)
    
    def __len__(self) -> int:
        return len(self.records)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get a single sample."""
        record = self.records[idx]
        
        # Create simple input tensor
        input_tensor = self.simple_preprocessing.encode_record(record)
        
        # Target is the utilization rate
        target = torch.tensor([record.utilization_rate], dtype=torch.float32)
        
        return input_tensor, target


class SimplePreprocessing:
    """Simple preprocessing for training data."""
    
    def __init__(self, max_length: int = 24):
        self.max_length = max_length
    
    def encode_record(self, record: AvailabilityRecord) -> torch.Tensor:
        """Encode a single record into a tensor."""
        # Utilization rate
        utilization = torch.tensor([record.utilization_rate], dtype=torch.float32)
        
        # Event count (normalized)
        event_count = torch.tensor([min(record.contextual_factors.event_count / 10, 1.0)], dtype=torch.float32)
        
        # Weather severity (normalized)
        weather_severity = torch.tensor([record.contextual_factors.weather_severity / 5], dtype=torch.float32)
        
        # Is holiday (binary)
        is_holiday = torch.tensor([1.0 if record.contextual_factors.is_holiday else 0.0], dtype=torch.float32)
        
        # Is weekend (binary)
        is_weekend = torch.tensor([1.0 if record.contextual_factors.is_weekend else 0.0], dtype=torch.float32)
        
        # Concatenate all features
        features = torch.cat([
            utilization,
            event_count,
            weather_severity,
            is_holiday,
            is_weekend,
        ])
        
        return features


class TrainingPipeline:
    """
    Training pipeline for the CAT model.
    
    Handles end-to-end model training with early stopping and checkpointing.
    """
    
    def __init__(
        self,
        model: CATModel,
        config: TrainingConfig = None,
    ):
        """
        Initialize the training pipeline.
        
        Args:
            model: CATModel to train
            config: TrainingConfig with training parameters
        """
        self.model = model
        self.config = config or TrainingConfig()
        self.device = torch.device(self.config.device)
        
        self.model = self.model.to(self.device)
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=1e-5,
        )
        
        self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=self.config.num_epochs,
        )
        
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        self.best_model_path = None
    
    def prepare_data(
        self,
        records: List[AvailabilityRecord],
    ) -> Tuple[DataLoader, DataLoader, DataLoader]:
        """
        Prepare data loaders for training, validation, and testing.
        
        Args:
            records: List of AvailabilityRecord objects
            
        Returns:
            Tuple of (train_loader, val_loader, test_loader)
        """
        # Split data
        n = len(records)
        n_val = int(n * self.config.validation_split)
        n_test = int(n * self.config.test_split)
        n_train = n - n_val - n_test
        
        # Shuffle and split
        indices = list(range(n))
        # Simple split (in production, use temporal split)
        train_records = records[:n_train]
        val_records = records[n_train:n_train + n_val]
        test_records = records[n_train + n_val:]
        
        # Create datasets
        preprocessing = PreprocessingModule()
        train_dataset = AvailabilityDataset(train_records, preprocessing, self.config.max_sequence_length)
        val_dataset = AvailabilityDataset(val_records, preprocessing, self.config.max_sequence_length)
        test_dataset = AvailabilityDataset(test_records, preprocessing, self.config.max_sequence_length)
        
        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
        )
        
        return train_loader, val_loader, test_loader
    
    def train_epoch(
        self,
        train_loader: DataLoader,
    ) -> float:
        """
        Train for one epoch.
        
        Args:
            train_loader: Training data loader
            
        Returns:
            Average training loss
        """
        self.model.train()
        total_loss = 0.0
        
        for batch_idx, (data, target) in enumerate(train_loader):
            data, target = data.to(self.device), target.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            
            # Create simple ModelInput
            from backend.services.cat.data_models import ModelInput
            model_input = ModelInput(
                event_embeddings=[0.0] * 128,
                weather_embeddings=[0.0] * 64,
                historical_sequence=data[:, :5].flatten().tolist(),
                temporal_encoding=[0.0] * 32,
            )
            
            prediction = self.model(model_input)
            
            # Calculate loss
            pred_tensor = torch.tensor([prediction.probability], dtype=torch.float32, device=self.device)
            loss = self.criterion(pred_tensor, target)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            
            self.optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_loader)
        return avg_loss
    
    def validate(
        self,
        val_loader: DataLoader,
    ) -> float:
        """
        Validate the model.
        
        Args:
            val_loader: Validation data loader
            
        Returns:
            Average validation loss
        """
        self.model.eval()
        total_loss = 0.0
        
        with torch.no_grad():
            for data, target in val_loader:
                data, target = data.to(self.device), target.to(self.device)
                
                # Create simple ModelInput
                from backend.services.cat.data_models import ModelInput
                model_input = ModelInput(
                    event_embeddings=[0.0] * 128,
                    weather_embeddings=[0.0] * 64,
                    historical_sequence=data[:, :5].flatten().tolist(),
                    temporal_encoding=[0.0] * 32,
                )
                
                prediction = self.model(model_input)
                
                # Calculate loss
                pred_tensor = torch.tensor([prediction.probability], dtype=torch.float32, device=self.device)
                loss = self.criterion(pred_tensor, target)
                
                total_loss += loss.item()
        
        avg_loss = total_loss / len(val_loader)
        return avg_loss
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        experiment_name: str = "CAT Training",
    ) -> Dict[str, Any]:
        """
        Train the model with early stopping.
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            experiment_name: MLflow experiment name
            
        Returns:
            Training results dictionary
        """
        # Set up MLflow
        mlflow.set_experiment(experiment_name)
        
        with mlflow.start_run():
            # Log configuration
            mlflow.log_params({
                'batch_size': self.config.batch_size,
                'learning_rate': self.config.learning_rate,
                'num_epochs': self.config.num_epochs,
                'early_stopping_patience': self.config.early_stopping_patience,
                'validation_split': self.config.validation_split,
                'device': self.config.device,
            })
            
            # Training loop
            for epoch in range(self.config.num_epochs):
                # Train
                train_loss = self.train_epoch(train_loader)
                
                # Validate
                val_loss = self.validate(val_loader)
                
                # Learning rate scheduling
                self.scheduler.step()
                
                # Log metrics
                mlflow.log_metrics({
                    'train_loss': train_loss,
                    'val_loss': val_loss,
                    'learning_rate': self.scheduler.get_last_lr()[0],
                }, step=epoch)
                
                logger.info(f"Epoch {epoch + 1}/{self.config.num_epochs}: "
                           f"train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")
                
                # Early stopping check
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.patience_counter = 0
                    
                    # Save best model
                    self.best_model_path = f"checkpoints/best_model_epoch_{epoch + 1}.pt"
                    os.makedirs('checkpoints', exist_ok=True)
                    self.model.save(self.best_model_path)
                    
                    mlflow.pytorch.log_model(self.model, "model")
                    
                    logger.info(f"Saved best model at epoch {epoch + 1}")
                else:
                    self.patience_counter += 1
                    
                    if self.patience_counter >= self.config.early_stopping_patience:
                        logger.info(f"Early stopping at epoch {epoch + 1}")
                        break
            
            # Log final metrics
            mlflow.log_metrics({
                'best_val_loss': self.best_val_loss,
                'epochs_trained': epoch + 1,
            })
            
            return {
                'best_val_loss': self.best_val_loss,
                'epochs_trained': epoch + 1,
                'best_model_path': self.best_model_path,
            }
    
    def load_best_model(self) -> CATModel:
        """Load the best model from checkpoint."""
        if self.best_model_path and os.path.exists(self.best_model_path):
            return CATModel.load(self.best_model_path)
        else:
            raise ValueError("No best model found. Run training first.")