from typing import Any, Dict, List, Optional, Tuple
from src.utils.pipeline import DataTransformationPipeline
from src.utils.error_handling import ErrorCollector, ErrorSeverity
import logging

logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Processes a batch of records using a DataTransformationPipeline.
    Supports error handling strategies: 'skip' (default), 'abort'.
    Tracks progress and provides a batch summary report.
    """
    def __init__(self, pipeline: DataTransformationPipeline, error_strategy: str = 'skip'):
        self.pipeline = pipeline
        self.error_strategy = error_strategy  # 'skip' or 'abort'
        self.error_collector = ErrorCollector()
        self.processed: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []

    def process_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], ErrorCollector]:
        """
        Process a list of records. Returns (processed, error_collector).
        """
        for idx, record in enumerate(records):
            normalized, errors = self.pipeline.process_reading(record)
            if errors:
                self.failed.append(record)
                for field, msg in errors.items():
                    self.error_collector.add_error(
                        'ValidationError', field, f"Record {idx}: {msg}", ErrorSeverity.HIGH
                    )
                if self.error_strategy == 'abort':
                    logger.error(f"Aborting batch on error at record {idx}: {errors}")
                    break
                continue  # skip
            self.processed.append(normalized)
        return self.processed, self.error_collector

    def summary(self) -> Dict[str, Any]:
        """
        Returns a summary of the batch processing results.
        """
        return {
            'total': len(self.processed) + len(self.failed),
            'processed': len(self.processed),
            'failed': len(self.failed),
            'errors': self.error_collector.get_errors(),
        } 