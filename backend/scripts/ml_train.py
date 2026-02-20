"""Wrapper for backwards compatibility"""
import sys
sys.path.insert(0, '..')
from intelligence.training.pipeline import train_pipeline

if __name__ == "__main__":
    train_pipeline()
