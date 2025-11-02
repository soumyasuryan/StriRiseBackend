import pandas as pd
import joblib

# Load model and encoder
model = joblib.load("business_recommendation_model.joblib")
label_encoder = joblib.load("business_label_encoder.joblib")

# Create a single test input
user_input = pd.DataFrame([{
    "Age": 32,
    "Gender": "Female",
    "Location_Type": "Rural",
    "Budget_Range": "Low",
    "Practical_Skills": "Handicraft",
    "Interest_Area": "Education",
    "Work_Mode": "Home-based",
    "Risk_Tolerance": "Low",
    "Available_Time_Per_Day": 6,
    "Literacy_Level": "Moderate",
    "Assets_Owned": "Phone",
    "Community_Support_Level": "High",
    "Is_Digital_Asset": 1,
    "Feasibility_Score": 0.7
}])

# Predict
prediction = model.predict(user_input)
business = label_encoder.inverse_transform(prediction)

print(f"🎯 Recommended Business Category: {business[0]}")
