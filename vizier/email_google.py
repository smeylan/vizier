import os
import smtplib
import ssl

class Gmail(object):
    def __init__(self, email, password):
        self.email = email
        self.password = password
        session = smtplib.SMTP_SSL('smtp.gmail.com', 465)        
        session.ehlo()        
        session.login(self.email, self.password)
        self.session = session

    def send_message(self, subject, body, recipient):
        ''' This must be removed '''
        headers = [
            "From: " + self.email,
            "Subject: " + subject,
            "To: " + recipient,
            "MIME-Version: 1.0",
           "Content-Type: text/html"]
        headers = "\r\n".join(headers)
        self.session.sendmail(
            from_addr= self.email,
            to_addrs = recipient,
            msg=headers + "\r\n\r\n" + body)


#gmail = Gmail(os.environ['VIZIER_GMAIL_ADDRESS'], os.environ['VIZIER_GMAIL_PW'])
#gmail.send_message(subject="test",body="test",recipient="meylan.stephan@gmail.com")