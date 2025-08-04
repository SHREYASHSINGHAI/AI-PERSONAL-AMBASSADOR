# Dockerfile
# Use a lightweight Python base image. This helps reduce memory overhead.
FROM python:3.9-slim

# Set the working directory inside the container.
WORKDIR /app

# Copy the requirements file and install dependencies first.
# This step is cached, so it's only re-run when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Expose the port that the app will run on.
EXPOSE 5000

# Use Gunicorn, a lightweight production web server, to run the app.
# By setting --workers=1, we ensure only one process runs, which
# significantly reduces the memory footprint during deployment.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app", "--workers=1"]
