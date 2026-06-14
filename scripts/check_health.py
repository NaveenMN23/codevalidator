import os
import sys
import socket
import psycopg2
import redis
import pika
import boto3
from botocore.config import Config

def check_postgres():
    print("Checking PostgreSQL...", end=" ")
    try:
        conn = psycopg2.connect(
            dbname="interview_db",
            user="admin",
            password="password",
            host="localhost",
            port="5432"
        )
        conn.close()
        print("✅ OK")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def check_redis():
    print("Checking Redis...", end=" ")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
        r.ping()
        print("✅ OK")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def check_rabbitmq():
    print("Checking RabbitMQ...", end=" ")
    try:
        credentials = pika.PlainCredentials('admin', 'password')
        parameters = pika.ConnectionParameters('localhost', 5672, '/', credentials, socket_timeout=2)
        connection = pika.BlockingConnection(parameters)
        connection.close()
        print("✅ OK")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def check_minio():
    print("Checking MinIO...", end=" ")
    try:
        s3 = boto3.client(
            's3',
            endpoint_url='http://localhost:9000',
            aws_access_key_id='admin',
            aws_secret_access_key='password',
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        s3.list_buckets()
        print("✅ OK")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    print("--- Platform Infrastructure Health Check ---\n")
    results = [
        check_postgres(),
        check_redis(),
        check_rabbitmq(),
        check_minio()
    ]
    
    print("\n-------------------------------------------")
    if all(results):
        print("🚀 ALL SYSTEMS GO! Infrastructure is ready.")
    else:
        print("⚠️ SOME SYSTEMS DOWN. Please ensure 'docker compose up -d' is running.")
    print("-------------------------------------------\n")

if __name__ == "__main__":
    main()
