# =====================================================================================
#  cura_KlipperFeatureTypes.py – Cura-Post-Processing-Skript
#  -----------------------------------------------------------------------------------
#  Macht fuer Cura drei Dinge, die Orca von Haus aus mitbringt:
#   1) Nach jedem ";TYPE:..." -> "APPLY_TYPE TYP=..."  (Live-Tuning pro Feature)
#   2) Nach jedem ";LAYER:..." -> "LAYER_MARK"         (Schichtzaehler, Pause bei Schicht)
#   3) GANZ OBEN: "EXCLUDE_OBJECT_DEFINE" mit der Gesamt-Bounding-Box aller Druck-Moves
#      -> dadurch funktionieren das ADAPTIVE Bed-Mesh und die kollisionsfreie Park-/
#      Purge-Platzierung auch mit Cura-Dateien. (In Orca stattdessen "Objekte markieren"
#      aktivieren - dann NICHT dieses Skript dafuer noetig, es erkennt das selbst.)
#
#  INSTALLATION (Cura 5.x):
#   1) Cura: Hilfe -> Konfigurationsordner anzeigen  (oefnen)
#   2) Dort in den Ordner "scripts" kopieren (Ordner ggf. anlegen):
#         scripts/KlipperFeatureTypes.py   (diese Datei, exakt so benannt!)
#   3) Cura NEU starten
#   4) Erweiterungen -> Nachbearbeitung -> Nachbearbeitung konfigurieren ->
#      Skript hinzufuegen -> "Klipper: Feature-Types & Objekt-Box"
#   Fertig – das Skript laeuft bei jedem Slice.
# =====================================================================================

try:
    from ..Script import Script  # Cura-Plugin-Umgebung
except ImportError:
    from Script import Script    # Fallback beim manuellen Test


class KlipperFeatureTypes(Script):
    def getSettingDataString(self):
        return {
            "name": "Klipper: Feature-Types & Objekt-Box",
            "key": "klipper_feature_types",
            "metadata": {},
            "settings": {
                "objektbox": {
                    "label": "Objekt-Box einfuegen (adaptives Mesh/Parken)",
                    "description": "Setzt EXCLUDE_OBJECT_DEFINE mit der Gesamt-Bounding-Box aller Extrusions-Moves an den Dateianfang.",
                    "type": "bool",
                    "default_value": True,
                },
            },
        }

    def execute(self, data):
        objektbox = self.getSettingValueByKey("objektbox")

        # ---------- 1) Bounding-Box ueber alle Extrusions-Moves berechnen -------------
        min_x = min_y = 1e9
        max_x = max_y = -1e9
        letzte_x = letzte_y = None
        for zeile in data:
            p = zeile.strip()
            if not p.startswith("G1") and not p.startswith("G0"):
                continue
            xs = ys = es = None
            for token in p.split():
                if token.startswith("X") and token[1:].replace(".", "", 1).lstrip("-").isdigit():
                    xs = float(token[1:])
                elif token.startswith("Y") and token[1:].replace(".", "", 1).lstrip("-").isdigit():
                    ys = float(token[1:])
                elif token.startswith("E") and token[1:].replace(".", "", 1).lstrip("-").isdigit():
                    es = float(token[1:])
            if xs is not None:
                letzte_x = xs
            if ys is not None:
                letzte_y = ys
            # Zaehlt als Druck-Move: Extrusion mit bekannter Position
            if es is not None and es > 0 and letzte_x is not None and letzte_y is not None:
                min_x = min(min_x, letzte_x); max_x = max(max_x, letzte_x)
                min_y = min(min_y, letzte_y); max_y = max(max_y, letzte_y)

        box_einfuegen = (objektbox and min_x < max_x and min_y < max_y
                         and max_x - min_x < 1000)
        if box_einfuegen:
            cx = (min_x + max_x) / 2.0
            cy = (min_y + max_y) / 2.0
            # Als einzelnes "Objekt" namens druck definieren (Polygon = Box)
            polygon = "[{:.2f},{:.2f}], [{:.2f},{:.2f}], [{:.2f},{:.2f}], [{:.2f},{:.2f}]".format(
                min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y)

        # ---------- 2) Datei Zeile fuer Zeile neu aufbauen ----------------------------
        neu = []
        kopf_done = False
        letzter_typ = None
        for zeile in data:
            neu.append(zeile)
            p = str(zeile).strip()

            # Objekt-Box hinter dem ersten reinen Befehl nach dem Header einfuegen
            if box_einfuegen and not kopf_done and p.startswith("G28"):
                kopf_done = True
                neu.append(";KLIPPER Objekt-Box (adaptives Mesh/Parken)\n")
                neu.append("EXCLUDE_OBJECT_DEFINE NAME=druck CENTER={:.2f},{:.2f} POLYGON={}\n".format(cx, cy, polygon))
                neu.append("M117 Klipper-Box aktiv\n")

            if p.startswith(";TYPE:"):
                typ = p.split(":", 1)[1].strip()
                if typ and typ != letzter_typ:
                    letzter_typ = typ
                    neu.append("APPLY_TYPE TYP={}\n".format(typ))
            elif p.startswith(";LAYER:"):
                neu.append("LAYER_MARK\n")

        return neu
