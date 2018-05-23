Lambda scripts to back up EC2 instances daily/weekly/monthly.

## Preparation

Create following resources at the region you are using.

### [Lambda function] ec2-backup-root

This function filters instances required to back up at the time.  
And then invoke `ec2-backup-local` function for each EBS volume attached to instances.

- **Runtime**

  Python 3.6

- **Environment variables**

  | Key | Value |
  | --- | ----- |
  | TZ | The time zone you want to use for setting the backup time.<br>*e.g. Asia/Tokyo* |
  | LEAF_FUNCTION | The name of Lambda function to create local EBS snapshot.<br>*e.g. ec2-backup-local* |

### [Lambda function] ec2-backup-local

This function creates local EBS snapshot of given EBS volume.  
"local" means the same region where instance exists.

- **Runtime**

  Python 3.6


### [Lambda function] ec2-backup-remote

This function copies given local EBS snapshot to remote region.

- **Runtime**

  Python 3.6

### [CloudWatch rule] ec2-backup-clock

Create the cron rule which invokes `ec2-backup-root` at regular intervals.

- **Cron expression**

  *e.g. `0/1 * * * ? *` (every minutes)*

### [CloudWatch rule] ec2-backup-local-succeeded

Create the rule which detects successful (local) EBS snapshot creations and invokes `ec2-backup-remote`.

- **Event pattern**

```json
{
  "source": [
    "aws.ec2"
  ],
  "detail-type": [
    "EBS Snapshot Notification"
  ],
  "detail": {
    "event": [
      "createSnapshot"
    ],
    "result": [
      "succeeded"
    ]
  }
}
```

## Usage

Attach following tags to each instance you want to back up.

| Key | Value |
| --- | ----- |
| DailyBackupHour | 0..23 |
| DailyBackupMinute | 0..59 |
| DailyBackupGeneration | 1.. |
| DailyBackupRemoteRegion | \<region name\> |
| WeeklyBackupDay | Mon..Sun |
| WeeklyBackupHour | 0..23 |
| WeeklyBackupMinute | 0..59 |
| WeeklyBackupGeneration | 1.. |
| WeeklyBackupRemoteRegion | \<region name\> |
| MonthlyBackupDay | 1..31 or<br>Last or<br>Mon..Sun#1..5 or<br>Mon..Sun#Last |
| MonthlyBackupHour | 0..23 |
| MontlyBackupMinute | 0..59 |
| MonthlyBackupGeneration | 1.. |
| MonthlyBackupRemoteRegion | \<region name\> |

daily/weekly/monthly can be mixed.

### Example

If you want to...

- back up at every 00:00
  - and hold 7 days
- back up at every 06:00 on first Monday
  - and hold a month
  - and copy to remote region (us-west-1)

Then

| Key | Value |
| --- | ----- |
| DailyBackupHour | 0 |
| DailyBackupMinute | 0 |
| DailyBackupGeneration | 7 |
| MonthlyBackupDay | Mon#1 |
| MonthlyBackupHour | 6 |
| MonthlyBackupMinute | 0 |
| MonthlyBackupGeneration | 1 |
| MonthlyBackupRemoteRegion | us-west-1 |
