#!/bin/sh 

# create data directory if it does not exist
DIR_DATA=./data/ssl
if [ ! -d "$DIR_DATA" ]; then
    echo "CREATING DATA DIRECTORY: $DIR_DATA"
    mkdir -p $DIR_DATA
fi

# generate open ssl certificate if does not exist
FILE_SSL_CERT_PEM=./data/ssl/cert.pem
FILE_SSL_KEY_PEM=./data/ssl/key.pem
if [ ! -f "$FILE_SSL_CERT_PEM" ]; then
    echo "GENERATING SSL CERTIFICATE AND KEY AT: $FILE_SSL_CERT_PEM"
    openssl req -x509 -newkey rsa:4096 -nodes -out "$FILE_SSL_CERT_PEM" -keyout "$FILE_SSL_KEY_PEM" -days 365
fi

# start server
python controller/app.py ./data