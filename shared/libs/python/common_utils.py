# shared/libs/python/common_utils.py
import logging
import json
import yaml
from typing import Any, Dict, Optional, Union
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
import jwt
from jwt.exceptions import PyJWTError

class ConfigLoader:
    """Configuration loader for service configurations."""
    
    def __init__(self, config_path: Union[str, Path]):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        
    def load(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            return self.config
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            raise

class JsonEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling special types."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class AWSClient:
    """AWS service client wrapper."""
    
    def __init__(self, service_name: str, region: str, endpoint_url: Optional[str] = None):
        self.service_name = service_name
        self.client = boto3.client(
            service_name,
            region_name=region,
            endpoint_url=endpoint_url
        )
    
    def call(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute AWS API operation with error handling."""
        try:
            return self.client._make_api_call(operation, kwargs)
        except ClientError as e:
            logging.error(f"AWS operation failed: {e}")
            raise

class SecurityUtils:
    """Security utility functions."""
    
    @staticmethod
    def generate_jwt_token(
        payload: Dict[str, Any],
        secret: str,
        algorithm: str = 'HS256',
        expires_in: int = 3600
    ) -> str:
        """Generate JWT token."""
        try:
            payload['exp'] = datetime.utcnow().timestamp() + expires_in
            return jwt.encode(payload, secret, algorithm=algorithm)
        except PyJWTError as e:
            logging.error(f"JWT token generation failed: {e}")
            raise

    @staticmethod
    def verify_jwt_token(token: str, secret: str, algorithm: str = 'HS256') -> Dict[str, Any]:
        """Verify JWT token and return payload."""
        try:
            return jwt.decode(token, secret, algorithms=[algorithm])
        except PyJWTError as e:
            logging.error(f"JWT token verification failed: {e}")
            raise

class LoggerSetup:
    """Logger setup utility."""
    
    @staticmethod
    def setup_logger(
        name: str,
        level: str = 'INFO',
        format: str = 'json',
        output: str = 'stdout'
    ) -> logging.Logger:
        """Configure logging with the specified parameters."""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper()))
        
        if format == 'json':
            formatter = logging.Formatter(
                '{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        if output == 'stdout':
            handler = logging.StreamHandler()
        else:
            handler = logging.FileHandler(output)
            
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

class Validation:
    """Data validation utilities."""
    
    @staticmethod
    def validate_stock_symbol(symbol: str) -> bool:
        """Validate stock symbol format."""
        if not symbol or not isinstance(symbol, str):
            return False
        return True

    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> bool:
        """Validate date range."""
        if not start_date or not end_date:
            return False
        if end_date < start_date:
            return False
        if end_date > date.today():
            return False
        return True

class MetricsCollector:
    """Metrics collection utility."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics: Dict[str, Any] = {}
    
    def increment_counter(self, metric_name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = 0
        self.metrics[metric_name] += value
    
    def record_timing(self, metric_name: str, value: float) -> None:
        """Record a timing metric."""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        return self.metrics

class StockDataUtils:
    """Stock data processing utilities."""
    
    @staticmethod
    def calculate_moving_average(prices: list[float], window: int) -> list[float]:
        """Calculate simple moving average."""
        if len(prices) < window:
            return []
        return [
            sum(prices[i:i+window]) / window
            for i in range(len(prices) - window + 1)
        ]
    
    @staticmethod
    def calculate_percentage_change(old_value: float, new_value: float) -> float:
        """Calculate percentage change between two values."""
        if old_value == 0:
            return 0
        return ((new_value - old_value) / old_value) * 100

class HTTPClient:
    """HTTP client utility with retry logic."""
    
    def __init__(self, base_url: str, timeout: int = 30, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
    
    def _create_session(self):
        """Create and configure requests session."""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request with retry logic."""
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"HTTP GET request failed: {e}")
            raise