"""Create or update the Lambda function behind the run_python tool.

    python deploy/deploy_run_python.py           # create, or update the code if it exists
    python deploy/deploy_run_python.py --check   # run print(6 * 7) through the deployed function

The function's role can only write CloudWatch logs. Needs AWS credentials allowed to create IAM
roles and Lambda functions (see README "run_python tool").
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
FUNCTION = os.environ.get("ESCALATOR_RUN_PYTHON_FUNCTION", "escalator-run-python")
ROLE = f"{FUNCTION}-role"
REGION = os.environ.get("AWS_REGION", "us-east-1")
TRUST = {
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                   "Action": "sts:AssumeRole"}],
}
LOGS_ONLY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


def package() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT / "lambda" / "run_python" / "handler.py", "handler.py")
    return buffer.getvalue()


def ensure_role(iam) -> str:
    try:
        return iam.get_role(RoleName=ROLE)["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        arn = iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(TRUST),
                              Description="run_python sandbox: CloudWatch logs only")["Role"]["Arn"]
        iam.attach_role_policy(RoleName=ROLE, PolicyArn=LOGS_ONLY)
        print(f"created role {ROLE}; waiting for IAM to propagate...")
        time.sleep(12)
        return arn


def deploy() -> None:
    iam, lam = boto3.client("iam"), boto3.client("lambda", region_name=REGION)
    role_arn, code = ensure_role(iam), package()
    try:
        lam.get_function(FunctionName=FUNCTION)
        lam.update_function_code(FunctionName=FUNCTION, ZipFile=code)
        lam.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION)
        print(f"updated {FUNCTION}")
        return
    except lam.exceptions.ResourceNotFoundException:
        for attempt in range(5):  # a brand-new role can take a few more seconds to be assumable
            try:
                lam.create_function(FunctionName=FUNCTION, Runtime="python3.12", Role=role_arn,
                                    Handler="handler.handler", Code={"ZipFile": code},
                                    Timeout=15, MemorySize=256,
                                    Description="Runs short Python programs for the Escalator agent")
                break
            except lam.exceptions.InvalidParameterValueException:
                if attempt == 4:
                    raise
                time.sleep(5)
        lam.get_waiter("function_active_v2").wait(FunctionName=FUNCTION)
        print(f"created {FUNCTION} in {REGION}")


def check() -> int:
    sys.path.insert(0, str(ROOT))
    from escalator.tools import format_result, lambda_invoke

    print(format_result(lambda_invoke({"code": "print(6 * 7)"})))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        sys.exit(check())
    deploy()
    sys.exit(check())
