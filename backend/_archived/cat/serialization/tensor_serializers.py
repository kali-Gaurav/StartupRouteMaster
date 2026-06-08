"""
PyTorch tensor serialization utilities for CAT system.
Handles serialization/deserialization of PyTorch tensors to/from JSON
with shape and dtype preservation.
"""

import base64
import json
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch import Tensor


class TensorSerializer:
    """
    Serializer for PyTorch tensors with JSON compatibility.
    
    Supports:
    - Serialization to/from JSON
    - Shape and dtype preservation
    - Validation after deserialization
    - Base64 encoding for binary data
    """
    
    # Mapping from torch dtype to string representation
    DTYPE_MAP = {
        torch.float16: "float16",
        torch.float32: "float32",
        torch.float64: "float64",
        torch.int8: "int8",
        torch.int16: "int16",
        torch.int32: "int32",
        torch.int64: "int64",
        torch.uint8: "uint8",
        torch.bool: "bool",
    }
    
    # Reverse mapping from string to torch dtype
    DTYPE_REVERSE_MAP = {v: k for k, v in DTYPE_MAP.items()}
    
    @staticmethod
    def serialize_tensor(tensor: Tensor, include_data: bool = True) -> Dict[str, Any]:
        """
        Serialize a PyTorch tensor to dictionary.
        
        Args:
            tensor: PyTorch tensor to serialize
            include_data: Whether to include the actual tensor data
            
        Returns:
            Dictionary with tensor metadata and optionally data
        """
        result = {
            'shape': list(tensor.shape),
            'dtype': TensorSerializer.DTYPE_MAP.get(tensor.dtype, str(tensor.dtype)),
            'device': str(tensor.device),
            'requires_grad': tensor.requires_grad
        }
        
        if include_data:
            # Convert tensor to numpy for serialization
            if tensor.is_cuda:
                tensor = tensor.cpu()
            
            # Detach from computation graph if needed
            if tensor.requires_grad:
                tensor = tensor.detach()
            
            if tensor.dtype == torch.bool:
                # For bool, convert to uint8 for JSON compatibility
                np_array = tensor.numpy().astype(np.uint8)
            else:
                np_array = tensor.numpy()
            
            # Serialize numpy array to base64
            result['data'] = base64.b64encode(np_array.tobytes()).decode('utf-8')
            result['shape'] = list(np_array.shape)
        
        return result
    
    @staticmethod
    def deserialize_tensor(data: Dict[str, Any]) -> Tensor:
        """
        Deserialize dictionary to PyTorch tensor.
        
        Args:
            data: Dictionary with serialized tensor data
            
        Returns:
            Deserialized PyTorch tensor
        """
        # Get shape and dtype
        shape = tuple(data['shape'])
        dtype_str = data['dtype']
        device_str = data.get('device', 'cpu')
        requires_grad = data.get('requires_grad', False)
        
        # Convert dtype string to torch dtype
        if dtype_str in TensorSerializer.DTYPE_REVERSE_MAP:
            dtype = TensorSerializer.DTYPE_REVERSE_MAP[dtype_str]
        else:
            # Try to parse as torch dtype string
            dtype = eval(f"torch.{dtype_str}")
        
        # Get device
        device = torch.device(device_str)
        
        # Deserialize data
        if 'data' in data:
            # Decode base64 data
            decoded_data = base64.b64decode(data['data'])
            
            # Determine numpy dtype
            if dtype_str == 'bool':
                np_dtype = np.uint8
            elif 'float' in dtype_str:
                bit_depth = ''.join(filter(str.isdigit, dtype_str))
                np_dtype = getattr(np, f'float{bit_depth}')
            elif 'int' in dtype_str:
                bit_depth = ''.join(filter(str.isdigit, dtype_str))
                np_dtype = getattr(np, f'int{bit_depth}')
            else:
                np_dtype = np.float32
            
            # Reconstruct numpy array
            np_array = np.frombuffer(decoded_data, dtype=np_dtype)
            np_array = np_array.reshape(shape)
            
            # Convert to tensor
            tensor = torch.from_numpy(np_array).to(device)
            
            # Set dtype correctly
            if dtype != tensor.dtype:
                tensor = tensor.to(dtype)
            
            tensor.requires_grad = requires_grad
        else:
            # Create empty tensor
            tensor = torch.empty(shape, dtype=dtype, device=device)
            tensor.requires_grad = requires_grad
        
        return tensor
    
    @staticmethod
    def validate_tensor(tensor: Tensor, expected_shape: Optional[Tuple[int, ...]] = None,
                        expected_dtype: Optional[torch.dtype] = None) -> bool:
        """
        Validate a tensor after deserialization.
        
        Args:
            tensor: Tensor to validate
            expected_shape: Expected shape (optional)
            expected_dtype: Expected dtype (optional)
            
        Returns:
            True if validation passes
        """
        # Check for NaN and Inf values
        if torch.isnan(tensor).any():
            raise ValueError("Tensor contains NaN values")
        if torch.isinf(tensor).any():
            raise ValueError("Tensor contains Inf values")
        
        # Check shape if provided
        if expected_shape is not None:
            if tensor.shape != expected_shape:
                raise ValueError(f"Shape mismatch: expected {expected_shape}, got {tensor.shape}")
        
        # Check dtype if provided
        if expected_dtype is not None:
            if tensor.dtype != expected_dtype:
                raise ValueError(f"Dtype mismatch: expected {expected_dtype}, got {tensor.dtype}")
        
        return True
    
    @staticmethod
    def to_json(tensor: Tensor, indent: int = None) -> str:
        """
        Serialize tensor to JSON string.
        
        Args:
            tensor: PyTorch tensor to serialize
            indent: Indentation level for pretty printing
            
        Returns:
            JSON string representation
        """
        data = TensorSerializer.serialize_tensor(tensor)
        return json.dumps(data, indent=indent)
    
    @staticmethod
    def from_json(json_str: str) -> Tensor:
        """
        Deserialize JSON string to tensor.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Deserialized PyTorch tensor
        """
        data = json.loads(json_str)
        return TensorSerializer.deserialize_tensor(data)
    
    @staticmethod
    def validate_from_json(json_str: str, expected_shape: Optional[Tuple[int, ...]] = None,
                          expected_dtype: Optional[torch.dtype] = None) -> Tensor:
        """
        Deserialize JSON string to tensor and validate.
        
        Args:
            json_str: JSON string to deserialize
            expected_shape: Expected shape (optional)
            expected_dtype: Expected dtype (optional)
            
        Returns:
            Validated PyTorch tensor
        """
        tensor = TensorSerializer.from_json(json_str)
        TensorSerializer.validate_tensor(tensor, expected_shape, expected_dtype)
        return tensor


class TensorBatchSerializer:
    """
    Serializer for batches of tensors.
    """
    
    @staticmethod
    def serialize_batch(tensors: List[Tensor], names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Serialize a batch of tensors.
        
        Args:
            tensors: List of tensors to serialize
            names: Optional list of tensor names
            
        Returns:
            Dictionary with serialized tensors
        """
        if names is None:
            names = [f"tensor_{i}" for i in range(len(tensors))]
        
        result = {}
        for name, tensor in zip(names, tensors):
            result[name] = TensorSerializer.serialize_tensor(tensor)
        
        return result
    
    @staticmethod
    def deserialize_batch(data: Dict[str, Any]) -> Dict[str, Tensor]:
        """
        Deserialize dictionary of tensors.
        
        Args:
            data: Dictionary with serialized tensors
            
        Returns:
            Dictionary of deserialized tensors
        """
        result = {}
        for name, tensor_data in data.items():
            result[name] = TensorSerializer.deserialize_tensor(tensor_data)
        return result
    
    @staticmethod
    def validate_batch(data: Dict[str, Any], expected_shapes: Dict[str, Tuple[int, ...]] = None,
                      expected_dtypes: Dict[str, torch.dtype] = None) -> bool:
        """
        Validate a batch of tensors.
        
        Args:
            data: Dictionary with serialized tensors
            expected_shapes: Expected shapes by name (optional)
            expected_dtypes: Expected dtypes by name (optional)
            
        Returns:
            True if all validations pass
        """
        for name, tensor_data in data.items():
            tensor = TensorSerializer.deserialize_tensor(tensor_data)
            
            expected_shape = expected_shapes.get(name) if expected_shapes else None
            expected_dtype = expected_dtypes.get(name) if expected_dtypes else None
            
            TensorSerializer.validate_tensor(tensor, expected_shape, expected_dtype)
        
        return True


class ModelInputSerializer:
    """
    Serializer for ModelInput tensors used in CAT preprocessing.
    """
    
    @staticmethod
    def serialize_model_input(event_emb: Tensor, weather_emb: Tensor,
                             historical_seq: Tensor, temporal_enc: Tensor) -> Dict[str, Any]:
        """
        Serialize all ModelInput tensors.
        
        Args:
            event_emb: Event embeddings tensor
            weather_emb: Weather embeddings tensor
            historical_seq: Historical sequence tensor
            temporal_enc: Temporal encoding tensor
            
        Returns:
            Dictionary with all serialized tensors
        """
        return {
            'event_embeddings': TensorSerializer.serialize_tensor(event_emb),
            'weather_embeddings': TensorSerializer.serialize_tensor(weather_emb),
            'historical_sequence': TensorSerializer.serialize_tensor(historical_seq),
            'temporal_encoding': TensorSerializer.serialize_tensor(temporal_enc)
        }
    
    @staticmethod
    def deserialize_model_input(data: Dict[str, Any]) -> Dict[str, Tensor]:
        """
        Deserialize ModelInput tensors.
        
        Args:
            data: Dictionary with serialized tensors
            
        Returns:
            Dictionary with deserialized tensors
        """
        return {
            'event_embeddings': TensorSerializer.deserialize_tensor(data['event_embeddings']),
            'weather_embeddings': TensorSerializer.deserialize_tensor(data['weather_embeddings']),
            'historical_sequence': TensorSerializer.deserialize_tensor(data['historical_sequence']),
            'temporal_encoding': TensorSerializer.deserialize_tensor(data['temporal_encoding'])
        }
    
    @staticmethod
    def validate_model_input(data: Dict[str, Any], expected_shapes: Dict[str, Tuple[int, ...]]) -> bool:
        """
        Validate ModelInput tensors.
        
        Args:
            data: Dictionary with serialized tensors
            expected_shapes: Expected shapes for each tensor
            
        Returns:
            True if all validations pass
        """
        return TensorBatchSerializer.validate_batch(data, expected_shapes)
    
    @staticmethod
    def to_json(event_emb: Tensor, weather_emb: Tensor,
               historical_seq: Tensor, temporal_enc: Tensor, indent: int = None) -> str:
        """
        Serialize ModelInput to JSON string.
        
        Args:
            event_emb: Event embeddings tensor
            weather_emb: Weather embeddings tensor
            historical_seq: Historical sequence tensor
            temporal_enc: Temporal encoding tensor
            indent: Indentation level for pretty printing
            
        Returns:
            JSON string representation
        """
        data = ModelInputSerializer.serialize_model_input(event_emb, weather_emb,
                                                         historical_seq, temporal_enc)
        return json.dumps(data, indent=indent)
    
    @staticmethod
    def from_json(json_str: str) -> Dict[str, Tensor]:
        """
        Deserialize JSON string to ModelInput tensors.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Dictionary with deserialized tensors
        """
        data = json.loads(json_str)
        return ModelInputSerializer.deserialize_model_input(data)


# Convenience functions
def serialize_tensor(tensor: Tensor) -> str:
    """
    Serialize a tensor to JSON string.
    
    Args:
        tensor: PyTorch tensor to serialize
        
    Returns:
        JSON string representation
    """
    return TensorSerializer.to_json(tensor)


def deserialize_tensor(json_str: str) -> Tensor:
    """
    Deserialize JSON string to tensor.
    
    Args:
        json_str: JSON string to deserialize
        
    Returns:
        Deserialized PyTorch tensor
    """
    return TensorSerializer.from_json(json_str)


def validate_tensor(json_str: str, expected_shape: Optional[Tuple[int, ...]] = None,
                   expected_dtype: Optional[torch.dtype] = None) -> Tensor:
    """
    Deserialize and validate a tensor from JSON.
    
    Args:
        json_str: JSON string to deserialize
        expected_shape: Expected shape (optional)
        expected_dtype: Expected dtype (optional)
        
    Returns:
        Validated PyTorch tensor
    """
    return TensorSerializer.validate_from_json(json_str, expected_shape, expected_dtype)
