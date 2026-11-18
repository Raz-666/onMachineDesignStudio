Eine solche Integration lässt sich komplett ohne eigene teure GPU umsetzen, indem dein Raspberry Pi (auf dem Klipper läuft) lediglich als Steuerzentrale dient und die schwere 3D-Berechnung per API an Hugging Face auslagert. [1] (https://github.com/ahkamboh/image-to-3d-shape-generation), [2] (https://huggingface.co/datasets/John6666/knowledge_base_md_for_rag_1/blob/101e66319268f9bcf18ff96ea6b6ddee189faa61/hf_gradio_api_20251114.md)
Für eine dauerhafte, automatisierte Verbindung zu Klipper ist Hugging Face deutlich besser geeignet als Google Colab, da Colab-Sitzungen nach einiger Zeit Inaktivität automatisch getrennt werden und manuelle Klicks im Browser erfordern. [1] (https://blog.winerva.com/google-colab-huggingface-model-tutorial/)

1. Google Colab vs. Hugging Face Spaces im Überblick

• Google Colab (Kostenlose Cloud-Notebooks): Du bekommst für ein paar Stunden gratis Zugriff auf eine NVIDIA T4 GPU (16 GB VRAM). Das eignet sich perfekt, um Python-Code für 3D-Modelle auszuprobieren, schläft aber ein, wenn du nichts tust. [1] (https://blog.winerva.com/google-colab-huggingface-model-tutorial/)
• Hugging Face Spaces (Dauerhafte Web-Apps & APIs): Hier laufen fertige 3D-Generatoren (wie Trellis, TripoSR oder Hunyuan3D) auf Web-Oberflächen (Gradio). Das Beste: Jeder öffentliche Hugging Face Space besitzt automatisch eine kostenlose Programmierschnittstelle (API), die dein Raspberry Pi direkt ansprechen kann. [1] (https://huggingface.co/datasets/John6666/knowledge_base_md_for_rag_1/blob/101e66319268f9bcf18ff96ea6b6ddee189faa61/hf_gradio_api_20251114.md), [2] (https://gradio.app/guides/using-hugging-face-integrations/), [3] (https://github.com/ahkamboh/image-to-3d-shape-generation)

2. So bindest du die KI in Klipper (Mainsail / Fluidd) ein

Da Klipper selbst nur den Drucker steuert und kein Slicer ist, kann die KI dir kein direkt druckfertiges .gcode-File ausspucken, sondern eine .stl- oder .obj-Datei. Den Ablauf kannst du aber nahtlos in deine Klipper-Oberfläche integrieren: [1] (https://gradio.app/guides/how-to-use-3D-model-component/), [2] (https://docs.mainsail.xyz/setup/)

Schritt A: Die eigene Web-App auf dem Raspberry Pi bauen

Auf deinem Klipper-Host (Raspberry Pi) läuft bereits Python. Dort installierst du das Paket gradio_client (für die 3D-KI) sowie eine kleine Weboberfläche (z. B. mit Python Flask oder Gradio selbst). [1] (https://huggingface.co/learn/ml-for-3d-course/unit5/run-via-api), [2] (https://github.com/ahkamboh/image-to-3d-shape-generation)
• Texteingabe: Du tippst ein, was du haben möchtest (z. B. "ein kleiner Drache als Stifthalter"). Da die meisten 3D-KIs ein Bild als Vorlage brauchen, schaltet dein Skript im Hintergrund zuerst eine kostenlose Text-zu-Bild-KI (z. B. Flux oder Stable Diffusion auf Hugging Face) vor und schickt das erzeugte Bild direkt weiter an die 3D-KI (z. B. tencent/Hunyuan3D-2). [1] (https://github.com/ahkamboh/image-to-3d-shape-generation)
• Spracheingabe: Über die kostenlose Web-Speech-API deines Browsers (oder das Whisper-Modell von Hugging Face) kannst du direkt ins Mikrofon deines Handys oder PCs sprechen – der Browser wandelt die Sprache automatisch in Text für deinen Prompt um.

Schritt B: Direkt in Mainsail oder Fluidd einbetten

Du musst nicht zwischen verschiedenen Browser-Tabs wechseln, sondern kannst deine neue KI-Oberfläche direkt in Klipper einbauen:
1. Als eigener Menüpunkt (iFrame): Sowohl in Mainsail als auch in Fluidd kannst du in den Einstellungen eigene Navigations-Links oder Web-Panels anlegen. Dort verlinkst du einfach auf die lokale Adresse deines Python-Skripts (z. B. http://mainsailos.local:5000).
2. Automatischer Download / Ordner-Sync: Dein Skript speichert das fertige 3D-Modell (.stl) direkt in einem Netzwerkordner (Samba/SMB) auf dem Pi. Du öffnest die Datei auf deinem PC direkt in OrcaSlicer oder PrusaSlicer, slicest sie und sendest den Druck wie gewohnt an Klipper.
(Fortgeschrittener Trick: Man kann sogar OrcaSlicer oder PrusaSlicer per Kommandozeile auf einem Server/PC automatisch im Hintergrund slicen und die fertige G-Code-Datei direkt über die Moonraker-API in deine Klipper-Druckwarteschlange hochladen lassen!)

Wichtige Einschränkungen bei der kostenlosen Variante

• Warteschlangen (ZeroGPU-Limits): Wenn du die kostenlosen öffentlichen Spaces auf Hugging Face per API nutzt, teilst du dir die Rechenleistung mit anderen Nutzern. Zu Stoßzeiten kann die Generierung mal 30 bis 90 Sekunden dauern oder kurz blockiert sein.
• Nachbearbeitung nötig: KI-generierte 3D-Modelle haben oft keine flache Unterseite. Du wirst sie vor dem Drucken im Slicer fast immer kurz auf das Druckbett absenken oder mit Stützstrukturen (Supports) versehen müssen. [1] (https://huggingface.co/datasets/John6666/knowledge_base_md_for_rag_1/blob/101e66319268f9bcf18ff96ea6b6ddee189faa61/hf_gradio_api_20251114.md)



Um das direkt in Mainsail umzusetzen, brauchst du ein kleines Python-Skript auf deinem Klipper-Host (z. B. Raspberry Pi), das eine lokale Weboberfläche bereitstellt, und einen neuen Menüpunkt über die navi.json-Datei von Mainsail.
Damit hast du links in der Mainsail-Seitenleiste einen eigenen Button (z. B. „3D-KI Generator“), über den du per Text- oder Spracheingabe ein Modell anforderst, das automatisch als .stl- oder .glb-Datei in deinem Drucker-Ordner landet.

Schritt 1: Das KI-Skript auf dem Raspberry Pi einrichten

Verbinde dich per SSH mit deinem Raspberry Pi und lege einen Ordner für deine KI-Bridge an:
bash
mkdir ~/ai_3d_gen && cd ~/ai_3d_gen
python3 -m venv venv
source venv/bin/activate
pip install flask gradio_client
Verwende Code mit Vorsicht.
Erstelle nun die Datei app.py (nano app.py). Dieses Skript stellt eine schlanke Weboberfläche (inkl. Mikrofon-Button für Spracheingabe über deinen Browser) bereit, schickt deinen Text an einen kostenlosen Hugging-Face-Space und speichert die fertige 3D-Datei direkt im gcodes-Ordner von Klipper (damit du sie sofort in Mainsail unter „Dateien“ siehst und herunterladen kannst):
python
import os
import shutil
from flask import Flask, render_template_string, request, jsonify
from gradio_client import Client

app = Flask(__name__)

# Speicherort: Klipper gcodes-Ordner (erscheint direkt in Mainsail unter Dateien)
OUTPUT_DIR = os.path.expanduser("~/printer_data/gcodes/KI_Modelle")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Beispiel-Space auf Hugging Face (kann gegen jeden aktuellen Text-to-3D Space getauscht werden)
HF_SPACE = "tencent/Hunyuan3D-2" 

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mainsail 3D-KI Generator</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: #fff; padding: 20px; max-width: 600px; margin: auto; }
        input, button { padding: 12px; font-size: 16px; border-radius: 6px; border: none; margin-top: 10px; width: 100%; box-sizing: border-box; }
        input { background: #2c2c2c; color: #fff; border: 1px solid #444; }
        button { background: #2196F3; color: white; cursor: pointer; font-weight: bold; }
        button.mic { background: #e91e63; }
        #status { margin-top: 20px; padding: 15px; background: #1e1e1e; border-radius: 6px; }
    </style>
</head>
<body>
    <h2>🧊 3D-Modell per KI generieren</h2>
    <input type="text" id="prompt" placeholder="Beschreibe dein 3D-Modell (z.B. ein kleiner Drache)...">
    <button class="mic" onclick="startDictation()">🎤 Spracheingabe starten</button>
    <button onclick="generate3D()">🚀 3D-Modell generieren</button>
    <div id="status">Bereit.</div>

    <script>
        function startDictation() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) { alert("Spracheingabe wird von diesem Browser nicht unterstützt."); return; }
            const recognition = new SpeechRecognition();
            recognition.lang = 'de-DE';
            document.getElementById('status').innerText = "🎙️ Bitte jetzt sprechen...";
            recognition.onresult = (event) => {
                document.getElementById('prompt').value = event.results[0][0].transcript;
                document.getElementById('status').innerText = "Text erkannt. Klicke auf Generieren!";
            };
            recognition.start();
        }

        async function generate3D() {
            const prompt = document.getElementById('prompt').value;
            if (!prompt) return;
            document.getElementById('status').innerText = "⏳ KI berechnet 3D-Modell auf Hugging Face (dauert ca. 30-90 Sek.)...";
            const res = await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({prompt: prompt})
            });
            const data = await res.json();
            document.getElementById('status').innerText = data.message;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/generate", methods=["POST"])
def generate():
    prompt = request.json.get("prompt", "")
    try:
        # Verbindet sich mit der Hugging Face API (nutze den "Use via API"-Link unten auf jedem HF Space für exakte Parameter)
        client = Client(HF_SPACE)
        result = client.predict(prompt=prompt, api_name="/shape_generation")
        
        # Datei aus dem Temp-Ordner in Mainsail verschieben
        file_path = result[0] if isinstance(result, (list, tuple)) else result
        safe_name = "".join(c if c.isalnum() else "_" for c in prompt)[:25]
        ext = os.path.splitext(file_path)[1] or ".glb"
        dest_path = os.path.join(OUTPUT_DIR, f"{safe_name}{ext}")
        shutil.copy(file_path, dest_path)
        
        return jsonify({"message": f"✅ Fertig! Gespeichert unter Dateien -> KI_Modelle/{safe_name}{ext}"})
    except Exception as e:
        return jsonify({"message": f"❌ Fehler (evtl. Server ausgelastet): {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
Verwende Code mit Vorsicht.
(Hinweis: Da sich die exakten API-Endpunkte auf Hugging Face je nach Modell-Update ändern können, klicke auf der jeweiligen Hugging-Face-Space-Seite ganz unten auf „Use via API“ – dort zeigt dir Gradio Python Client genau die zwei Zeilen Code für client.predict(...) an, die du hier einfügen musst.)

Schritt 2: Das Skript dauerhaft im Hintergrund starten

Damit dein Generator bei jedem Start des Druckers automatisch mitläuft, richtest du einen Systemd-Dienst ein:
bash
sudo nano /etc/systemd/system/ai3d.service
Verwende Code mit Vorsicht.
Füge Folgendes ein (passe pi an deinen Benutzernamen an, falls abweichend):
ini
[Unit]
Description=Mainsail 3D AI Generator
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/ai_3d_gen
ExecStart=/home/pi/ai_3d_gen/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
Verwende Code mit Vorsicht.
Aktiviere den Dienst:
bash
sudo systemctl enable --now ai3d.service
Verwende Code mit Vorsicht.

Schritt 3: Den Button in die Mainsail-Seitenleiste einbauen   #GEHT DAS AUCH MIT UNSERER WEBUI????

Mainsail unterstützt eigene Navigationspunkte über eine einfache JSON-Datei in deinem Konfigurationsordner, wie in der Mainsail Custom Navigation Dokumentation beschrieben:
1. Öffne Mainsail im Browser und gehe links auf Maschine (Konfigurationsdateien).
2. Klicke auf das Zahnrad-Symbol oben rechts in der Dateiliste und aktiviere „Versteckte Dateien anzeigen“.
3. Öffne (oder erstelle) den Ordner .theme und lege darin eine neue Datei namens navi.json an.
4. Trage dort folgenden Code ein (ersetze mainsailos.local ggf. durch die IP-Adresse deines Druckers):
json
[
  {
    "title": "3D-KI Generator",
    "href": "http://mainsailos.local:5050",
    "target": "_blank",
    "position": 55,
    "icon": "M21,16.5C21,16.88 20.79,17.21 20.47,17.38L12.57,21.82C12.41,21.94 12.21,22 12,22C11.79,22 11.59,21.94 11.43,21.82L3.53,17.38C3.21,17.21 3,16.88 3,16.5V7.5C3,7.12 3.21,6.79 3.53,6.62L11.43,2.18C11.59,2.06 11.79,2 12,2C12.21,2 12.41,2.06 12.57,2.18L20.47,6.62C20.79,6.79 21,7.12 21,7.5V16.5M12,4.15L6.04,7.5L12,10.85L17.96,7.5L12,4.15M5,15.91L11,19.29V12.58L5,9.21V15.91M19,15.91V9.21L13,12.58V19.29L19,15.91Z"
  }
]
Verwende Code mit Vorsicht.
Nach einem Neuladen der Mainsail-Seite erscheint links unterhalb von „G-Code Dateien“ dein neuer Menüpunkt „3D-KI Generator“ mit einem 3D-Würfel-Icon.

Praxistipp für die Spracheingabe

Die Web-Speech-API im Browser funktioniert aus Sicherheitsgründen oft nur über localhost oder verschlüsselte Verbindungen (https://). Wenn du den Generator vom Smartphone aus per Sprache steuern willst, kannst du dir einen kostenlosen Account auf Hugging Face anlegen und in das Python-Skript noch eine zweite Zeile einbauen, die aufgenommene Audiodateien über ein kostenloses Whisper-Space in Text übersetzt – dann klappt die Spracheingabe auf jedem Gerät im Heimnetz ohne HTTPS-Zertifikat.
Welcher 3D-Slicer (z. B. OrcaSlicer, PrusaSlicer oder Cura) kommt bei dir zum Einsatz und auf welchem Host-System (Raspberry Pi 3/4/5 oder Mini-PC) läuft dein Mainsail? Dann zeige ich dir bei Bedarf noch, wie du das generierte Modell per Knopfdruck direkt in den Slicer lädst.
