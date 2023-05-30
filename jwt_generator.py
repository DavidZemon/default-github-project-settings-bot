#!/usr/bin/env python3
import os

import jwt
import time

PRIVATE_KEY_FILE_PATH = os.getenv('KEY_FILE_PATH', 'key.pem')
APP_ID = os.getenv('APP_ID', '340328')


def generate():
    # Read the key
    with open(PRIVATE_KEY_FILE_PATH, 'rb') as pem_file:
        signing_key = jwt.jwk_from_pem(pem_file.read())

    payload = {
        # Issued at time
        'iat': int(time.time()),
        # JWT max expiration time is 10 minutes in the future. Server time can fall out of sync, so make the actual
        # expiration significantly less than 10 minutes in case the GH server clock is behind our clock
        'exp': int(time.time()) + 400,
        # GitHub App's identifier
        'iss': APP_ID
    }

    # Create JWT
    jwt_instance = jwt.JWT()
    encoded_jwt = jwt_instance.encode(payload, signing_key, alg='RS256')

    return encoded_jwt


if __name__ == '__main__':
    print(f'JWT: {generate()}')
