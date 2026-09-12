import torch
from PIL import Image
from torchvision import transforms
from huggingface_hub import hf_hub_download
import timm


print("Loading AgroScan Plant Disease AI...")


# Download model files
model_file = hf_hub_download(
    repo_id="imaflower/plantvillage-mobilenetv3",
    filename="pytorch_model.bin"
)

print("Model downloaded successfully!")


# Load MobileNetV3
model = timm.create_model(
    "mobilenetv3_large_100",
    pretrained=False,
    num_classes=15
)

checkpoint = torch.load(
    model_file,
    map_location="cpu"
)

model.load_state_dict(checkpoint)

model.eval()

print("Plant disease model loaded successfully!")


# Ask for image
image_path = input(
    "Enter the path of your crop image: "
)

image = Image.open(image_path).convert("RGB")


# Image preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


image_tensor = transform(image).unsqueeze(0)


# Prediction
with torch.no_grad():

    output = model(image_tensor)

    probabilities = torch.softmax(
        output,
        dim=1
    )

    confidence, predicted_class = torch.max(
        probabilities,
        dim=1
    )


print()
print("================================")
print("       AGROSCAN AI RESULT")
print("================================")

print(
    "Prediction class:",
    predicted_class.item()
)

print(
    "Confidence:",
    round(
        confidence.item() * 100,
        2
    ),
    "%"
)

print("================================")