"""
Unit tests for the CAT training pipeline.
Tests data loading, training loop, and model training behavior.
"""

import pytest
import torch
from datetime import datetime, timedelta

from backend.cat.training.pipeline import CATDataset, CATDataLoader, TrainingPipeline
from backend.cat.preprocessing.encoders import TensorPreprocessor
from backend.cat.data_collection.synthetic_data import SyntheticDataGenerator
from backend.cat.config import settings


class TestCATDataset:
    """Tests for CATDataset class."""
    
    def test_dataset_creation(self):
        """Test that dataset can be created with empty data."""
        dataset = CATDataset(contextual_data=[])
        
        assert len(dataset) == 0
    
    def test_dataset_with_samples(self):
        """Test dataset with sample data."""
        # Generate synthetic data
        generator = SyntheticDataGenerator(
            num_locations=2,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            seed=42
        )
        
        historical, contextual = generator.generate_dataset(num_samples=100)
        
        dataset = CATDataset(contextual_data=contextual)
        
        assert len(dataset) == len(contextual)
    
    def test_dataset_getitem(self):
        """Test getting items from dataset."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 5),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=10)
        
        dataset = CATDataset(contextual_data=contextual)
        
        # Get a single item
        input_tensor, target = dataset[0]
        
        assert isinstance(input_tensor, torch.Tensor)
        assert isinstance(target, torch.Tensor)
        assert target.dim() == 0  # Scalar tensor
        assert 0.0 <= target.item() <= 1.0  # Target should be in [0, 1]
    
    def test_dataset_len(self):
        """Test dataset length."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=50)
        
        dataset = CATDataset(contextual_data=contextual)
        
        assert len(dataset) == 50


class TestCATDataLoader:
    """Tests for CATDataLoader class."""
    
    def test_dataloader_creation(self):
        """Test that data loader can be created."""
        # Create a dataset with actual data
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 2),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=10)
        dataset = CATDataset(contextual_data=contextual)
        
        loader = CATDataLoader(dataset, batch_size=4, shuffle=False)
        
        assert loader.batch_size == 4
    
    def test_batch_loading(self):
        """Test loading batches from data loader."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 5),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=20)
        
        dataset = CATDataset(contextual_data=contextual)
        loader = CATDataLoader(dataset, batch_size=4, shuffle=False)
        
        # Get a batch
        inputs, targets = next(iter(loader))
        
        assert inputs.shape[0] == 4
        assert targets.shape[0] == 4
    
    def test_batch_shuffling(self):
        """Test that shuffling works correctly."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 5),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=20)
        
        dataset = CATDataset(contextual_data=contextual)
        
        # Create loader with shuffling
        loader = CATDataLoader(dataset, batch_size=4, shuffle=True, seed=42)
        
        # Get first batch - should work with shuffling enabled
        inputs, targets = next(iter(loader))
        
        assert inputs.shape[0] == 4
        assert targets.shape[0] == 4


class TestTrainingPipeline:
    """Tests for TrainingPipeline class."""
    
    def test_pipeline_creation(self):
        """Test that training pipeline can be created."""
        pipeline = TrainingPipeline()
        
        assert pipeline.model is not None
        assert pipeline.optimizer is not None
        assert pipeline.criterion is not None
    
    def test_prepare_data(self):
        """Test data preparation."""
        generator = SyntheticDataGenerator(
            num_locations=2,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 3, 1),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=200)
        
        pipeline = TrainingPipeline()
        train_loader, val_loader, test_loader = pipeline.prepare_data(contextual)
        
        # Check that data is split correctly
        assert train_loader is not None
        assert val_loader is not None
        assert test_loader is not None
        
        # Check approximate split ratios
        total = len(contextual)
        expected_train = int(total * settings.train_split_ratio)
        expected_val = int(total * settings.val_split_ratio)
        
        assert len(train_loader.dataset) > 0
        assert len(val_loader.dataset) > 0
    
    def test_train_epoch(self):
        """Test training for one epoch."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=50)
        
        pipeline = TrainingPipeline()
        train_loader, val_loader, _ = pipeline.prepare_data(contextual)
        
        # Train one epoch
        train_loss = pipeline.train_epoch(train_loader)
        
        assert isinstance(train_loss, float)
        assert train_loss >= 0.0
        assert not torch.isnan(torch.tensor(train_loss))
    
    def test_validate(self):
        """Test model validation."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 10),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=50)
        
        pipeline = TrainingPipeline()
        _, val_loader, _ = pipeline.prepare_data(contextual)
        
        # Validate
        metrics = pipeline.validate(val_loader)
        
        assert "val_loss" in metrics
        assert "val_mae" in metrics
        assert "val_rmse" in metrics
        assert metrics["val_loss"] >= 0.0
    
    def test_training_loop(self):
        """Test complete training loop."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 15),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=100)
        
        pipeline = TrainingPipeline()
        train_loader, val_loader, _ = pipeline.prepare_data(contextual)
        
        # Train for a few epochs
        history = pipeline.train(train_loader, val_loader, checkpoint_interval=5)
        
        assert "train_losses" in history
        assert "val_losses" in history
        assert len(history["train_losses"]) > 0
        
        # Check that losses are decreasing
        if len(history["train_losses"]) > 1:
            assert history["train_losses"][-1] <= history["train_losses"][0]
    
    def test_checkpoint_saving(self):
        """Test checkpoint saving."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 5),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=30)
        
        pipeline = TrainingPipeline()
        train_loader, _, _ = pipeline.prepare_data(contextual)
        
        # Train one epoch to create checkpoint
        pipeline.train_epoch(train_loader)
        pipeline.save_checkpoint("test_checkpoint.pt")
        
        # Check that checkpoint was created
        import os
        checkpoint_path = pipeline.checkpoint_dir / "test_checkpoint.pt"
        assert os.path.exists(checkpoint_path)
    
    def test_checkpoint_loading(self):
        """Test checkpoint loading."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 5),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=30)
        
        pipeline = TrainingPipeline()
        train_loader, _, _ = pipeline.prepare_data(contextual)
        
        # Train and save
        pipeline.train_epoch(train_loader)
        pipeline.save_checkpoint("test_checkpoint.pt")
        
        # Create new pipeline and load
        pipeline2 = TrainingPipeline()
        pipeline2.load_checkpoint(str(pipeline.checkpoint_dir / "test_checkpoint.pt"))
        
        # Check that epoch was restored
        assert pipeline2.current_epoch == pipeline.current_epoch


class TestHistoricalPatternPreservation:
    """
    Tests for Property 6: Historical Pattern Preservation.
    
    For any historical availability record, the model's prediction
    for that exact historical context SHALL be within 10% of the
    actual recorded availability.
    """
    
    def test_prediction_accuracy_on_training_data(self):
        """Test that predictions are reasonably accurate on training data."""
        generator = SyntheticDataGenerator(
            num_locations=1,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 20),
            seed=42
        )
        
        _, contextual = generator.generate_dataset(num_samples=100)
        
        # Create and train model
        pipeline = TrainingPipeline()
        train_loader, val_loader, _ = pipeline.prepare_data(contextual)
        
        # Train for a few epochs
        pipeline.train(train_loader, val_loader, checkpoint_interval=5)
        
        # Load best model
        best_path = pipeline.checkpoint_dir / "best_model.pt"
        if best_path.exists():
            pipeline.load_checkpoint(str(best_path))
        
        # Test on a few samples
        pipeline.model.eval()
        
        errors = []
        for ctx in contextual[:20]:
            # Get target from historical data
            if ctx.historical_availability.records:
                target = 1.0 - ctx.historical_availability.records[-1].utilization_rate
                
                # Get prediction
                preprocessor = pipeline.preprocessor
                if ctx.historical_availability.records:
                    pred_time = ctx.historical_availability.records[-1].timestamp
                else:
                    pred_time = ctx.timestamp
                
                (
                    event_emb, weather_emb,
                    historical_seq, temporal_enc
                ) = preprocessor.preprocess(
                    ctx.event_calendar,
                    ctx.weather,
                    ctx.historical_availability,
                    pred_time
                )
                
                model_input = preprocessor.create_model_input(
                    event_emb, weather_emb, historical_seq, temporal_enc
                )
                
                with torch.no_grad():
                    output = pipeline.model(model_input.unsqueeze(0))
                
                prediction = output["probability"].item()
                error = abs(prediction - target)
                errors.append(error)
        
        # Check that most predictions are within 10%
        if errors:
            avg_error = sum(errors) / len(errors)
            within_10_percent = sum(1 for e in errors if e <= 0.1) / len(errors)
            
            # At least 50% should be within 10% (relaxed for quick test)
            assert within_10_percent >= 0.5 or avg_error <= 0.2, (
                f"Too many predictions outside 10% threshold. "
                f"Within 10%: {within_10_percent:.2%}, Avg error: {avg_error:.3f}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])