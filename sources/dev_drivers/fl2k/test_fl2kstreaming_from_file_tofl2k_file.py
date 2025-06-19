import subprocess

def stream_to_fl2k_file(input_file, sampling_rate, fl2k_file_path="fl2k_file", buffer_size=4096):
    """
    Streamt einen Bytestream aus einer Datei und übergibt ihn per stdin an fl2k_file.

    :param input_file: Pfad zur Eingabedatei.
    :param sampling_rate: Abtastrate für fl2k_file (z. B. 10000000 für 10 MS/s).
    :param fl2k_file_path: Pfad zur fl2k_file-Binärdatei.
    :param buffer_size: Puffergröße für das Streaming (Standard: 4096 Bytes).
    """
    try:
        # Öffnen der Eingabedatei im Binärmodus
        with open(input_file, "rb") as f:
            # Starten von fl2k_file mit den entsprechenden Parametern
            process = subprocess.Popen(
                [fl2k_file_path, "-s", str(sampling_rate)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Lesen und Streamen der Datei in Blöcken
            while chunk := f.read(buffer_size):
                process.stdin.write(chunk)

            # Warten, bis fl2k_file beendet ist
            process.stdin.close()
            stdout, stderr = process.communicate()

            # Ausgabe der Ergebnisse
            print("fl2k_file output:")
            print(stdout.decode())
            if stderr:
                print("fl2k_file errors:")
                print(stderr.decode())

    except FileNotFoundError:
        print(f"Die Datei {input_file} wurde nicht gefunden.")
    except subprocess.SubprocessError as e:
        print(f"Fehler beim Ausführen von fl2k_file: {e}")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

# Beispielaufruf
stream_to_fl2k_file("input.bin", sampling_rate=10000000)
