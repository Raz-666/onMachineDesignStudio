# R286 — Web-UI integration in Mainsail

Die R2-D2 Web-UI (`web/index.html` + `web/r2_menu.py`, installiert via
`web/install_web.sh`) läuft auf einer **eigenen nginx-Site** unter
`/r2lcd/` auf einem eigenen Port. Mainsasils nginx-Konfig wird **nicht**
berührt.

## Empfohlene Integration: Mainsail-Custom-Button (Link-Typ)

Die robuste, Cross-Origin-sichere Variante. Mainsail öffnet das Display
in einem eigenen Panel/Tab — display-unabhängig (Browser, App, Tablet),
1:1 gleich wie am LCD.

### So fügst du den Button hinzu

1. Öffne Mainsail → **Settings** ( Zahnrad ) → **System**.
2. Scrolle zu **Custom Buttons** (oder über die Konfigurationsdatei
   `~/printer_data/config/mainsail/config/mainsail.cfg` bzw. die
   Mainsail-`config.json`).
3. Füge einen Button mit Link-Typ hinzu:

   ```json
   {
     "name": "R2-D2 Display",
     "type": "link",
     "url": "http://<PI-IP>:<PORT>/r2lcd/",
     "icon": "mdi-television-classic"
   }
   ```

   `<PI-IP>` = IP des Druckers, `<PORT>` = der Port, auf dem
   `install_web.sh` die Site geöffnet hat (das Skript gibt die URL
   aus — Standard-Port `7126` oder类似).
4. Seite neu laden — der Button erscheint in der Mainsail-Leiste und
   öffnet das R2-D2-Display.

## Optional: echte iframe-Einbettung

Möglich, weil die eigene Site **keine `X-Frame-Options`** setzt.
Allerdings: der **CSRF-Guard** der Site (R206/R207) vergleicht das
`Origin`-Header mit dem Host. Bei Cross-Origin-Einbettung (Mainsail auf
einem anderen Origin) müsste der Guard das Mainsail-Origin als erlaubt
sehen — pragmatischer und sicherer ist der **Custom-Button-Link** oben.

Für eine echte iframe-Einbettung (z.B. ein Panel innerhalb Mainsail):

1. Mainsail-Konfiguration erweitern (Mainsail hat keine eingebaute
   iframe-Panel-API — realistisch über Custom-CSS/JS oder einen
   Mainsail-Plugin).
2. CSRF-Guard der r2lcd-Site erlauben: im nginx-Site-File der
   `map $http_origin $r2_csrf_bad`-Regel das Mainsail-Origin als
   zulässig ergänzen (URI des Mainsail-Hosts).
3. Dann `<iframe src="http://<PI-IP>:<PORT>/r2lcd/">` einfügen.

## Warum der Custom-Button der bessere Weg ist

- Keine Mainsail-Plugin-Abhängigkeit (robust bei Mainsail-Updates).
- Cross-Origin-sicher (CSRF-Guard bleibt wirksam).
- Display-unabhängig: Browser, App, Tablet — 1:1 das LCD.
- MCU-schonend: Web-UI kommuniziert nur host-seitig über Moonraker
  (WebSocket-Subscription — Moonraker pusht nur bei Veränderung).

## WebSocket-Subscription (R286)

Seit R286 nutzt die Web-UI eine **WebSocket-Subscription** statt des
3-Sekunden-Pollings. Moonraker sendet Live-Werte nur bei Veränderung;
Polling bleibt als 15-s-Keepalive + Fallback. Das entlastet
`ClientConnection.process_received` und die Host-CPU massiv (Reactor-Stall-Analyse).

## TMC-Check-Reduktion (Reactor-Stall)

`TMCErrorCheck._do_periodic_check` (328x in den Stall-Frames) ist eine
**periodische Moonraker-Prüfung**. Wenn der TMC-Fehler-Check nicht
aktiv benötigt wird, die Prüfrate in der Moonraker-Konf
(`[tmc_error_check]`, `check_interval`) verlängern oder deaktivieren —
das reduziert die Reaktor-Callbacks weiter.

## G-Code-Batching

Die Web-UI sendet Menü-Befehle bereits als **Batch-Script**
(`/printer/gcode/script` mit allen Befehlen eines Klicks in einem POST) —
das reduziert die Pipe-Signale (`_got_pipe_signal` / `dispatch_gcode`).
