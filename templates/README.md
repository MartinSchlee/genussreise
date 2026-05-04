🍳 Genussreise - Rezeptverwaltung
Willkommen bei Genussreise, einer Flask-basierten Web-App zum Speichern, Suchen und Favorisieren deiner Lieblingsrezepte.

🚀 Schnelleinstieg für Entwickler
Befolge diese Schritte, um die Entwicklungsumgebung lokal aufzusetzen:

1. Repository vorbereiten
Kopiere die Projektdateien in deinen lokalen Arbeitsordner.

2. Virtuelle Umgebung einrichten
Erstelle eine virtuelle Umgebung, um Abhängigkeitskonflikte zu vermeiden:

Bash
python -m venv venv
Aktivieren:

Windows: venv\Scripts\activate

Mac/Linux: source venv/bin/activate

3. Abhängigkeiten installieren
Installiere alle benötigten Python-Pakete:

Bash
pip install -r requirements.txt
(Falls keine requirements.txt vorhanden ist: pip install flask flask-sqlalchemy flask-login Werkzeug)

4. Ordnerstruktur vervollständigen
Flask benötigt einen Ordner für die Rezeptbilder. Erstelle diesen manuell, falls er nicht existiert:

Pfad: static/uploads/

Wichtig: Stelle sicher, dass eine Datei namens default.jpg im Ordner static/uploads/ liegt. Diese dient als Platzhalter für Rezepte ohne eigenes Bild.

5. Datenbank-Initialisierung
Du musst keine Datenbank manuell erstellen. Beim ersten Start der App passiert Folgendes automatisch:

Die SQLite-Datenbank genussreise.db wird im Ordner instance/ erstellt.

Alle Tabellen werden angelegt.

Die Standard-Kategorien (25 Stück) werden automatisch in die Datenbank geladen.

6. Anwendung starten
Starte den lokalen Entwicklungsserver:

Bash
python app.py
Die App ist nun unter [http://127.0.0.1:5000](http://127.0.0.1:5000) erreichbar.

🔐 Admin-Rechte erhalten
Um Rezepte zu löschen oder Benutzer zu verwalten, benötigst du Admin-Rechte:

Gehe auf die Registrieren-Seite.

Gib deine Daten ein.

Nutze den Admin-Key: GEHEIM123 (bitte in der Produktion ändern!).

🛠 Features
Pagination: Nur 9 Rezepte pro Seite für bessere Übersicht.

Suche: Volltextsuche in Titeln und Anleitungen.

Favoriten: Rezepte per Klick auf das Herz-Icon speichern.

Kategorien: Rezepte nach 25 verschiedenen Typen filtern.

Zeiten: Automatische Berechnung der Gesamtzeit (Vorbereitung + Garen + Ruhe).

💡 Tipps für die Zusammenarbeit
Die Datei .gitignore sorgt dafür, dass deine lokale Datenbank und deine Test-Uploads nicht hochgeladen werden.

Sollten Datenbank-Fehler auftreten, lösche einfach die instance/genussreise.db und starte die App neu, um eine frische Struktur zu erhalten.

Viel Spaß beim Kochen und Coden! 👨‍🍳💻

Was du jetzt noch tun musst:
Damit die Anleitung perfekt funktioniert, tippe einmal kurz diesen Befehl in dein Terminal (während deine virtuelle Umgebung aktiv ist):

Bash
pip freeze > requirements.txt