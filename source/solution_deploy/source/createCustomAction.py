#!/usr/bin/python
###############################################################################
#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.    #
#                                                                             #
#  Licensed under the Apache License Version 2.0 (the "License"). You may not #
#  use this file except in compliance with the License. A copy of the License #
#  is located at                                                              #
#                                                                             #
#      http://www.apache.org/licenses/                                        #
#                                                                             #
#  or in the "license" file accompanying this file. This file is distributed  #
#  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express #
#  or implied. See the License for the specific language governing permis-    #
#  sions and limitations under the License.                                   #
###############################################################################

import os
import json
import boto3
import botocore
import hashlib
from logger import Logger
import requests
from urllib.request import Request, urlopen
from datetime import datetime

# initialise logger
LOG_LEVEL = os.getenv('log_level', 'info')
logger_obj = Logger(loglevel=LOG_LEVEL)
SEND_METRICS = os.environ.get('sendAnonymousMetrics', 'No')

def send(event, context, response_status, response_data, physical_resource_id, logger_obj, reason=None):

    response_url = event['ResponseURL']
    logger_obj.debug("CFN response URL: " + response_url)

    response_body = {}
    response_body['Status'] = response_status
    response_body['PhysicalResourceId'] = physical_resource_id or context.log_stream_name
    
    msg = 'See details in CloudWatch Log Stream: ' + context.log_stream_name
    
    logger_obj.debug('PhysicalResourceId: ' + physical_resource_id)
    if not reason:
        response_body['Reason'] = msg
    else:
        response_body['Reason'] = str(reason)[0:255] + '... ' + msg
        
    response_body['StackId'] = event['StackId']
    response_body['RequestId'] = event['RequestId']
    response_body['LogicalResourceId'] = event['LogicalResourceId']
    
    if response_data and response_data != {} and response_data != [] and isinstance(response_data, dict):
        response_body['Data'] = response_data

    logger_obj.debug("<<<<<<< Response body >>>>>>>>>>")
    logger_obj.debug(response_body)
    json_response_body = json.dumps(response_body)

    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }

    try:
        if response_url == 'http://pre-signed-S3-url-for-response':
            logger_obj.info("CloudFormation returned status code: THIS IS A TEST OUTSIDE OF CLOUDFORMATION")
        else:
            response = requests.put(response_url,
                                    data=json_response_body,
                                    headers=headers)
            logger_obj.info("CloudFormation returned status code: " + response.reason)
    except Exception as e:
        logger_obj.error("send(..) failed executing requests.put(..): " + str(e))
        raise

def send_metrics(data):
    try:
        if SEND_METRICS.lower() == 'yes':
            id = data['Id'][23:]
            id_as_bytes = str.encode(id)
            hash_lib = hashlib.sha256()
            hash_lib.update(id_as_bytes)
            id = hash_lib.hexdigest()
            data['Id'] = id
            usage_data = {
                'Solution': 'SO0111',
                'TimeStamp': str(datetime.utcnow().isoformat()),
                'UUID': id,
                'Data': data
            }
            url = 'https://metrics.awssolutionsbuilder.com/generic'
            req = Request( url, 
                        method = 'POST',
                        data=bytes(json.dumps(usage_data),
                        encoding='utf-8'),
                        headers = {'Content-Type': 'application/json'}
                        )
            rsp = urlopen(req)
            rspcode = rsp.getcode()
            logger_obj.debug(rspcode)
        return 
    except Exception as excep:
        print(excep)
        return 

def lambda_handler(event, context):

    response_data = {}
    physical_resource_id = ''

    try:
        properties = event['ResourceProperties']
        logger_obj.debug(json.dumps(properties))
        region = os.environ['AWS_REGION']
        partition = os.getenv('AWS_PARTITION', default='aws') # Set by deployment template
        client = boto3.client('securityhub', region_name=region)
        
        physical_resource_id = 'CustomAction' + properties.get('Id', 'ERROR')
        
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            try:
                logger_obj.info(event['RequestType'].upper() + ": " + physical_resource_id)
                response = client.create_action_target(
                    Name=properties['Name'],
                    Description=properties['Description'],
                    Id=properties['Id']
                )
                response_data['Arn'] = response['ActionTargetArn']
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ResourceConflictException':
                    logger_obj.info('ResourceConflictException: already exists. Continuing')
                else:
                    logger_obj.error(error)
                    raise
            except Exception as e:
                metrics_data = {
                    'status': 'Failed',
                    'Id': event['StackId'],
                    'err_msg': event['RequestType']
                    }
                send_metrics(metrics_data)
                logger_obj.error(e)
                raise
        elif event['RequestType'] == 'Delete':
            try:
                logger_obj.info('DELETE: ' + physical_resource_id)
                account_id = context.invoked_function_arn.split(":")[4]
                client.delete_action_target(
                    ActionTargetArn=f"arn:{partition}:securityhub:{region}:{account_id}:action/custom/{properties['Id']}"
                )
            except botocore.exceptions.ClientError as error:
                if error.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger_obj.info('ResourceNotFoundException - nothing to delete.')
                else:
                    logger_obj.error(error)
                    raise
            except Exception as e:
                metrics_data = {
                    'status': 'Failed',
                    'Id': event['StackId'],
                    'err_msg': event['RequestType']
                    }
                send_metrics(metrics_data)
                logger_obj.error(e)
                raise
        else:
            err_msg = 'Invalid RequestType: ' + event['RequestType']
            logger_obj.error(err_msg)
            send(
                event, context,
                "FAILED",
                response_data,
                physical_resource_id,
                logger_obj,
                reason=err_msg,
            )

        send(
            event,
            context,
            "SUCCESS",
            response_data,
            physical_resource_id,
            logger_obj
        )
        metrics_data = {
            'status': 'Success',
            'Id': event['StackId']
        }
        send_metrics(metrics_data)
        return

    except Exception as err:
        logger_obj.error('An exception occurred: ')
        err_msg = err.__class__.__name__ + ': ' + str(err)
        logger_obj.error(err_msg)
        metrics_data = {
            'status': 'Failed',
            'Id': event['StackId'],
            'err_msg': 'stack installation failed.'
        }
        send_metrics(metrics_data)
        send(
            event,
            context,
            "FAILED",
            response_data,
            event.get('physical_resource_id', 'ERROR'),
            logger_obj=logger_obj,
            reason=err_msg
        )
