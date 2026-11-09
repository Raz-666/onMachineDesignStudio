# GITHUB.md — Updates direkt von GitHub (ohne Zip-Download)

Der Zip-Weg bleibt (er funktioniert offline und per Anhang), aber wenn das
Paket einmal als **Git-Clone** auf dem Pi liegt, ist ein Update **ein
einzelner Befehl** — kein Herunterladen, kein Mainsail-Upload:

```bash
bash ~/printer_data/config/klipper-e3-r2d2/update.sh --git
```

Der Befehl holt den Stand von GitHub, prüft den Downgrade-Schutz
(Zähler-Regel wie beim Zip), setzt die Paketdateien auf den Origin-Stand
und fährt dann die komplette bekannte Choreographie durch: Include-Check,
Version, LED-Profil neu anwenden, FIRMWARE_RESTART, Watcher-Neustart +
Census, Web-LCD-Refresh. Deine persönlichen Dateien (`printer.cfg`,
`r2_hardware.cfg`, `variables.cfg`, `moonraker.conf`) liegen **außerhalb**
des Repos und werden nie angefasst.

---

## 1) Einmalig: das Repository auf GitHub bringen (am PC, ~10 Minuten)

**Du brauchst:** die Datei `r2d2-repo.bundle` (liegt der Release-Report-
Workbench bei — sie enthält das Repository **mit der kompletten
Historie**) und Git auf dem PC (Windows: <https://git-scm.com/download/win>,
macOS: `xcode-select --install`, Linux: Paketmanager).

```bash
cd ~/Downloads                     # wo auch immer der Bundle liegt
git clone r2d2-repo.bundle klipper-e3-r2d2
cd klipper-e3-r2d2
git remote remove origin           # origin zeigte noch auf die Bundle-Datei
git branch --show-current          # merk Dir den Namen (z. B. master)
```

**Auf github.com:** oben rechts „+“ → *New repository* → Name z. B.
`klipper-e3-r2d2` → **Private** (empfohlen; im Repo stehen keine
Geheimnisse — `printer.cfg`/`moonraker.conf`/Variablen sind nicht
enthalten —, aber es ist Dein Drucker-Setup. Public ginge wegen GPL-3.0
auch) → **kein** README/LICENSE/.gitignore anhäkeln (alles schon da) →
*Create repository*.

Dann verbinden und hochladen:

```bash
# SSH (empfohlen - einmalig einen Key einrichten, siehe unten)
git remote add origin git@github.com:DEIN_NAME/klipper-e3-r2d2.git
# oder HTTPS (fragt nach Name + Personal Access Token als Passwort):
# git remote add origin https://github.com/DEIN_NAME/klipper-e3-r2d2.git

git push -u origin master          # Branch-Name von oben
```

> **SSH-Key in 30 Sekunden** (falls noch keiner da ist):
> `ssh-keygen -t ed25519` → Enter, Enter → `cat ~/.ssh/id_ed25519.pub` →
> den Schlüssel unter github.com → *Settings → SSH and GPG keys → New*
> einfügen. HTTPS braucht stattdessen einen *Personal Access Token*
> (*Settings → Developer settings → Tokens*) — GitHub nimmt keine
> Passwörter mehr.

---

## 2) Einmalig: den Drucker (Pi) auf den Clone umstellen (~5 Minuten)

Der Pi braucht nur **Lese**-Zugriff (pull). Bei einem **privaten** Repo
legtst Du einmalig einen Deploy-Key an (siehe Kasten unten); bei einem
öffentlichen Repo reicht HTTPS ohne jede Anmeldung.

Per SSH auf dem Pi:

```bash
ssh pi@<deine-pi-ip>
cd ~/printer_data/config

# a) alten Ordner beiseite (Sicherung - printer.cfg etc. liegen sowieso
#    AUSSERHALB und bleiben unberührt)
mv klipper-e3-r2d2 klipper-e3-r2d2-vor-git

# b) den Clone holen
git clone https://github.com/DEIN_NAME/klipper-e3-r2d2.git
#    (privates Repo:  git clone git@github.com:DEIN_NAME/klipper-e3-r2d2.git)

# c) erster Lauf: "already up to date" + komplette Choreographie
#    (LED-Profil, Includes, Restarts, Watcher-Census, Web-LCD)
bash klipper-e3-r2d2/update.sh --git
```

Kontrolle: Konsole zeigt
`Macro system OK: all 19 modules loaded and current (build R2-2026-11-09.136ae)`,
LCD und Mainsail gehen wie gewohnt. **Erst wenn alles tut:**

```bash
rm -rf klipper-e3-r2d2-vor-git
```

> **Privates Repo → Deploy-Key (read-only, einmalig):**
> ```bash
> ssh-keygen -t ed25519 -f ~/.ssh/r2d2_github -N ""
> cat ~/.ssh/r2d2_github.pub
> ```
> Den Schlüssel auf GitHub ins Repo: *Settings → Deploy keys → Add* (read-only
> Häkchen genügt). Dann einmalig:
> ```bash
> cat >> ~/.ssh/config <<'EOF'
> Host github.com
>   IdentityFile ~/.ssh/r2d2_github
> EOF
> ```

---

## 3) Jedes weitere Update: zwei Schritte

**Schritt A — neuer Stand auf GitHub** (siehe Kasten unten, wie der
dahin kommt).

**Schritt B — auf dem Pi ziehen:**

```bash
bash ~/printer_data/config/klipper-e3-r2d2/update.sh --git
```

Das Skript sagt selbst, was passiert: `fetching origin …` →
`updating <alt> -> <neu>` (oder `already up to date` — dann läuft nur die
Choreographie, das ist abgesichert und harmlos) → Restarts →
`== done. Happy printing! ==`.

**Verhalten bei Problemen:**
- Lokale Änderungen im Paket-Ordner blockieren den Lauf (mit
  `git stash`-Hinweis) — bewusst, damit nichts Eigenes verloren geht.
  Bewusst überschreiben: `update.sh --git --force`.
- Ein Origin, der **älter** ist als die installierte Version (Rollback /
  Force-Push), wird abgelehnt — gleiche Zähler-Regel wie beim Zip.
- Kein Netz / falscher Remote: klare Meldung, nichts passiert.

---

## Woher kommt der neue Stand auf GitHub?

Neue Releases entstehen in der Arena-Workbench (dort liegt die
Entwicklungshistorie). Zwei Wege auf GitHub:

**Weg 1 — der Bundle (2 Befehle am PC, immer möglich):**
Jedes Release liegt als aktualisierte `r2d2-repo.bundle` in der Workbench.
Am PC:

```bash
cd <pfad-zu-deinem-lokalen-clone>
git pull <pfad-zur-neuen>/r2d2-repo.bundle master
git push
```

(`git pull` aus einer Bundle-Datei funktioniert wie von einem Remote.)
Danach auf dem Pi `update.sh --git` — fertig.

**Weg 2 — später:** Falls Arena mal einen GitHub-Anschluss bekommt, kann
der Push direkt aus der Workbench heraus passieren; bis dahin ist Weg 1
der offizielle Weg. Am Pi ändert sich dadurch nichts.

---

## Der Zip-Weg bleibt

Ohne GitHub gilt weiter: Zip in Mainsail in den **Config-Ordner**
hochladen (neben `printer.cfg`) und `bash update.sh` ausführen — siehe
INSTALL.md / README.md.

**Tipp zur Mischung:** ein über den Clone entpacktes Zip macht den Clone
„dirty“ (Dateien weichen vom Git-Stand ab) — der nächste `--git`-Lauf
weist darauf hin und wartet. Aufräumen geht dann mit
`git -C ~/printer_data/config/klipper-e3-r2d2 reset --hard origin/master`.
Empfehlung: nachdem der Clone läuft, **einen** Weg bleiben — `--git`.
