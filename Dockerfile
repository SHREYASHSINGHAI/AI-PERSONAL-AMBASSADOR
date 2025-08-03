# Dockerfile
# Use a lightweight Python base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port that the app will run on
EXPOSE 5000

# Command to run the application with Gunicorn
# Using gunicorn as the web server is more memory-efficient than Flask's
# built-in development server.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]
