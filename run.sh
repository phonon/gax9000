#!/bin/sh 

# If running on bash for Windows, any argument starting with a forward slash is automatically
# interpreted as a drive path. To stop that, you can prefix with 2 forward slashes instead
# of 1 - but in the specific case of openssl, that causes the first CN segment key to be read as
# "/O" instead of "O", and is skipped. We work around that by prefixing with a spurious segment,
# which will be skipped by openssl
# https://stackoverflow.com/questions/54258996/git-bash-string-parameter-with-at-start-is-being-expanded-to-a-file-path
function fix_slash_on_windows() {
    local result="${1}"
    case $OSTYPE in
        msys|win32) result="//SKIP=skip${result}"
    esac
    echo "$result"
}

# create directory for ssl certificates if it does not exist
DIR_SSL=./settings/ssl
if [ ! -d "$DIR_SSL" ]; then
    echo "CREATING SETTINGS DIRECTORY: $DIR_SSL"
    mkdir -p $DIR_SSL
fi

# generate open ssl certificate if does not exist
# https://security.stackexchange.com/questions/74345/provide-subjectaltname-to-openssl-directly-on-the-command-line/198409#198409
# Note: "DNS:" needed before localhost
FILE_SSL_CERT_PEM=./settings/ssl/cert.pem
FILE_SSL_KEY_PEM=./settings/ssl/key.pem
if [ ! -f "$FILE_SSL_CERT_PEM" ]; then
    echo "GENERATING SSL CERTIFICATE AND KEY AT: $FILE_SSL_CERT_PEM"
    openssl req -x509 -newkey rsa:4096 -days 365 -nodes \
        -out "$FILE_SSL_CERT_PEM" -keyout "$FILE_SSL_KEY_PEM" -subj $(fix_slash_on_windows "/CN=acyu/emailAddress=acyu@mit.edu/C=US/ST=MA/L=Boston/O=MIT") \
        -addext "subjectAltName=DNS:localhost"
fi

# start server
python controller/app.py ./settings