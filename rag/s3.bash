# Set variables (optional, but makes commands cleaner)
BUCKET_NAME="pokemonhunters"
REGION="us-east-1"
FILE_NAME="pokemonhunters.csv"
KB_NAME="PokemonHuntersKB"
DATA_SOURCE_NAME="PokemonHuntersS3DataSource"
# Replace with your actual Account ID and Role Name if different
BEDROCK_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/AmazonBedrockKnowledgeBaseRole"
EMBEDDING_MODEL_ARN="arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1"

# === Step 1: Create S3 bucket and upload file ===

echo "Creating S3 bucket: ${BUCKET_NAME} in region ${REGION}..."
aws s3api create-bucket \
    --bucket ${BUCKET_NAME} \
    --region ${REGION}
    # Note: For us-east-1, --create-bucket-configuration is NOT needed.
    # For other regions add: --create-bucket-configuration LocationConstraint=${REGION}

echo "Waiting for bucket to become available..."
aws s3api wait bucket-exists --bucket ${BUCKET_NAME}

echo "Uploading ${FILE_NAME} to s3://${BUCKET_NAME}/ ..."
aws s3 cp ${FILE_NAME} s3://${BUCKET_NAME}/ \
    --region ${REGION}

echo "S3 setup complete."

# === Step 2: Create Bedrock Knowledge Base and add Data Source ===

echo "Creating Bedrock Knowledge Base: ${KB_NAME}..."
# This command creates the KB. Capture the output KB ID.
KB_RESPONSE=$(aws bedrock-agent create-knowledge-base \
    --name ${KB_NAME} \
    --description "Knowledge Base for Pokemon Hunters data" \
    --role-arn ${BEDROCK_ROLE_ARN} \
    --knowledge-base-configuration '{
        "type": "VECTOR",
        "vectorKnowledgeBaseConfiguration": {
            "embeddingModelArn": "'"${EMBEDDING_MODEL_ARN}"'"
        }
    }' \
    --storage-configuration '{
        "type": "OPENSEARCH_SERVERLESS",
        "opensearchServerlessConfiguration": {
            "collectionArn": "PLACEHOLDER_OPENSEARCH_COLLECTION_ARN",
            "vectorIndexName": "PLACEHOLDER_INDEX_NAME",
            "fieldMapping": {
                "vectorField": "PLACEHOLDER_VECTOR_FIELD",
                "textField": "PLACEHOLDER_TEXT_FIELD",
                "metadataField": "PLACEHOLDER_METADATA_FIELD"
            }
        }
    }' \
# NOTE: As of recent updates, Bedrock often provisions a managed vector store by default
# if storage-configuration is omitted for S3 data sources, simplifying setup.
# Let's try omitting it, assuming managed vector store:

KB_RESPONSE=$(aws bedrock-agent create-knowledge-base \
    --name "${KB_NAME}" \
    --description "Knowledge Base for Pokemon Hunters data" \
    --role-arn "${BEDROCK_ROLE_ARN}" \
    --knowledge-base-configuration '{
        "type": "VECTOR",
        "vectorKnowledgeBaseConfiguration": {
            "embeddingModelArn": "'"${EMBEDDING_MODEL_ARN}"'"
        }
    }' \
    --region ${REGION})

# Extract the Knowledge Base ID (requires jq tool, or parse manually)
if command -v jq &> /dev/null
then
    KB_ID=$(echo ${KB_RESPONSE} | jq -r '.knowledgeBase.knowledgeBaseId')
else
    echo "jq is not installed. Please extract the 'knowledgeBaseId' from the response above manually."
    # Example manual extraction (less robust):
    # KB_ID=$(echo ${KB_RESPONSE} | grep -o '"knowledgeBaseId": "[^"]*' | cut -d'"' -f4)
    echo "Please manually set the KB_ID variable: export KB_ID='your_kb_id_here'"
    exit 1 # Exit if jq isn't available and manual intervention is needed
fi

echo "Knowledge Base created with ID: ${KB_ID}"
echo "Waiting for Knowledge Base to become ACTIVE..."
# Wait until the KB is Active (might take a minute) - adjust max-attempts as needed
aws bedrock-agent wait knowledge-base-active --knowledge-base-id ${KB_ID} --region ${REGION} --max-attempts 20

echo "Creating Data Source: ${DATA_SOURCE_NAME} for KB ${KB_ID}..."
# This command creates the Data Source link to S3. Capture the output Data Source ID.
DS_RESPONSE=$(aws bedrock-agent create-data-source \
    --knowledge-base-id ${KB_ID} \
    --name ${DATA_SOURCE_NAME} \
    --description "S3 source for ${FILE_NAME}" \
    --data-source-configuration '{
        "type": "S3",
        "s3Configuration": {
            "bucketArn": "arn:aws:s3:::'"${BUCKET_NAME}"'",
            "inclusionPrefixes": ["'"${FILE_NAME}"'"]
        }
    }' \
    --vector-ingestion-configuration '{
        "chunkingConfiguration": {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {
                "maxTokens": 300,
                "overlapPercentage": 20
            }
        }
    }' \
    --region ${REGION})

# Extract the Data Source ID (requires jq)
if command -v jq &> /dev/null
then
    DS_ID=$(echo ${DS_RESPONSE} | jq -r '.dataSource.dataSourceId')
else
    echo "jq is not installed. Please extract the 'dataSourceId' from the response above manually."
     echo "Please manually set the DS_ID variable: export DS_ID='your_ds_id_here'"
    exit 1 # Exit if jq isn't available and manual intervention is needed
fi

echo "Data Source created with ID: ${DS_ID}"
echo "Waiting for Data Source to become AVAILABLE..."
# Wait until the Data Source is Available (might take a minute) - adjust max-attempts as needed
aws bedrock-agent wait data-source-available --knowledge-base-id ${KB_ID} --data-source-id ${DS_ID} --region ${REGION} --max-attempts 20


echo "Starting ingestion job for Data Source ${DS_ID} in KB ${KB_ID}..."
INGESTION_RESPONSE=$(aws bedrock-agent start-ingestion-job \
    --knowledge-base-id ${KB_ID} \
    --data-source-id ${DS_ID} \
    --region ${REGION})

# Extract the Ingestion Job ID (requires jq)
if command -v jq &> /dev/null
then
    INGESTION_JOB_ID=$(echo ${INGESTION_RESPONSE} | jq -r '.ingestionJob.ingestionJobId')
else
    echo "jq is not installed. Please extract the 'ingestionJobId' from the response above manually."
    echo "Please manually set the INGESTION_JOB_ID variable: export INGESTION_JOB_ID='your_job_id_here'"
    exit 1 # Exit if jq isn't available
fi

echo "Ingestion job started with ID: ${INGESTION_JOB_ID}"
echo "You can monitor the job status using:"
echo "aws bedrock-agent get-ingestion-job --knowledge-base-id ${KB_ID} --data-source-id ${DS_ID} --ingestion-job-id ${INGESTION_JOB_ID} --region ${REGION}"

echo "Script finished. Ingestion is running in the background."