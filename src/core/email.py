from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from src.core.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,  # TLS pour le port 587
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_email(email: EmailStr, nom: str, password_clair: str):
    html = f"""
    <html>
        <body>
            <h3>Bienvenue Cher utilisateur, {nom} !</h3>
            <p>Ton compte a été créé (ou mis à jour) avec succès. Voici tes identifiants de connexion :</p>
            <ul>
                <li><strong>Identifiant :</strong> {email}</li>
                <li><strong>Mot de passe :</strong> {password_clair}</li>
            </ul>
            <p>Il est fortement conseillé de changer votre mot de passe dès votre première connexion.</p>
            <br>
            <p>Cordialement,<br>L'équipe RH PR_RDC </p>
        </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Tes accès au système :",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)