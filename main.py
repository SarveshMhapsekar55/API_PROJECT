from fastapi import FastAPI, UploadFile, File, Form
from typing import Literal
from fastapi.middleware.cors import CORSMiddleware

import torch
import torch.nn as nn

from torchvision import transforms, models

from PIL import Image

import io
import os
import json
import requests


# ============================================================
# AGROSCAN API
# ============================================================

app = FastAPI(
    title="AgroScan API",
    description="AI-Based Smart Farming Companion API",
    version="2.1.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "agroscan_model.pth"
)

CLASS_PATH = os.path.join(
    BASE_DIR,
    "models",
    "class_names.json"
)


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device("cpu")


# ============================================================
# LOAD CLASS NAMES
# ============================================================

with open(CLASS_PATH, "r") as file:
    CLASS_NAMES = json.load(file)


NUM_CLASSES = len(CLASS_NAMES)


# ============================================================
# LOAD AGROSCAN MODEL
# ============================================================

print("Loading AgroScan AI model...")

model = models.mobilenet_v3_small(
    weights=None
)

input_features = model.classifier[3].in_features

model.classifier[3] = nn.Linear(
    input_features,
    NUM_CLASSES
)


model.load_state_dict(
    torch.load(
        MODEL_PATH,
        map_location=DEVICE
    )
)

model = model.to(DEVICE)

model.eval()

print("AgroScan AI model loaded successfully!")

print(
    f"Number of classes: {NUM_CLASSES}"
)


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

image_transform = transforms.Compose([

    transforms.Resize(
        (224, 224)
    ),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[
            0.485,
            0.456,
            0.406
        ],

        std=[
            0.229,
            0.224,
            0.225
        ]
    )
])


# ============================================================
# DISEASE INFORMATION
# ============================================================

DISEASE_INFO = {

    "healthy": {

        "severity": "Healthy",

        "symptoms": [
            "No major disease symptoms detected",
            "Leaf appearance is consistent with a healthy plant"
        ],

        "actions": [
            "Continue regular crop monitoring",
            "Maintain proper irrigation",
            "Maintain balanced plant nutrition",
            "Monitor new leaves for any changes"
        ],

        "treatment_window":
            "No treatment required"
    },


    "Early blight": {

        "severity": "Moderate",

        "symptoms": [
            "Brown or dark spots on leaves",
            "Circular or concentric lesions",
            "Yellowing around infected areas"
        ],

        "actions": [
            "Remove severely infected leaves",
            "Improve air circulation between plants",
            "Avoid overhead irrigation",
            "Remove infected plant debris",
            "Monitor the crop regularly"
        ],

        "treatment_window":
            "Early action recommended"
    },


    "Late blight": {

        "severity": "High",

        "symptoms": [
            "Dark irregular lesions on leaves",
            "Rapid browning of infected tissue",
            "Yellowing or dying leaves"
        ],

        "actions": [
            "Remove severely infected plant material",
            "Improve air circulation",
            "Avoid overhead irrigation",
            "Monitor nearby plants for symptoms"
        ],

        "treatment_window":
            "Immediate attention recommended"
    },


    "Bacterial spot": {

        "severity": "Moderate",

        "symptoms": [
            "Small dark spots on leaves",
            "Yellow halos around lesions",
            "Progressive leaf damage"
        ],

        "actions": [
            "Remove severely affected leaves",
            "Avoid working with wet plants",
            "Improve air circulation",
            "Monitor disease progression"
        ],

        "treatment_window":
            "Early action recommended"
    },


    "Common rust": {

        "severity": "Moderate",

        "symptoms": [
            "Rust-colored spots on leaves",
            "Small raised lesions",
            "Progressive leaf discoloration"
        ],

        "actions": [
            "Remove heavily affected leaves",
            "Improve air circulation",
            "Monitor surrounding plants",
            "Avoid excessive leaf moisture"
        ],

        "treatment_window":
            "Early action recommended"
    },


    "Northern Leaf Blight": {

        "severity": "High",

        "symptoms": [
            "Long gray or brown lesions",
            "Leaf discoloration",
            "Progressive drying of affected leaves"
        ],

        "actions": [
            "Remove severely affected plant material",
            "Improve field air circulation",
            "Avoid excessive moisture",
            "Monitor nearby plants"
        ],

        "treatment_window":
            "Early intervention recommended"
    },


    "Black rot": {

        "severity": "High",

        "symptoms": [
            "Dark lesions on leaves",
            "Yellowing around affected areas",
            "Progressive tissue damage"
        ],

        "actions": [
            "Remove infected plant material",
            "Improve air circulation",
            "Remove infected debris",
            "Monitor surrounding plants"
        ],

        "treatment_window":
            "Early intervention recommended"
    },


    "Esca Black Measles": {

        "severity": "High",

        "symptoms": [
            "Leaf discoloration",
            "Spotted or damaged leaf tissue",
            "Progressive decline of affected foliage"
        ],

        "actions": [
            "Remove severely affected material",
            "Maintain good vineyard sanitation",
            "Improve plant health",
            "Monitor nearby vines"
        ],

        "treatment_window":
            "Early attention recommended"
    }
}

# ============================================================
# WEATHER FUNCTIONS
# ============================================================

def get_weather(location):
    """
    Resolve any user-entered place name to coordinates and fetch
    current weather for that exact resolved location.
    """

    location = (location or "").strip()

    if not location:
        return {
            "status": "error",
            "message": "Location is required."
        }

    try:
        # ----------------------------------------------------
        # STEP 1: GEOCODE LOCATION -> LATITUDE / LONGITUDE
        # ----------------------------------------------------

        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"

        geocode_params = {
            "name": location,
            "count": 10,
            "language": "en",
            "format": "json"
        }

        geocode_response = requests.get(
            geocode_url,
            params=geocode_params,
            timeout=15
        )
        geocode_response.raise_for_status()
        geocode_data = geocode_response.json()

        results = geocode_data.get("results", [])

        if not results:
            return {
                "status": "Location not found",
                "message": (
                    f"AgroScan could not find '{location}'. "
                    "Try a city, area, or postal code."
                ),
                "searched_location": location
            }

        # Prefer an Indian result when the user entered an Indian
        # locality such as Andheri, Kandivali, Virar, etc. This is
        # NOT hard-coded to any one city.
        indian_results = [
            r for r in results
            if str(r.get("country_code", "")).upper() == "IN"
        ]

        place = indian_results[0] if indian_results else results[0]

        latitude = float(place["latitude"])
        longitude = float(place["longitude"])

        matched_location = place.get("name", location)
        admin1 = place.get("admin1", "")
        admin2 = place.get("admin2", "")
        country = place.get("country", "")
        country_code = place.get("country_code", "")
        timezone = place.get("timezone", "")
        elevation = place.get("elevation")

        # ----------------------------------------------------
        # STEP 2: WEATHER USING THE RESOLVED COORDINATES
        # ----------------------------------------------------

        weather_url = "https://api.open-meteo.com/v1/forecast"

        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "precipitation,"
                "weather_code"
            ),
            "hourly": "precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto"
        }

        weather_response = requests.get(
            weather_url,
            params=weather_params,
            timeout=15
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        current = weather_data.get("current", {})

        temperature = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        precipitation = current.get("precipitation")
        weather_code = current.get("weather_code")
        current_time = current.get("time")

        # ----------------------------------------------------
        # STEP 3: FIND PRECIPITATION PROBABILITY FOR THE
        # CURRENT/NEAREST HOURLY FORECAST, NOT ALWAYS HOUR 0
        # ----------------------------------------------------

        hourly = weather_data.get("hourly", {})
        hourly_times = hourly.get("time", [])
        probability_values = hourly.get(
            "precipitation_probability", []
        )

        precipitation_probability = None

        if hourly_times and probability_values:
            if current_time in hourly_times:
                index = hourly_times.index(current_time)
            else:
                # Fallback: choose the closest available forecast hour.
                try:
                    from datetime import datetime

                    current_dt = datetime.fromisoformat(
                        current_time
                    )

                    parsed_times = [
                        datetime.fromisoformat(t)
                        for t in hourly_times
                    ]

                    index = min(
                        range(len(parsed_times)),
                        key=lambda i: abs(
                            parsed_times[i] - current_dt
                        )
                    )
                except Exception:
                    index = 0

            if index < len(probability_values):
                precipitation_probability = probability_values[index]

        if precipitation_probability is None:
            precipitation_probability = 0

        # ----------------------------------------------------
        # STEP 4: WEATHER DESCRIPTION
        # ----------------------------------------------------

        weather_condition = get_weather_condition(weather_code)

        # ----------------------------------------------------
        # STEP 5: SIMPLE DISEASE WEATHER-RISK SCORE
        # ----------------------------------------------------

        risk_score = 0

        if humidity is not None:
            if humidity >= 80:
                risk_score += 40
            elif humidity >= 65:
                risk_score += 25

        if precipitation_probability >= 60:
            risk_score += 35
        elif precipitation_probability >= 30:
            risk_score += 20

        if temperature is not None:
            if 18 <= temperature <= 30:
                risk_score += 25
            elif 15 <= temperature <= 33:
                risk_score += 10

        if risk_score >= 70:
            risk_level = "High"
        elif risk_score >= 40:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        # ----------------------------------------------------
        # STEP 6: RETURN A CLEAN, FRONTEND-FRIENDLY STRUCTURE
        # ----------------------------------------------------

        location_information = {
            "searched_location": location,
            "matched_location": matched_location,
            "area": admin1,
            "sub_area": admin2,
            "country": country,
            "country_code": country_code,
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "timezone": timezone,
            "elevation": elevation
        }

        weather = {
            "temperature": temperature,
            "humidity": humidity,
            "rain_probability": precipitation_probability,
            "precipitation": precipitation,
            "condition": weather_condition,
            "weather_code": weather_code,
            "observed_at": current_time,
            "timezone": timezone
        }

        disease_weather_risk = {
            "score": min(risk_score, 100),
            "risk_level": risk_level,
            "message": (
                "Weather conditions may support disease spread."
                if risk_level == "High"
                else "Weather conditions require monitoring."
                if risk_level == "Moderate"
                else "Current weather conditions show lower disease risk."
            )
        }

        return {
            "status": "success",
            "location_information": location_information,
            "weather": weather,
            "disease_weather_risk": disease_weather_risk
        }

    except requests.RequestException as e:
        return {
            "status": "Weather service unavailable",
            "searched_location": location,
            "message": "Could not connect to the location/weather service.",
            "error": str(e)
        }

    except Exception as e:
        return {
            "status": "Weather analysis failed",
            "searched_location": location,
            "message": "An unexpected error occurred while fetching weather.",
            "error": str(e)
        }


# ============================================================
# WEATHER CODE DESCRIPTION
# ============================================================

def get_weather_condition(code):

    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail"
    }

    return weather_codes.get(
        code,
        "Unknown"
    )

# ============================================================
# SOIL ASSESSMENT LOGIC
# ============================================================

def assess_soil(
    soil_moisture,
    drainage,
    watering_frequency,
    plant_growth
):
    """Calculate a simple questionnaire-based soil health score."""

    score = 100
    recommendations = []

    # --------------------------------------------------------
    # Soil moisture
    # --------------------------------------------------------

    if soil_moisture == "very_dry":
        score -= 20
        recommendations.append(
            "Increase irrigation gradually and maintain consistent soil moisture."
        )

    elif soil_moisture == "very_wet":
        score -= 20
        recommendations.append(
            "Reduce excessive watering and check drainage to prevent waterlogging."
        )

    # --------------------------------------------------------
    # Drainage
    # --------------------------------------------------------

    if drainage == "quick":
        score -= 10
        recommendations.append(
            "Monitor soil moisture because water may drain quickly."
        )

    elif drainage == "slow":
        score -= 20
        recommendations.append(
            "Improve drainage where possible to reduce prolonged waterlogging."
        )

    # --------------------------------------------------------
    # Watering frequency
    # --------------------------------------------------------

    if watering_frequency == "rarely":
        score -= 10
        recommendations.append(
            "Check soil regularly and water when the crop actually needs it."
        )

    elif watering_frequency == "frequently":
        score -= 15
        recommendations.append(
            "Avoid unnecessary frequent irrigation."
        )

    # "once_or_twice" and "depends_on_weather" are treated as
    # reasonable practices and do not reduce the score.

    # --------------------------------------------------------
    # Plant growth
    # --------------------------------------------------------

    if plant_growth == "sometimes_poor":
        score -= 10
        recommendations.append(
            "Monitor plant growth and review moisture and nutrient conditions."
        )

    elif plant_growth == "poor":
        score -= 20
        recommendations.append(
            "Poor growth may indicate moisture, nutrient or soil-condition problems."
        )

    score = max(0, min(100, score))

    # --------------------------------------------------------
    # Overall condition
    # --------------------------------------------------------

    if score >= 80:
        condition = "Good"
        explanation = (
            "Your answers indicate generally suitable soil conditions for crop growth."
        )

    elif score >= 60:
        condition = "Moderate"
        explanation = (
            "Your answers indicate that some soil conditions may need attention."
        )

    else:
        condition = "Needs Attention"
        explanation = (
            "Your answers indicate possible soil moisture, drainage or growth problems."
        )

    if not recommendations:
        recommendations.append(
            "Continue regular monitoring of soil moisture, drainage and plant growth."
        )

    return {
        "condition": condition,
        "score": score,
        "health_score": score,
        "explanation": explanation,
        "recommendations": recommendations,
        "assessment_type": "Questionnaire-based soil assessment"
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    return {
        "message": "Welcome to AgroScan API",
        "status": "running",
        "version": "2.2.0",
        "model": "MobileNetV3",
        "classes": NUM_CLASSES,
        "features": [
            "AI crop and disease classification",
            "Dynamic location and weather analysis",
            "Optional questionnaire-based soil assessment",
            "English and Hindi voice guidance"
        ]
    }


# ============================================================
# CROP ANALYSIS API
# ============================================================

@app.post("/api/crop/analyze")
async def analyze_crop(
    image: UploadFile = File(...),
    location: str = Form(...),
    language: str = Form(...)
):
    """
    Analyze a crop-leaf image using the trained MobileNetV3 model.

    The endpoint:
    1. Reads and validates the uploaded image.
    2. Predicts crop + disease from the trained 14-class model.
    3. Resolves the user-entered location to latitude/longitude.
    4. Fetches live weather for the resolved coordinates.
    5. Returns a structured report suitable for the AgroScan frontend.

    Soil is intentionally NOT guessed here. The frontend can call
    /api/soil/assess separately after the user chooses to complete
    the optional soil questionnaire.
    """

    # --------------------------------------------------------
    # Validate location
    # --------------------------------------------------------

    location = (location or "").strip()

    if not location:
        return {
            "status": "error",
            "message": "Location is required."
        }

    # --------------------------------------------------------
    # Read uploaded image
    # --------------------------------------------------------

    image_bytes = await image.read()

    try:
        leaf_image = Image.open(
            io.BytesIO(image_bytes)
        ).convert("RGB")
    except Exception:
        return {
            "status": "error",
            "message": "Invalid image file. Please upload a JPG, PNG or WEBP image."
        }

    # --------------------------------------------------------
    # Preprocess image
    # --------------------------------------------------------

    input_tensor = image_transform(
        leaf_image
    ).unsqueeze(0)

    # --------------------------------------------------------
    # AI prediction
    # --------------------------------------------------------

    with torch.no_grad():
        outputs = model(input_tensor)

        probabilities = torch.softmax(
            outputs,
            dim=1
        )

        confidence, prediction = torch.max(
            probabilities,
            dim=1
        )

    predicted_index = prediction.item()
    confidence_value = confidence.item() * 100

    predicted_class = CLASS_NAMES[predicted_index]

    # --------------------------------------------------------
    # Split crop and disease
    # --------------------------------------------------------

    if "___" in predicted_class:
        crop_name, disease_name = predicted_class.split(
            "___",
            1
        )
    else:
        crop_name = predicted_class
        disease_name = "Unknown"

    # --------------------------------------------------------
    # Clean crop name
    # --------------------------------------------------------

    crop_name = (
        crop_name
        .replace("_(maize)", "")
        .replace("_", " ")
        .replace(",", "")
        .strip()
    )

    # --------------------------------------------------------
    # Clean disease name
    # --------------------------------------------------------

    disease_name = (
        disease_name
        .replace("_", " ")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    # --------------------------------------------------------
    # Disease information
    # --------------------------------------------------------

    is_healthy = "healthy" in disease_name.lower()

    if is_healthy:
        info = DISEASE_INFO["healthy"]
    else:
        info = DISEASE_INFO.get(
            disease_name,
            {
                "severity": "Requires Attention",
                "symptoms": [
                    "Disease detected by the trained AI image classifier"
                ],
                "actions": [
                    "Monitor the affected plant",
                    "Remove severely affected leaves",
                    "Maintain good air circulation",
                    "Monitor disease progression"
                ],
                "treatment_window": "Early action recommended"
            }
        )

    # --------------------------------------------------------
    # Dynamic location + weather
    # --------------------------------------------------------

    weather_result = get_weather(location)

    location_information = weather_result.get(
        "location_information",
        {}
    )

    weather_information = weather_result.get(
        "weather",
        {}
    )

    disease_weather_risk = weather_result.get(
        "disease_weather_risk",
        {}
    )

    # --------------------------------------------------------
    # Numeric severity score for the frontend speedometer
    # --------------------------------------------------------

    severity_label = info["severity"]

    if severity_label == "Healthy":
        severity_score = 5
    elif severity_label == "Moderate":
        severity_score = 55
    elif severity_label == "High":
        severity_score = 85
    else:
        severity_score = 70

    # --------------------------------------------------------
    # Structured response
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": "Crop analysis completed successfully",

        "request_information": {
            "filename": image.filename,
            "location": location,
            "language": language
        },

        "ai_analysis": {
            "crop": crop_name,
            "disease": disease_name,
            "confidence": round(confidence_value, 2),
            "model": "MobileNetV3",
            "classification_classes": NUM_CLASSES
        },

        "health_assessment": {
            "severity": info["severity"],
            "severity_score": severity_score,
            "affected_area": "Leaf area assessed from the uploaded image",
            "disease_stage": "Initial AI assessment",
            "symptoms_detected": info["symptoms"]
        },

        "location_information": location_information,

        "weather": weather_information,

        "weather_risk": {
            "temperature": weather_information.get("temperature"),
            "humidity": weather_information.get("humidity"),
            "rain_probability": weather_information.get("rain_probability"),
            "precipitation": weather_information.get("precipitation"),
            "condition": weather_information.get("condition"),
            "risk_level": disease_weather_risk.get("risk_level"),
            "risk_score": disease_weather_risk.get("score"),
            "risk_message": disease_weather_risk.get("message"),
            "status": weather_result.get("status")
        },

        # Soil is optional and must come from the questionnaire.
        "soil_condition": {
            "status": "Not assessed yet",
            "message": "Complete the optional soil questionnaire to add soil assessment."
        },

        "recommended_action": info["actions"],
        "treatment_window": info["treatment_window"],
        "voice_guidance_available": True,
        "voice_languages": ["English", "Hindi"]
    }


# ============================================================
# SOIL ASSESSMENT API
# ============================================================

@app.post("/api/soil/assess")
async def soil_assessment(
    soil_moisture: Literal[
        "very_dry",
        "normal",
        "very_wet"
    ] = Form(...),

    drainage: Literal[
        "quick",
        "normal",
        "slow"
    ] = Form(...),

    watering_frequency: Literal[
        "rarely",
        "once_or_twice",
        "frequently",
        "depends_on_weather"
    ] = Form(...),

    plant_growth: Literal[
        "healthy",
        "sometimes_poor",
        "poor"
    ] = Form(...)
):
    """
    Questionnaire-based soil assessment.

    IMPORTANT:
    - This endpoint expects multipart/form-data.
    - The four values must match the option values used by the frontend.
    - No laboratory pH/N/P/K values are invented.
    """

    result = assess_soil(
        soil_moisture,
        drainage,
        watering_frequency,
        plant_growth
    )

    return {
        "status": "success",
        "message": "Soil assessment completed successfully",
        "soil_assessment": result,
        "assessment_method": "User observation based questionnaire",
        "voice_guidance_available": True,
        "voice_languages": ["English", "Hindi"]
    }
