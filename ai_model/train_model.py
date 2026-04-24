import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.models import Sequential
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
LABELED_DIR = PROJECT_ROOT / "data" / "labeled"
MODEL_DIR = PROJECT_ROOT / "model"
CACHE_DIR = PROJECT_ROOT / ".keras"
TEMP_DIR = PROJECT_ROOT / ".tmp"
os.environ.setdefault("KERAS_HOME", str(CACHE_DIR))
os.environ.setdefault("TMP", str(TEMP_DIR))
os.environ.setdefault("TEMP", str(TEMP_DIR))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEMP_DIR)
TRAIN_TYPE = os.getenv("TRAIN_TYPE", "all").strip().lower()
IMG_SIZE = int(os.getenv("IMG_SIZE", "128"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
EPOCHS = int(os.getenv("EPOCHS", "15"))
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_ALIASES = {
    "mask": {
        "positive": {"withmask", "with_mask", "mask", "masked"},
        "negative": {"withoutmask", "without_mask", "nomask", "no_mask", "no-mask"},
        "default_labels": ("without_mask", "with_mask"),
    },
    "glasses": {
        "positive": {"withglasses", "with_glasses", "glasses", "eyeglasses", "spectacles"},
        "negative": {
            "withoutglasses",
            "without_glasses",
            "noglasses",
            "no_glasses",
            "no-glasses",
        },
        "default_labels": ("without_glasses", "with_glasses"),
    },
}
def normalize_name(name: str) -> str:
    return "".join(char.lower() for char in name if char.isalnum() or char == "_")
def has_images(path: Path) -> bool:
    return any(file.suffix.lower() in IMAGE_EXTENSIONS for file in path.iterdir() if file.is_file())
def classify_folder(train_type: str, folder_name: str):
    aliases = CLASS_ALIASES[train_type]
    normalized = normalize_name(folder_name)
    if normalized in aliases["positive"]:
        return aliases["default_labels"][1]
    if normalized in aliases["negative"]:
        return aliases["default_labels"][0]
    return None
def collect_raw_sources(train_type: str):
    sources = {}
    if not RAW_DIR.exists():
        return sources
    for directory in RAW_DIR.rglob("*"):
        if not directory.is_dir() or not has_images(directory):
            continue
        label = classify_folder(train_type, directory.name)
        if label:
            sources.setdefault(label, []).append(directory)
    return sources
def prepare_labeled_dataset(train_type: str):
    destination_root = LABELED_DIR / train_type
    sources = collect_raw_sources(train_type)
    labels = CLASS_ALIASES[train_type]["default_labels"]
    if not all(label in sources for label in labels):
        raise FileNotFoundError(f"Missing classes in RAW for {train_type}")
    if destination_root.exists():
        shutil.rmtree(destination_root)
    for label in labels:
        target_dir = destination_root / label
        target_dir.mkdir(parents=True, exist_ok=True)
        idx = 0
        for source in sources[label]:
            for img in source.iterdir():
                if img.suffix.lower() in IMAGE_EXTENSIONS:
                    idx += 1
                    shutil.copy2(img, target_dir / f"{idx}{img.suffix}")
    return destination_root
def ensure_dataset(train_type: str):
    dataset_path = LABELED_DIR / train_type
    if dataset_path.exists():
        class_dirs = [p for p in dataset_path.iterdir() if p.is_dir()]
        if len(class_dirs) >= 2:
            print(f" Using labeled dataset for {train_type}")
            return dataset_path
    print(f" Building dataset from RAW for {train_type}")
    return prepare_labeled_dataset(train_type)
def build_model():
    try:
        base_model = MobileNetV2(
            input_shape=(IMG_SIZE, IMG_SIZE, 3),
            include_top=False,
            weights="imagenet",
        )
    except:
        base_model = MobileNetV2(
            input_shape=(IMG_SIZE, IMG_SIZE, 3),
            include_top=False,
            weights=None,
        )
    base_model.trainable = False
    model = Sequential([
        base_model,
        GlobalAveragePooling2D(),
        Dense(128, activation="relu"),
        Dropout(0.5),
        Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model
def list_dataset_files(dataset_path: Path):
    class_names = sorted(p.name for p in dataset_path.iterdir() if p.is_dir())
    file_paths, labels = [], []
    for i, cls in enumerate(class_names):
        for img in (dataset_path / cls).rglob("*"):
            if img.suffix.lower() in IMAGE_EXTENSIONS:
                file_paths.append(str(img))
                labels.append(float(i))
    if len(class_names) < 2:
        raise FileNotFoundError("Dataset needs 2 classes")
    rng = np.random.default_rng(42)
    indices = rng.permutation(len(file_paths))
    file_paths = [file_paths[i] for i in indices]
    labels = [labels[i] for i in indices]
    split = int(0.8 * len(file_paths))
    return (
        class_names,
        file_paths[:split],
        labels[:split],
        file_paths[split:],
        labels[split:],
    )
def decode_image(path, label):
    img = tf.io.read_file(path)
    img = tf.image.decode_jpeg(img, channels=3)
    img.set_shape([None, None, 3])
    img = tf.image.resize(img, [IMG_SIZE, IMG_SIZE])
    img = tf.cast(img, tf.float32) / 255.0
    return img, tf.expand_dims(label, axis=-1)
def build_tf_dataset(paths, labels):
    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    ds = ds.map(decode_image, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
def create_generators(dataset_path: Path):
    cls, tp, tl, vp, vl = list_dataset_files(dataset_path)
    train = build_tf_dataset(tp, tl)
    val = build_tf_dataset(vp, vl)
    train.class_names = cls
    val.class_names = cls
    return train, val
def save_labels(train_type, train_data):
    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_DIR / f"{train_type}_labels.txt", "w") as f:
        for i, name in enumerate(train_data.class_names):
            f.write(f"{i}:{name}\n")
def save_tflite(train_type, model):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite = converter.convert()
    with open(MODEL_DIR / f"{train_type}_model.tflite", "wb") as f:
        f.write(tflite)
def train_one(train_type):
    dataset_path = ensure_dataset(train_type)
    print(f"Dataset path: {dataset_path}")
    train, val = create_generators(dataset_path)
    print("Classes:", train.class_names)
    model = build_model()
    model.summary()
    model.fit(
        train,
        validation_data=val,
        epochs=EPOCHS,
        callbacks=[EarlyStopping(patience=3, restore_best_weights=True)],
    )
    model.save(MODEL_DIR / f"{train_type}_detector.keras")
    save_labels(train_type, train)
    save_tflite(train_type, model)
    print(f" Done: {train_type}")
def main():
    types = ["mask", "glasses"] if TRAIN_TYPE == "all" else [TRAIN_TYPE]
    for t in types:
        try:
            train_one(t)
        except Exception as e:
            print(f"Skipping {t}: {e}")
if __name__ == "__main__":
    main()