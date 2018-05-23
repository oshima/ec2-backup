import boto3
from datetime import datetime


def fetch_snapshots(ec2, _type, volume_id):
  snapshots = ec2.describe_snapshots(
    Filters=[
      {'Name': 'tag:Type', 'Values': [_type]},
      {'Name': 'tag:VolumeId', 'Values': [volume_id]}
    ]
  )['Snapshots']
  return sorted(snapshots, key=lambda s: s['StartTime'])


def create_snapshot(ec2, volume_id):
  return ec2.create_snapshot(VolumeId=volume_id)['SnapshotId']


def tag_snapshot(ec2, snapshot_id, _type, volume_id, name):
  ec2.create_tags(
    Resources=[snapshot_id],
    Tags=[
      {'Key': 'Type', 'Value': _type},
      {'Key': 'VolumeId', 'Value': volume_id},
      {'Key': 'Name', 'Value': name}
    ]
  )


def delete_old_snapshots(ec2, snapshots, generation):
  old_count = max(len(snapshots) - int(generation), 0)
  old_snapshots = snapshots[:old_count]
  for old_snapshot in old_snapshots:
    ec2.delete_snapshot(SnapshotId=old_snapshot['SnapshotId'])


def get_latest_snapshot(snapshots):
  return snapshots[-1] if len(snapshots) > 0 else None


def is_created_just_before(snapshot):
  now = datetime.utcnow()
  start_time = snapshot['StartTime'].replace(tzinfo=None)
  return (now - start_time).total_seconds() < 60 * 30


def lambda_handler(event, context):
  _type = event['Type']
  volume_id = event['VolumeId']
  name = event['Name']
  generation = event['Generation']

  ec2 = boto3.client('ec2')

  print(f'Start local backup ({_type}, {volume_id}, {name})')
  snapshots = fetch_snapshots(ec2, _type, volume_id)
  latest_snapshot = get_latest_snapshot(snapshots)
  if latest_snapshot and is_created_just_before(latest_snapshot):
    snapshot_id = latest_snapshot['SnapshotId']
  else:
    snapshot_id = create_snapshot(ec2, volume_id)
    snapshots += [{'SnapshotId': snapshot_id}]
  tag_snapshot(ec2, snapshot_id, _type, volume_id, name)
  delete_old_snapshots(ec2, snapshots, generation)
  print(f'End local backup ({_type}, {volume_id}, {name})')
