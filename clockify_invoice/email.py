from __future__ import annotations

import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clockify_invoice.config import Config


class Email:
    def __init__(
        self, to: str, sender: str, subject: str, body: str, config: Config
    ) -> None:
        em = MIMEMultipart()
        em["To"] = to
        em["From"] = sender
        em["Subject"] = subject
        em.attach(MIMEText(body))

        self.to = to
        self.sender = sender
        self.config = config
        self.em = em
        self.ssl_context = ssl.create_default_context()

    def attach_pdf(self, filename: str, pdf_bytes: bytes) -> None:
        attachment = MIMEBase("application", "pdf")
        attachment.set_payload(pdf_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition", f'attachment; filename="{filename}"'
        )
        self.em.attach(attachment)

    def send(self) -> None:
        if self.config.MAIL_USE_SSL:
            with smtplib.SMTP_SSL(
                self.config.MAIL_SERVER, self.config.MAIL_PORT, context=self.ssl_context
            ) as smtp:
                smtp.login(self.config.MAIL_USERNAME, self.config.MAIL_PASSWORD)
                smtp.sendmail(self.sender, self.to, self.em.as_string())
        else:
            with smtplib.SMTP(self.config.MAIL_SERVER, self.config.MAIL_PORT) as smtp:
                smtp.login(self.config.MAIL_USERNAME, self.config.MAIL_PASSWORD)
                smtp.sendmail(self.sender, self.to, self.em.as_string())
