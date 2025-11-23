# Käytetään virallista Python 3.12 -kuvaa
FROM python:3.12-slim

# Aseta työskentelyhakemisto konttiin
WORKDIR /app

# Kopioi kaikki tiedostot nykyisestä kansiosta konttiin
COPY . .

# Asenna riippuvuudet
RUN pip install --no-cache-dir -r requirements.txt

# Käynnistä ohjelma (main.py)
CMD ["python", "main.py"]
