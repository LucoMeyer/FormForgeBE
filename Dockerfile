# Use the official Python image from the Docker Hub
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Increase system limits
RUN ulimit -n 2048

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
# RUN pip install --upgrade pip && pip install --no-cache-dir Flask
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Make port 12345 available to the world outside this container
EXPOSE 12345

# Define environment variable
ENV NAME World

# Run app.py when the container launches
CMD ["python", "app.py"]

