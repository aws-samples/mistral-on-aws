import boto3
import json
from urllib.parse import urlparse
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth


boto3_session = boto3.session.Session()
region_name = boto3_session.region_name
account_number = boto3.client('sts').get_caller_identity().get('Account')
identity = boto3.client('sts').get_caller_identity()['Arn']
iam_client = boto3.client('iam')

def create_oss_policy_attach_execution_role(collection_id, notebook_execution_role):
    
    # define oss policy document
    oss_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "aoss:APIAccessAll"
                ],
                "Resource": [
                    f"arn:aws:aoss:{region_name}:{account_number}:collection/{collection_id}"
                ]
            }
        ]
    }

    oss_policy_name = collection_id + '-blog-oss'
    
    oss_policy = iam_client.create_policy(
        PolicyName=oss_policy_name,
        PolicyDocument=json.dumps(oss_policy_document),
        Description='Policy for accessing opensearch serverless',
    )
    oss_policy_arn = oss_policy["Policy"]["Arn"]
    # print("Opensearch serverless policy arn: ", oss_policy_arn)

    iam_client.attach_role_policy(
        RoleName=notebook_execution_role.split('/')[-1],
        PolicyArn=oss_policy_arn
    )
    return None


def create_policies_in_oss(collection_name, aoss_client, notebook_execution_role):

    encryption_policy_name = collection_name + '-blog-encryption'
    encryption_policy = aoss_client.create_security_policy(
        name=encryption_policy_name,
        policy=json.dumps(
            {
                'Rules': [{'Resource': ['collection/' + collection_name],
                           'ResourceType': 'collection'}],
                'AWSOwnedKey': True
            }),
        type='encryption'
    )

    network_policy_name = collection_name + '-blog-network'
    network_policy = aoss_client.create_security_policy(
        name=network_policy_name,
        policy=json.dumps(
            [
                {'Rules': [{'Resource': ['collection/' + collection_name],
                            'ResourceType': 'collection'}],
                 'AllowFromPublic': True}
            ]),
        type='network'
    )
    
    access_policy_name = collection_name + '-blog-access'
    access_policy = aoss_client.create_access_policy(
        name=access_policy_name,
        policy=json.dumps(
            [
                {
                    'Rules': [
                        {
                            'Resource': ['collection/' + collection_name],
                            'Permission': [
                                'aoss:CreateCollectionItems',
                                'aoss:DeleteCollectionItems',
                                'aoss:UpdateCollectionItems',
                                'aoss:DescribeCollectionItems'],
                            'ResourceType': 'collection'
                        },
                        {
                            'Resource': ['index/' + collection_name + '/*'],
                            'Permission': [
                                'aoss:CreateIndex',
                                'aoss:DeleteIndex',
                                'aoss:UpdateIndex',
                                'aoss:DescribeIndex',
                                'aoss:ReadDocument',
                                'aoss:WriteDocument'],
                            'ResourceType': 'index'
                        }],
                    'Principal': [identity, notebook_execution_role],
                    'Description': 'Easy data policy'}
            ]),
        type='data'
    )
    return encryption_policy, network_policy, access_policy


def create_collection(collection_name, notebook_execution_role):
    aoss_client = boto3.client('opensearchserverless')
    access_policy = create_policies_in_oss(collection_name, aoss_client, notebook_execution_role)
    collection = aoss_client.create_collection(name=collection_name,type='VECTORSEARCH', standbyReplicas='DISABLED')
    
    collection_id = collection['createCollectionDetail']['id']
    create_oss_policy_attach_execution_role(collection_id, notebook_execution_role)

    endpoint ='https://' + collection_id + '.' + region_name + '.aoss.amazonaws.com:443'
    return endpoint


def create_index(index_name, endpoint, emb_dim=1024):
    service = 'aoss'
    credentials = boto3.Session().get_credentials()
    awsauth = AWSV4SignerAuth(credentials, "us-west-2", service)

    parsed_url = urlparse(endpoint)
    host = parsed_url.netloc.split(':')[0]
    
    # Build the OpenSearch client
    oss_client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=300
    )

    # Prepare index configurations
    index_body = {
           "settings": {
              "index.knn": "true",
               "number_of_shards": 1,
               "knn.algo_param.ef_search": 512,
               "number_of_replicas": 0,
           },
           "mappings": {
              "properties": {
                 "vector": {
                    "type": "knn_vector",
                    "dimension": emb_dim,
                     "method": {
                         "name": "hnsw",
                         "engine": "faiss",
                         "space_type": "l2"
                     },
                 },
                 "chunk": {"type": "text"},
              }
           }
        }
    try:
        response = oss_client.indices.create(index_name, body=index_body)
        print(f"response received for the create index -> {response}")
    except Exception as e:
        print(f"error in creating index={index_name}, exception={e}")