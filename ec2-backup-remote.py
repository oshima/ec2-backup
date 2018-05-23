import boto3
from datetime import datetime


def fetch_instance(ec2, volume_id):
  return ec2.describe_instances(
    Filters=[
      {'Name': 'block-device-mapping.volume-id', 'Values': [volume_id]}
    ]
  )['Reservations'][0]['Instances'][0]


def fetch_snapshot(ec2, snapshot_id):
  return ec2.describe_snapshots(
    SnapshotIds=[snapshot_id]
  )['Snapshots'][0]


def fetch_snapshots(ec2, _type, volume_id):
  snapshots = ec2.describe_snapshots(
    Filters=[
      {'Name': 'tag:Type', 'Values': [_type]},
      {'Name': 'tag:VolumeId', 'Values': [volume_id]}
    ]
  )['Snapshots']
  return sorted(snapshots, key=lambda s: s['StartTime'])


def copy_snapshot(ec2, source_region, snapshot_id):
  return ec2.copy_snapshot(
    SourceRegion=source_region,
    SourceSnapshotId=snapshot_id
  )['SnapshotId']


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


def extract_snapshot_id(arn):
  return arn[(arn.index('/') + 1):]


def get_tag_value(entity, tag_key):
  tag = next(
    filter(lambda tag: tag['Key'] == tag_key, entity['Tags']),
    None
  )
  return tag['Value'] if tag else None


def lambda_handler(event, context):
  snapshot_id = extract_snapshot_id(event['resources'][0])

  ec2 = boto3.client('ec2')
  local_region = ec2.meta.region_name

  snapshot = fetch_snapshot(ec2, snapshot_id)
  _type = get_tag_value(snapshot, 'Type')
  volume_id = get_tag_value(snapshot, 'VolumeId')
  name = get_tag_value(snapshot, 'Name')

  instance = fetch_instance(ec2, volume_id)
  generation = get_tag_value(instance, f'{_type}Generation')
  remote_region = get_tag_value(instance, f'{_type}RemoteRegion')

  if remote_region is None:
    return

  ec2 = boto3.client('ec2', region_name=remote_region)

  print(f'Start remote backup ({_type}, {volume_id}, {name})')
  snapshots = fetch_snapshots(ec2, _type, volume_id)
  latest_snapshot = get_latest_snapshot(snapshots)
  if latest_snapshot and is_created_just_before(latest_snapshot):
    snapshot_id = latest_snapshot['SnapshotId']
  else:
    snapshot_id = copy_snapshot(ec2, local_region, snapshot_id)
    snapshots += [{'SnapshotId': snapshot_id}]
  tag_snapshot(ec2, snapshot_id, _type, volume_id, name)
  delete_old_snapshots(ec2, snapshots, generation)
  print(f'End remote backup ({_type}, {volume_id}, {name})')
