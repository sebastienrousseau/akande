# Use the official Python image as a base
FROM python:3.8-slim

# Install system dependencies
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes pulseaudio-utils \
    && apt-get install -y gcc portaudio19-dev alsa-utils pulseaudio ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/run/pulse /var/lib/pulse /var/cache/pulse \
    && chmod 1777 /var/run/pulse /var/lib/pulse /var/cache/pulse \
    && getent group pulse-access || groupadd -r pulse-access \
    && usermod -a -G pulse-access root

COPY pulse-client.conf /etc/pulse/client.conf

USER $UNAME
ENV HOME /home/akande

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Run the application
CMD ["python", "./akande/__main__.py"]
