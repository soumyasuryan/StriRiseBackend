import pandas as pd
import os

# Build full path dynamically
base_dir = os.path.dirname(__file__)  # folder where predict.py is located
csv_path = os.path.join(base_dir, "expanded_business_recommendation_dataset.csv")

print("📂 Looking for CSV at:", csv_path)

df = pd.read_csv(csv_path)
print("✅ Dataset loaded successfully!")
print(df.head())
print("Shape:", df.shape)
print("Columns:", df.columns.tolist())

# Check for unique values in Practical_Skills
print("\n🔍 Unique values in 'Practical_Skills':")
print(df["Practical_Skills"].value_counts(dropna=False))

# Or just the unique list (if you don’t want counts)
# print(df["Practical_Skills"].unique())

# Check for unique values in Interest_Area
print("\n🔍 Unique values in 'Interest_Area':")
print(df["Interest_Area"].value_counts(dropna=False))

# Optional: number of unique entries
print("\nTotal unique Practical_Skills:", df["Practical_Skills"].nunique())
print("Total unique Interest_Area:", df["Interest_Area"].nunique())
