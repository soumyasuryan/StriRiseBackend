import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report
from xgboost import XGBClassifier
import joblib
import warnings

warnings.filterwarnings("ignore")

# -------------------------------------------------
# 1️⃣ Load Dataset
# -------------------------------------------------
try:
    df = pd.read_csv("expanded_business_recommendation_dataset.csv")
    print("✅ Dataset loaded successfully!")
    print(f"Shape: {df.shape}")
    print("Columns:", df.columns.tolist())
except Exception as e:
    print("❌ Error loading dataset:", e)
    exit()

# -------------------------------------------------
# 2️⃣ Basic Cleaning
# -------------------------------------------------
df.fillna("Unknown", inplace=True)

# Make sure string columns are properly stripped
for col in df.select_dtypes(include="object"):
    df[col] = df[col].astype(str).str.strip()

# Add derived feature: check if user owns digital assets
df["Is_Digital_Asset"] = df["Assets_Owned"].apply(
    lambda x: 1 if isinstance(x, str) and ("Internet" in x or "Phone" in x) else 0
)

# -------------------------------------------------
# 3️⃣ Label Encode Target Variable
# -------------------------------------------------
label_encoder = LabelEncoder()
df["Business_Category"] = label_encoder.fit_transform(df["Business_Category"])
joblib.dump(label_encoder, "business_label_encoder.joblib")

# -------------------------------------------------
# 4️⃣ Balance Data (optional)
# -------------------------------------------------
df_balanced = (
    df.groupby("Business_Category", group_keys=False)
    .apply(lambda x: x.sample(n=df["Business_Category"].value_counts().max(), replace=True))
)
print(f"Balanced dataset shape: {df_balanced.shape}")

# -------------------------------------------------
# 5️⃣ Define Features & Target
# -------------------------------------------------
X = df_balanced.drop(
    ["Recommended_Business_Idea", "Business_Category", "User_Satisfaction"], axis=1
)
y = df_balanced["Business_Category"]

# Identify column types
categorical_cols = X.select_dtypes(include="object").columns.tolist()
numerical_cols = X.select_dtypes(include=["int64", "float64"]).columns.tolist()

# -------------------------------------------------
# 6️⃣ Preprocessing Pipeline
# -------------------------------------------------
preprocessor = ColumnTransformer(
    transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
        ("num", StandardScaler(), numerical_cols),
    ]
)

# -------------------------------------------------
# 7️⃣ Build ML Pipeline (XGBoost)
# -------------------------------------------------
model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            XGBClassifier(
                n_estimators=200,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
                use_label_encoder=False,
                eval_metric="mlogloss",
            ),
        ),
    ]
)

# -------------------------------------------------
# 8️⃣ Train-Test Split
# -------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# -------------------------------------------------
# 9️⃣ Train Model
# -------------------------------------------------
print("\n🚀 Training model...")
model.fit(X_train, y_train)

# -------------------------------------------------
# 🔟 Evaluate
# -------------------------------------------------
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\n✅ Model Evaluation")
print("Accuracy:", round(accuracy, 2))
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# -------------------------------------------------
# 11️⃣ Save Model
# -------------------------------------------------
joblib.dump(model, "business_recommendation_model.joblib")
print("\n🎯 Model saved as 'business_recommendation_model.joblib'")
