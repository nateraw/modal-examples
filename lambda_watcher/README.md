# Lambda Labs Cloud Watcher

Text yourself whenever the machine you want on [Lambda](https://lambdalabs.com/cloud) is available.

- Uses the [lambdacloud](https://github.com/nateraw/lambdacloud) Python Library to authenticate + interface with the Lambda API.
- [Twilio](https://twilio.com) for SMS messaging.

## Usage

0. You should have a Lambda account and a Twilio account. The Twilio account should be set up for SMS messaging.

1. Set up secrets on Modal. I made a new secret called "twilio" and added the following env variables:
  - `TWILIO_SID`: Twilio account identifier
  - `TWILIO_AUTH`: Your Twilio auth token
  - `LAMBDA_SECRET`: Your Lambda Labs Cloud API Key

2. Replace variables in run.py

Cron jobs can't accept function params, so we hard code some variables in `run.py`. 

Replace/update the following variables:

- `FROM_PHONE` with your Twilio phone number and
- `TO_PHONE` with your phone number. 
- Update `DESIRED_INSTANCE_TYPES` with the instance types you want to be notified about. By default, we watch for 8xA100 and 8xV100 machines.
- Update the cron schedule in `run.py` to change how often you want to check for availability. By default, it checks every 5 minutes, M-F, 3am-10am UTC.

3. Finally, run the script:

```
python run.py
```
