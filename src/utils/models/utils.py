import os
import shutil

def copy_dataset_parquet(src_dir, dst_dir, dst_path):

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)

    os.makedirs(dst_dir, exist_ok=True)

    parquet_files = [f for f in os.listdir(src_dir) if f.endswith(".parquet")]
    print(parquet_files)
    if len(parquet_files) == 0:
        raise FileNotFoundError(f"No parquet files found in {src_dir}")
    elif len(parquet_files) > 1:
        raise RuntimeError(f"Expected exactly one parquet file in {src_dir}, found {len(parquet_files)}")

    src_path = os.path.join(src_dir, parquet_files[0])

    shutil.copy(src_path, dst_path)

def split_dataset(
    spark,
    dst_path, dataset,
    train_ratio=0.8,
    val_ratio=0.1
):
    original_parquet = spark.read.parquet(dst_path)
    original_parquet_size = original_parquet.count()
    train_size = int(original_parquet_size * train_ratio)
    val_size = int(original_parquet_size * val_ratio)
    test_size = original_parquet_size - train_size - val_size

    train_dataset = dataset.take(train_size)
    val_dataset = dataset.skip(train_size).take(val_size)
    test_dataset = dataset.skip(train_size + val_size)

    return train_dataset, val_dataset, test_dataset