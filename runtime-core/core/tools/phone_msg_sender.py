"""SMS sender adapters.

Each adapter reads its credentials from environment variables and raises
``RuntimeError`` when they're missing rather than silently failing with the
provider's error path. The dispatcher (``send_msg``) forwards the actual
``phone`` / ``verification_code`` / ``content`` arguments through —
earlier versions of this module hardcoded test phone numbers and message
bodies, ignoring the call site (see issue #91).
"""

import logging
import os

logger = logging.getLogger(__name__)


def _require_env(*names: str) -> dict:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"phone_msg_sender requires env vars: {', '.join(missing)}"
        )
    return {name: os.environ[name] for name in names}


def send_msg(phone, verification_code=None, content=None, type='twilio'):
    if type == 'twilio':
        return send_with_twilio(phone, verification_code=verification_code, content=content)
    if type == 'vonage':
        return send_with_vonge(phone, verification_code=verification_code, content=content)
    if type == 'qcloudsms':
        return send_with_qcloudsms(phone, verification_code, content)
    raise ValueError(f"{type} is not supported")


def send_with_qcloudsms(phone, verification_code, content):
    from qcloudsms_py import SmsSingleSender
    from qcloudsms_py.httpclient import HTTPError

    creds = _require_env(
        "QCLOUDSMS_APPID",
        "QCLOUDSMS_APPKEY",
        "QCLOUDSMS_TEMPLATE_ID",
        "QCLOUDSMS_SIGN",
    )
    appid = int(creds["QCLOUDSMS_APPID"])
    template_id = int(creds["QCLOUDSMS_TEMPLATE_ID"])
    sender = SmsSingleSender(appid, creds["QCLOUDSMS_APPKEY"])

    params = []
    if verification_code:
        params = [str(verification_code), "5"]
    elif content:
        params = [str(content)]

    try:
        sender.send_with_param(86, phone, template_id, params, sign=creds["QCLOUDSMS_SIGN"])
        return True
    except HTTPError as exc:
        logger.warning("qcloudsms HTTP error: %s", exc)
        return False
    except Exception as exc:
        logger.warning("qcloudsms send failed: %s", exc)
        return False


def send_with_vonge(phone, verification_code=None, content=None):
    from vonage import Client, Sms

    creds = _require_env("VONAGE_API_KEY", "VONAGE_API_SECRET")
    client = Client(key=creds["VONAGE_API_KEY"], secret=creds["VONAGE_API_SECRET"])
    sms = Sms(client)

    text = content or (
        f"Your verification code is {verification_code}. Expires in 5 minutes."
        if verification_code
        else ""
    )
    sender_name = os.getenv("VONAGE_SENDER", "Vonage APIs")

    response = sms.send_message({"from": sender_name, "to": phone, "text": text})
    status = response["messages"][0]["status"]
    if status == "0":
        return True
    logger.warning("Vonage send failed: %s", response["messages"][0].get("error-text"))
    return False


def send_with_twilio(phone, verification_code=None, content=None):
    from twilio.rest import Client
    from core.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER

    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
        raise RuntimeError(
            "Twilio requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER"
        )

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    if content:
        msg = content
    elif verification_code:
        msg = f"尊敬的用户，您的验证码是：{verification_code}，有效期为5分钟。"
    else:
        raise ValueError("send_with_twilio requires either content or verification_code")

    client.messages.create(body=msg, from_=TWILIO_PHONE_NUMBER, to=phone)
    return True
