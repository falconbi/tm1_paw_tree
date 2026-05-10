FROM python:3.11-slim

WORKDIR /app

COPY requirements.docker.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Remove files that should not ship in the image
RUN rm -f cube_map/tm1_model.json .env

EXPOSE 8082

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8082", "--timeout", "120", "app:app"]
