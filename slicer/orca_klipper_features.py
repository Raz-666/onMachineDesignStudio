#!/usr/bin/env python3
# =====================================================================================
#  orca_klipper_features.py – Post-Processing-Skript fuer OrcaSlicer / PrusaSlicer
#  -----------------------------------------------------------------------------------
#  AUFGABE:
#   Orca schreibt Feature-Wechsel als Kommentare in die Datei (";TYPE:Outer wall").
#   Klipper kann Kommentare nicht verarbeiten. Dieses Skript setzt hinter jeden
#   Feature-Wechsel einen echten Befehl:
#        APPLY_TYPE TYPE=Outer wall
#   Unser APPLY_TYPE-Makro (macros/10_live_tuning.cfg) setzt daraufhin Speed-Faktor /
#   Beschleunigung / (Ironing-)Flow – und das LIVE am LCD oder in Mainsail aenderbar.
#
#  INSTALLATION (OrcaSlicer):
#   1) Diesen Ordner auf den Raspberry Pi kopieren (z.B. /home/pi/klipper-e3-r2d2/)
#   2) Orca: Vorbereiten -> Nachbearbeitung (Post-Processing) ->
#      "python3 /home/pi/klipper-e3-r2d2/slicer/orca_klipper_features.py;"
#      (ja, MIT Semikolon am Ende – Orca trennt mehrere Skripte damit)
#   3) Fertig. Beim Slicen laeuft das Skript automatisch (Orca startet es lokal auf
#      deinem PC – es aendert nur die exportierte G-Code-Datei, sonst nichts).
#
#  HINWEIS: LAYER_MARK (Schichtzaehler/Pausen) kommt NICHT von hier – das steht im
#  Orca-Feld "G-Code bei Schichtwechsel" (siehe slicer/ORCA.md).
# =====================================================================================
import sys

# Orca/Slic3r-Featurenamen -> werden 1:1 an APPLY_TYPE durchgereicht (das Makro
# normalisiert selbst: WALL-OUTER, WALL-INNER, SUPPORT, SPARSE-INFILL, SOLID-INFILL,
# IRONING, SKIRT, SONSTIGE)
def main():
    if len(sys.argv) < 2:
        print("orca_klipper_features.py: keine G-Code-Datei uebergeben", file=sys.stderr)
        sys.exit(1)
    pfad = sys.argv[-1]
    with open(pfad, "r", encoding="utf-8", errors="replace") as f:
        zeilen = f.readlines()

    neu = []
    letzter_typ = None
    ersetzungen = 0
    for zeile in zeilen:
        neu.append(zeile)
        p = zeile.strip()
        if p.startswith(";TYPE:"):
            typ = p.split(":", 1)[1].strip()
            if typ and typ != letzter_typ:        # nur bei echtem Wechsel einsetzen
                letzter_typ = typ
                neu.append("APPLY_TYPE TYPE={}\n".format(typ))
                ersetzungen += 1

    with open(pfad, "w", encoding="utf-8") as f:
        f.writelines(neu)
    print("orca_klipper_features.py: {} APPLY_TYPE-Marker eingesetzt ({})".format(
        ersetzungen, pfad))

if __name__ == "__main__":
    main()
