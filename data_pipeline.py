import os
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import dataset as ds
from sqlalchemy import create_engine, text
from pydantic import BaseModel, ValidationError
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngestionSchema(BaseModel):
    user_id: str
    recency_days: float
    frequency: int
    monetary_value: float
    session_failures: int
    payment_friction_index: float
    active_support_tickets: int
    churn_probability: float | None = None
    segment: str | None = None
    is_deleted: bool = False

    class Config:
        extra = "ignore"

class IngestionEngine:
    def __init__(self, source_uri: str, target_dir: str = settings.data_root):
        self.source_uri = source_uri
        self.target_dir = target_dir
        os.makedirs(self.target_dir, exist_ok=True)

    def ingest_table(self, table_name: str, merchant_id: int, chunk_size: int = 10000):
        """
        Streams incoming tables in micro-batches using PyArrow and SQLAlchemy,
        buffering directly to local Parquet files partitioned by merchant_id.
        """
        logger.info(f"Starting ingestion from {self.source_uri} for table {table_name}")
        
        # If it's a parquet/s3 path, use PyArrow dataset directly
        if self.source_uri.startswith("s3://") or self.source_uri.endswith(".parquet"):
            self._ingest_from_parquet(table_name, merchant_id)
            return

        # Otherwise, assume relational DB via SQLAlchemy
        engine = create_engine(self.source_uri)
        
        # Define the path for the partition
        partition_path = os.path.join(self.target_dir, f"merchant_id={merchant_id}")
        os.makedirs(partition_path, exist_ok=True)
        file_path = os.path.join(partition_path, f"{table_name}_buffer.parquet")

        with engine.connect() as conn:
            # Using server-side cursors if supported (PostgreSQL/MySQL), simulated via yield_per in SQLAlchemy
            resultProxy = conn.execution_options(stream_results=True).execute(
                text(f"SELECT * FROM {table_name}")
            )

            schema = None
            writer = None
            
            while True:
                chunk = resultProxy.fetchmany(chunk_size)
                if not chunk:
                    break
                
                # Convert list of tuples to PyArrow Table
                # Use keys from resultProxy
                keys = list(resultProxy.keys())
                
                validated_chunk = []
                for row in chunk:
                    row_dict = dict(zip(keys, row))
                    try:
                        valid_model = IngestionSchema(**row_dict)
                        validated_chunk.append(valid_model.model_dump())
                    except ValidationError as e:
                        logger.error(f"Schema mismatch dropped row {row_dict.get('user_id', 'UNKNOWN')}: {e}")
                
                if not validated_chunk:
                    continue

                # Convert validated chunk to arrays
                arrays = []
                for key in IngestionSchema.model_fields.keys():
                    col_data = [row[key] for row in validated_chunk]
                    arrays.append(pa.array(col_data))
                
                batch = pa.RecordBatch.from_arrays(arrays, names=list(IngestionSchema.model_fields.keys()))
                table = pa.Table.from_batches([batch])
                
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(file_path, schema, compression='snappy')
                
                writer.write_table(table)

            if writer:
                writer.close()
                logger.info(f"Successfully buffered {table_name} to {file_path}")
            else:
                logger.warning(f"No data found in {table_name}")

    def _ingest_from_parquet(self, table_name: str, merchant_id: int):
        dataset = ds.dataset(self.source_uri, format="parquet")
        partition_path = os.path.join(self.target_dir, f"merchant_id={merchant_id}")
        os.makedirs(partition_path, exist_ok=True)
        
        pq.write_to_dataset(
            dataset.to_table(),
            root_path=self.target_dir,
            partition_cols=["merchant_id"],
            compression="snappy"
        )
        logger.info(f"Synced parquet source {self.source_uri}")

if __name__ == "__main__":
    # Example usage:
    # engine = IngestionEngine("postgresql://user:pass@localhost:5432/db")
    # engine.ingest_table("customers", merchant_id=1)
    pass
