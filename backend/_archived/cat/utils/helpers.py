"""
Utility functions for the Contextual Availability Transformer (CAT) system.
"""

import random
import time
from datetime import datetime
from typing import Optional, ContextManager

import torch


def set_seed(seed: int) -> None:
    """
    Set random seed for reproducibility.
    
    Args:
        seed: Random seed value
    """
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    
    # Set Python hash seed for consistent behavior
    import os
    os.environ['PYTHONHASHSEED'] = str(seed)
    
    # Configure PyTorch
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_device() -> torch.device:
    """
    Get the appropriate device for computation.
    
    Returns:
        CUDA device if available, otherwise CPU
    """
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def format_time(seconds: float) -> str:
    """
    Format seconds into human-readable time string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string (e.g., "2h 30m 15s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        return f"{days}d {hours}h"


def parse_time(time_str: str) -> Optional[datetime]:
    """
    Parse a time string into a datetime object.
    
    Args:
        time_str: Time string in ISO format or common formats
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    return None


class Timer(ContextManager):
    """
    Context manager for timing code blocks.
    
    Usage:
        with Timer() as t:
            # code to time
        print(f"Elapsed: {t.elapsed:.2f}s")
    """
    
    def __init__(self, name: str = "Timer"):
        """
        Initialize the timer.
        
        Args:
            name: Name for the timer (for logging)
        """
        self.name = name
        self.start_time = None
        self.elapsed = 0.0
    
    def __enter__(self):
        """Start the timer."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log elapsed time."""
        self.elapsed = time.time() - self.start_time
        return False
    
    def __str__(self):
        """Return formatted elapsed time."""
        return f"{self.name}: {format_time(self.elapsed)}"


class AverageMeter:
    """
    Computes and stores the average and current value.
    
    Useful for tracking metrics like loss, accuracy, etc.
    """
    
    def __init__(self, name: str = "Avg", fmt: str = ".4f"):
        """
        Initialize the average meter.
        
        Args:
            name: Name of the metric
            fmt: Format string for display
        """
        self.name = name
        self.fmt = fmt
        self.reset()
    
    def reset(self):
        """Reset the meter."""
        self.val = 0.0
        self.avg = 0.0
        self.sum = 0.0
        self.count = 0
    
    def update(self, val: float, n: int = 1):
        """
        Update the meter with a new value.
        
        Args:
            val: New value
            n: Number of samples this value represents
        """
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count if self.count > 0 else 0.0
    
    def __str__(self):
        """Return formatted string representation."""
        return f"{self.name}: {self.val:{self.fmt}} ({self.avg:{self.fmt}})"


def count_parameters(model: torch.nn.Module) -> int:
    """
    Count the number of trainable parameters in a model.
    
    Args:
        model: PyTorch model
        
    Returns:
        Number of trainable parameters
    """
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_model_size(model: torch.nn.Module) -> float:
    """
    Calculate the model size in megabytes.
    
    Args:
        model: PyTorch model
        
    Returns:
        Model size in MB
    """
    param_size = 0
    for param in model.parameters():
        param_size += param.numel() * param.element_size()
    
    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.numel() * buffer.element_size()
    
    size_mb = (param_size + buffer_size) / (1024 ** 2)
    return size_mb


def moving_average(data: list, window: int = 10) -> list:
    """
    Compute moving average of a list.
    
    Args:
        data: List of values
        window: Window size
        
    Returns:
        List of moving averages
    """
    if len(data) < window:
        return data
    
    result = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        window_data = data[start:i + 1]
        result.append(sum(window_data) / len(window_data))
    
    return result


def exponential_moving_average(data: list, alpha: float = 0.3) -> list:
    """
    Compute exponential moving average of a list.
    
    Args:
        data: List of values
        alpha: Smoothing factor (0 < alpha <= 1)
        
    Returns:
        List of EMA values
    """
    if not data:
        return []
    
    result = [data[0]]
    for i in range(1, len(data)):
        ema = alpha * data[i] + (1 - alpha) * result[-1]
        result.append(ema)
    
    return result


if __name__ == "__main__":
    # Test utilities
    print("Testing utilities...")
    
    # Test set_seed
    set_seed(42)
    print("Seed set to 42")
    
    # Test get_device
    device = get_device()
    print(f"Using device: {device}")
    
    # Test Timer
    with Timer("Test") as t:
        time.sleep(0.1)
    print(t)
    
    # Test AverageMeter
    meter = AverageMeter("Loss")
    for i in range(10):
        meter.update(0.1 * i + random.random() * 0.1)
    print(meter)
    
    # Test format_time
    print(f"1 hour: {format_time(3600)}")
    print(f"30 minutes: {format_time(1800)}")
    print(f"90 seconds: {format_time(90)}")
    
    # Test parse_time
    times = [
        "2024-06-15T18:00:00",
        "2024-06-15",
        "2024/06/15 18:00:00"
    ]
    for t in times:
        parsed = parse_time(t)
        print(f"Parsed '{t}': {parsed}")