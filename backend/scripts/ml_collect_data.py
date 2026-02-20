"""Wrapper for backwards compatibility"""
import sys
sys.path.insert(0, '..')
from intelligence.training.data_collection import *

if __name__ == "__main__":
    collect_data()
