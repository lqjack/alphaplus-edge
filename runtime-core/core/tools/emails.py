from core.settings import EMAIL_ADDRESS, EMAIL_PASSWORD

def send_email(email=EMAIL_ADDRESS, verification_code=None, password=EMAIL_PASSWORD, content=None, subject=None):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # 发送邮件
    msg = MIMEMultipart()
    msg['From'] = email
    msg['To'] = email
    msg['Subject'] = '您的验证码'

    body = ''
    if verification_code:
        body = f'尊敬的用户，您的验证码是：{verification_code}，有效期为5分钟。'
    if content:
        body = content
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)  # 使用 Gmail 的 SMTP 服务
    server.starttls()
    server.login(email, password)
    server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
    server.quit()
