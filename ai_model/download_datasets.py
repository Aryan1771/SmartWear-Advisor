import shutil
from pathlib import Path
import pandas as pd
import numpy as np
try:
    import kagglehub
except ModuleNotFoundError:
    kagglehub = None
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
LABELED_DIR = PROJECT_ROOT / "data" / "labeled" / "glasses"
RAW_DIR.mkdir(parents=True, exist_ok=True)
LABELED_DIR.mkdir(parents=True, exist_ok=True)
WITH_GLASSES_DIR = LABELED_DIR / "with_glasses"
WITHOUT_GLASSES_DIR = LABELED_DIR / "without_glasses"
WITH_GLASSES_DIR.mkdir(parents=True, exist_ok=True)
WITHOUT_GLASSES_DIR.mkdir(parents=True, exist_ok=True)
DATASETS = [
    "jeffheaton/glasses-or-no-glasses",
]
LIMIT_PER_CLASS = 1000
IMG_SIZE = 128
def process_glasses_dataset(downloaded_path: Path):
    print("\nProcessing glasses dataset (vector → image)...")
    csv_file = downloaded_path / "train.csv"
    if not csv_file.exists():
        raise Exception("train.csv not found")
    df = pd.read_csv(csv_file)
    print("CSV loaded")
    print("Shape:", df.shape)
    with_glasses = df[df["glasses"] == 1]
    without_glasses = df[df["glasses"] == 0]
    with_glasses = with_glasses.sample(min(LIMIT_PER_CLASS, len(with_glasses)))
    without_glasses = without_glasses.sample(min(LIMIT_PER_CLASS, len(without_glasses)))
    def save_images(df_subset, target_dir):
        for idx, row in df_subset.iterrows():
            try:
                pixels = row.drop(["id", "glasses"]).values.astype(np.uint8)
                img = pixels.reshape(32, 16)
                img = Image.fromarray(img)
                img = img.resize((IMG_SIZE, IMG_SIZE))
                img.save(target_dir / f"{idx}.jpg")
            except Exception as e:
                print(f"Skipping row {idx}: {e}")
    print("Generating WITH glasses images...")
    save_images(with_glasses, WITH_GLASSES_DIR)
    print("Generating WITHOUT glasses images...")
    save_images(without_glasses, WITHOUT_GLASSES_DIR)
    print("Dataset converted and saved!")
def clean_raw_data(downloaded_path: Path):
    try:
        print("\nCleaning raw dataset...")
        if downloaded_path.exists():
            shutil.rmtree(downloaded_path)
        if RAW_DIR.exists():
            shutil.rmtree(RAW_DIR)
            RAW_DIR.mkdir(parents=True, exist_ok=True)

        print(" Raw data deleted successfully")

    except Exception as e:
        print(f" Cleanup failed: {e}")
def main():
    if kagglehub is None:
        raise ModuleNotFoundError(
            "Install kagglehub using: pip install kagglehub"
        )
    for dataset in DATASETS:
        print(f"\nDownloading: {dataset}")
        downloaded_path = Path(kagglehub.dataset_download(dataset))
        print(f"Downloaded to cache: {downloaded_path}")
        if "glasses" in dataset:
            process_glasses_dataset(downloaded_path)
        clean_raw_data(downloaded_path)
    print(f"\n Final dataset ready at: {LABELED_DIR}")
if __name__ == "__main__":
    main()