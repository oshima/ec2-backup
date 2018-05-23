import boto3
import os
import json
from datetime import datetime, timezone
from calendar import monthrange
from functools import reduce


def fetch_instances(ec2, filters):
  response = ec2.describe_instances(Filters=filters)
  return reduce(
    lambda instances, reservation: instances + reservation['Instances'],
    response['Reservations'],
    []
  )


def invoke_function(lmd, function_name, payload):
  lmd.invoke(
    FunctionName=function_name,
    Payload=json.dumps(payload),
    InvocationType='Event'
  )


def get_datetime(string):
  dt = datetime.strptime(string, '%Y-%m-%dT%H:%M:%SZ')
  dt = dt.replace(tzinfo=timezone.utc)
  return dt.astimezone()


def make_instance_filters(_type, dt):
  if _type == 'DailyBackup':
    return make_instance_filters_of_daily_backup(dt)
  elif _type == 'WeeklyBackup':
    return make_instance_filters_of_weekly_backup(dt)
  elif _type == 'MonthlyBackup':
    return make_instance_filters_of_monthly_backup(dt)


def make_instance_filters_of_daily_backup(dt):
  return [
    {'Name': 'tag:DailyBackupHour', 'Values': [str(dt.hour)]},
    {'Name': 'tag:DailyBackupMinute', 'Values': [str(dt.minute)]}
  ]


def make_instance_filters_of_weekly_backup(dt):
  day_of_week = dt.strftime('%a')
  return [
    {'Name': 'tag:WeeklyBackupDay', 'Values': [day_of_week]},
    {'Name': 'tag:WeeklyBackupHour', 'Values': [str(dt.hour)]},
    {'Name': 'tag:WeeklyBackupMinute', 'Values': [str(dt.minute)]}
  ]


def make_instance_filters_of_monthly_backup(dt):
  last_day = monthrange(dt.year, dt.month)[1]
  day_of_week = dt.strftime('%a')
  week = (dt.day - 1) // 7 + 1
  return [
    {
      'Name': 'tag:MonthlyBackupDay',
      'Values': list(filter(lambda v: v, [
        str(dt.day),
        'Last' if dt.day == last_day else None,
        f'{day_of_week}#{week}',
        f'{day_of_week}#Last' if dt.day > last_day - 7 else None
      ]))
    },
    {'Name': 'tag:MonthlyBackupHour', 'Values': [str(dt.hour)]},
    {'Name': 'tag:MonthlyBackupMinute', 'Values': [str(dt.minute)]}
  ]


def get_tag_value(instance, tag_key):
  tag = next(
    filter(lambda tag: tag['Key'] == tag_key, instance['Tags']),
    None
  )
  return tag['Value'] if tag else None


def lambda_handler(event, context):
  leaf_function = os.environ['LEAF_FUNCTION']
  dt = get_datetime(event['time'])

  ec2 = boto3.client('ec2')
  lmd = boto3.client('lambda')

  for _type in ['DailyBackup', 'WeeklyBackup', 'MonthlyBackup']:
    print(f'Start invocation of leaf functions ({_type})')
    filters = make_instance_filters(_type, dt)
    instances = fetch_instances(ec2, filters)
    for instance in instances:
      instance_name = get_tag_value(instance, 'Name')
      generation = get_tag_value(instance, f'{_type}Generation')
      for block_device_mapping in instance['BlockDeviceMappings']:
        device_name = block_device_mapping['DeviceName']
        volume_id = block_device_mapping['Ebs']['VolumeId']
        invoke_function(lmd, leaf_function, {
          'Type': _type,
          'VolumeId': volume_id,
          'Name': f'{instance_name}:{device_name}',
          'Generation': generation
        })
    print(f'End invocation of leaf functions ({_type})')
