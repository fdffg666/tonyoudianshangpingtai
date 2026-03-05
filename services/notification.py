# services/notification.py
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.config import (
    WECHAT_WEBHOOK_KEY, MAIL_SERVER, MAIL_PORT, MAIL_USERNAME,
    MAIL_PASSWORD, MAIL_FROM, MAIL_TO
)
from utils.logger import ContextLogger

logger = ContextLogger(__name__)


def send_wechat_notification(order):
    """通过企业微信机器人发送通知"""
    if not WECHAT_WEBHOOK_KEY:
        logger.warning("企业微信 Webhook 未配置，跳过通知")
        return
    webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WECHAT_WEBHOOK_KEY}"
    content = f"💰 新订单已付款\n订单号：{order.order_no}\n金额：{order.total_amount}元\n用户ID：{order.user_id}"
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": ["@all"]  # 可选
        }
    }
    try:
        resp = requests.post(webhook_url, json=data)
        if resp.status_code == 200 and resp.json().get("errcode") == 0:
            logger.info("企业微信通知发送成功")
        else:
            logger.error(f"企业微信通知失败: {resp.text}")
    except Exception as e:
        logger.error(f"企业微信通知异常: {e}")


def send_email_notification(order):
    """发送邮件通知"""
    if not all([MAIL_SERVER, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM, MAIL_TO]):
        logger.warning("邮件配置不完整，跳过通知")
        return
    subject = f"新订单已付款 - {order.order_no}"
    body = f"""
    订单号：{order.order_no}
    金额：{order.total_amount}元
    用户ID：{order.user_id}
    下单时间：{order.created_at}
    """
    msg = MIMEMultipart()
    msg['From'] = MAIL_FROM
    msg['To'] = MAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info("邮件通知发送成功")
    except Exception as e:
        logger.error(f"邮件通知发送失败: {e}")


def notify_order_paid(order):
    """订单付款后的通知（可同时启用多个渠道）"""
    send_wechat_notification(order)
    send_email_notification(order)