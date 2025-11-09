# Use an official Python base image, for example Python 3.12-slim
FROM python:3.12-slim

# Install gfortran and build dependencies
RUN apt-get update && apt-get install -y build-essential gfortran

# Set working directory
WORKDIR /app

# Copy your project files into the container
COPY . .

# Upgrade pip, setuptools, wheel, and install dependencies
RUN pip install --upgrade pip setuptools wheel cython
RUN pip install -r requirements.txt

# Specify command to run your Flask app (change if needed)
CMD ["python", "app.py"]
