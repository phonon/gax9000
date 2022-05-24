:: create directory for ssl certificates if it does not exist
set "DIR_SSL=%~dp0data\ssl\"
echo %DIR_SSL%
if not exist %DIR_SSL% (
    echo CREATING DATA DIRECTORY: %DIR_SSL%
    mkdir %DIR_SSL%
)

:: generate open ssl certificate if does not exist
:: https://security.stackexchange.com/questions/74345/provide-subjectaltname-to-openssl-directly-on-the-command-line/198409#198409
:: Note: "DNS:" needed before localhost
set "FILE_SSL_CERT_PEM=%DIR_SSL%cert.pem"
set "FILE_SSL_KEY_PEM=%DIR_SSL%key.pem"
if not exist %FILE_SSL_CERT_PEM% (
    echo GENERATING SSL CERTIFICATE AND KEY AT: %FILE_SSL_CERT_PEM%
    openssl req -x509 -newkey rsa:4096 -days 365 -nodes ^
        -out "%FILE_SSL_CERT_PEM%" -keyout "%FILE_SSL_KEY_PEM%" -subj "/CN=acyu/emailAddress=acyu@mit.edu/C=US/ST=MA/L=Boston/O=MIT" ^
        -addext "subjectAltName=DNS:localhost"
)

:: start server
python controller\app.py data
