#!/usr/bin/env python3
"""
test_01.py
Prueba de conectividad a AWS Bedrock utilizando el mecanismo de inyección
de variables de entorno con SOPS y Age.
"""

import json
import os
import sys
import boto3

def main():
    print("--- Diagnóstico de Conexión a AWS Bedrock (vía SOPS/Age) ---")

    # 1. Validar presencia de credenciales inyectadas por el entorno
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    if not aws_access_key or not aws_secret_key:
        print("❌ Estado: ESTO NO ANDA")
        print("   Razón: No se encontraron credenciales de AWS inyectadas en el entorno.")
        print("   Solución: Ejecuta el script envolviéndolo con 'sops exec-env':")
        print("   SOPS_AGE_KEY_FILE=\"$HOME/.config/sops/age/keys.txt\" sops exec-env secrets.enc.env \"python3 test_01.py\"")
        sys.exit(1)

    print("✔ Variables de entorno inyectadas correctamente por SOPS.")
    print(f"✔ Región detectada: {region}")

    # 2. Inicializar cliente Bedrock Runtime
    try:
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=region
        )
        print("✔ Cliente boto3 inicializado correctamente.")
    except Exception as e:
        print("❌ Estado: ESTO NO ANDA")
        print(f"   Razón al crear el cliente de Bedrock: {e}")
        sys.exit(1)

    # 3. Invocar al modelo Amazon Nova Micro
    model_id = 'amazon.nova-micro-v1:0'
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"text": "Responde estrictamente con la frase 'Conexión exitosa' y nada más."}]
            }
        ],
        "inferenceConfig": {
            "max_new_tokens": 500,
            "temperature": 0.1
        }
    }

    try:
        print(f"✔ Enviando petición a {model_id}...")
        response = bedrock.invoke_model(
            modelId=model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(payload)
        )

        response_body = json.loads(response['body'].read())
        resultado = response_body['output']['message']['content'][0]['text'].strip()

        print("\n" + "=" * 50)
        print("✅ Sí, anda todo ok")
        print("=" * 50)
        print(f"Respuesta del modelo: {resultado}\n")

    except Exception as e:
        print("\n" + "=" * 50)
        print("❌ ESTO NO ANDA")
        print("=" * 50)
        print(f"Detalle del error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
