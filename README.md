# AgroScan – Smart Farming Companion

AgroScan is an AI-powered smart farming application that uses deep learning to identify crop diseases from leaf images and provide useful farming recommendations.

## Technologies Used

- Python
- FastAPI
- PyTorch
- Torchvision
- MobileNetV3
- PlantVillage Dataset
- HTML
- CSS
- JavaScript

## Machine Learning Model

The project uses a MobileNetV3 deep-learning model trained using the PlantVillage dataset.

### Model Performance

- Crops: 5
- Disease Classes: 14
- Training Epochs: 8
- Test Accuracy: 99.39%
- Precision: 99.41%
- Recall: 99.39%
- F1 Score: 99.39%

## Features

- Crop leaf image analysis
- AI-based disease identification
- Disease confidence score
- Health assessment
- Weather risk information
- Treatment recommendations
- Soil assessment
- Scan history
- Hindi/English voice guidance
- FastAPI backend
- Swagger API documentation

## API Endpoint

POST `/api/crop/analyze`

The user uploads a crop leaf image and the FastAPI server processes it using the trained deep-learning model.

## Project Structure

```text
AgroSCan/
├── frontend/
├── backend/
├── models/
├── requirements.txt
├── README.md
└── .gitignore
