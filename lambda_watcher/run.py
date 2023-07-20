import os

import modal


stub = modal.Stub()
my_image = modal.Image.debian_slim().pip_install("lambdacloud", "twilio")

# Replace these with your own values
FROM_PHONE = "+15551234567"
TO_PHONE = "+15555555555"
DESIRED_INSTANCE_TYPES = ["gpu_8x_a100_80gb_sxm4", "gpu_8x_a100", "gpu_8x_v100"]


@stub.function(image=my_image, schedule=modal.Cron("*/5 3-9 * * 1-5"), secret=modal.Secret.from_name("twilio"))
def poll_lambda_for_big_instances():
    from lambdacloud import list_instance_types, login
    from twilio.rest import Client

    # Auth with lambda
    login(token=os.environ["LAMBDA_SECRET"])

    # Auth with twilio
    account_sid = os.environ["TWILIO_SID"]
    auth_token = os.environ["TWILIO_AUTH"]
    client = Client(account_sid, auth_token)

    instances_available = [x.name for x in list_instance_types()]
    nl = "\n"
    print(f"Instances available:{nl}✅ - {f'{nl}✅ - '.join(instances_available)}")

    desired_instances_available = []
    for desired_instance in DESIRED_INSTANCE_TYPES:
        if desired_instance in instances_available:
            desired_instances_available.append(desired_instance)

    if len(desired_instances_available):
        body = f"The following instances are available on Lambda Cloud: {', '.join(desired_instances_available)}."
        message = client.messages.create(from_=FROM_PHONE, to=TO_PHONE, body=body)
        print(f"Message sent - SID: {message.sid}")


if __name__ == "__main__":
    modal.runner.deploy_stub(stub, name="lambda-watcher")
