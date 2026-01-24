import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import os
TRAIN_TYPE = "mask"

DATASET_PATHS = {
    "mask": "../data/labeled/mask",
    "glasses": "../data/labeled/glasses"
}

MODEL_PATHS = {
    "mask": "model/mask_detector.h5",
    "glasses": "model/glasses_detector.h5"
}

LABELS = {
    "mask": ["without_mask", "with_mask"],
    "glasses": ["without_glasses", "with_glasses"]
}

IMG_SIZE = 128
BATCH_SIZE = 32
EPOCHS = 10
datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    validation_split=0.2
)

train_data = datagen.flow_from_directory(
    DATASET_PATHS[TRAIN_TYPE],
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="binary",
    subset="training"
)

val_data = datagen.flow_from_directory(
    DATASET_PATHS[TRAIN_TYPE],
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="binary",
    subset="validation"
)
model = Sequential([
    Conv2D(32, (3, 3), activation="relu", input_shape=(IMG_SIZE, IMG_SIZE, 3)),
    MaxPooling2D(2, 2),

    Conv2D(64, (3, 3), activation="relu"),
    MaxPooling2D(2, 2),

    Flatten(),
    Dense(128, activation="relu"),
    Dropout(0.5),
    Dense(1, activation="sigmoid")
])

model.compile(
    optimizer="adam",
    loss="binary_crossentropy",
    metrics=["accuracy"]
)
model.fit(
    train_data,
    validation_data=val_data,
    epochs=EPOCHS
)
os.makedirs("model", exist_ok=True)
model.save(MODEL_PATHS[TRAIN_TYPE])

with open("model/labels.txt", "w") as f:
    f.write(f"0:{LABELS[TRAIN_TYPE][0]}\n")
    f.write(f"1:{LABELS[TRAIN_TYPE][1]}\n")

print(f"Training completed for {TRAIN_TYPE} model.")
