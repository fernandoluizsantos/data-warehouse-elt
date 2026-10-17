#!/bin/sh
# Gera a configuração de credenciais do S3 a partir das variáveis de ambiente
# (assim nenhuma chave fica escrita em arquivo versionado) e sobe o SeaweedFS.
set -e

cat > /tmp/s3.json <<EOF
{
  "identities": [
    {
      "name": "admin",
      "credentials": [
        { "accessKey": "${S3_ACCESS_KEY}", "secretKey": "${S3_SECRET_KEY}" }
      ],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
EOF

# server = master + volume + filer num processo só; -s3 liga a API S3
exec weed server \
  -dir=/data \
  -ip=seaweedfs \
  -ip.bind=0.0.0.0 \
  -volume.max=0 \
  -filer \
  -s3 \
  -s3.port=8333 \
  -s3.config=/tmp/s3.json
