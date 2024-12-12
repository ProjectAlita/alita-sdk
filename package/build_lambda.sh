#!/bin/bash

mkdir package/lambda
docker run --rm -v "$PWD/package":/var/task getcarrier/lambda:python3.10-build pip install -r requirements.txt -t /var/task/lambda
cp package/handler.py package/lambda
cd package/lambda
zip alita-sdk.zip -r .
cp alita-sdk.zip ../
cd ..
rm -rf lambda
cd ..

