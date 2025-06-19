###Lesen von File und streamen über fl2k_file:

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

#####################################Queue Version für pipes


from multiprocessing import Process, Queue
import struct
import time

# Begrenzter Puffer für Binärdaten mit maximal 5 Elementen
buffer = Queue(maxsize=5)

# Schreibprozess
def writer(q):
    print("Schreibprozess gestartet...")
    try:
        for i in range(20):  # Schreibe 20 int16-Werte #TODO: Passe Puffergröße an !
            # Binärdaten erstellen: int16 -> struct.pack
            data = struct.pack("h", i)  # 'h' für int16
            q.put(data)  # Blockiert, wenn der Puffer voll ist
            print(f"Geschrieben: {i} (binär: {data})")
            time.sleep(0.2)  # Simuliere eine Verzögerung beim Schreiben
    except KeyboardInterrupt:
        print("Schreibprozess beendet.")

# Leseprozess
def reader(q):
    print("Leseprozess gestartet...")
    try:
        while True:
            # Daten aus dem Puffer lesen (blockiert, wenn leer)
            data = q.get()
            # Binärdaten in int16 dekodieren
            value = struct.unpack("h", data)[0]  # 'h' für int16
            print(f"Gelesen: {value} (binär: {data})")
            time.sleep(0.5)  # Simuliere eine Verzögerung beim Lesen
    except KeyboardInterrupt:
        print("Leseprozess beendet.")

# Prozesse starten
if __name__ == "__main__":
    writer_process = Process(target=writer, args=(buffer,))
    reader_process = Process(target=reader, args=(buffer,))

    writer_process.start()
    reader_process.start()

    try:
        # Warten, bis beide Prozesse abgeschlossen sind
        writer_process.join()
        reader_process.join()
    except KeyboardInterrupt:
        print("Hauptprozess beendet.")
        writer_process.terminate()
        reader_process.terminate()


########################VERSION 2 mit Kommunikation über stdin/stdout############################################

import subprocess
from multiprocessing import Queue, Process

# Puffer initialisieren
buffer = Queue(maxsize=10)

# Funktion zum Starten des Executables und Schreiben in den Puffer
def writer_from_executable(executable_path, buffer):
    # Starte das Executable
    process = subprocess.Popen(
        [executable_path],  # Pfad zum Executable
        stdout=subprocess.PIPE,  # Leite stdout um
        bufsize=1  # Zeilenweise Pufferung
    )
    
    try:
        # Lese die Daten zeilenweise von stdout und schreibe sie in den Puffer
        for line in process.stdout:
            buffer.put(line)  # Blockiert, falls der Puffer voll ist
            print(f"Geschrieben: {line}")
    except Exception as e:
        print(f"Fehler im Writer: {e}")
    finally:
        process.stdout.close()
        process.wait()  # Warten, bis der Prozess beendet ist
        print("Executable beendet.")

# Beispiel-Leseprozess
def reader(buffer):
    while True:
        data = buffer.get()  # Blockiert, bis Daten verfügbar sind
        print(f"Gelesen: {data.decode().strip()}")
        if data.strip() == b"STOP":
            break

# Prozesse starten
if __name__ == "__main__":
    # Pfad zum Executable (ersetze dies durch deinen echten Pfad)
    executable_path = "./dein_executable"
    
    writer_process = Process(target=writer_from_executable, args=(executable_path, buffer))
    reader_process = Process(target=reader, args=(buffer,))

    writer_process.start()
    reader_process.start()

    writer_process.join()
    buffer.put(b"STOP")  # Stop-Signal senden
    reader_process.join()

###############Version 2: Verwendung von named pipes:############################################

import os
import subprocess
from multiprocessing import Queue, Process

# Puffer initialisieren
buffer = Queue(maxsize=10)

# Funktion zum Starten des Executables und Lesen aus der Pipe
def writer_from_fifo(pipe_path, executable_path, buffer):
    # Stelle sicher, dass die Pipe existiert
    if not os.path.exists(pipe_path):
        os.mkfifo(pipe_path)

    try:
        # Starte das Executable, das in die Pipe schreibt
        process = subprocess.Popen([executable_path], stdout=open(pipe_path, "wb"))

        # Lese aus der Pipe und schreibe in den Puffer
        with open(pipe_path, "rb") as fifo:
            while True:
                data = fifo.read(1024)  # Lese Daten in Blöcken
                if not data:
                    break
                buffer.put(data)  # Schreibe Daten in den Puffer
                print(f"Geschrieben: {data}")
    except Exception as e:
        print(f"Fehler im Writer: {e}")
    finally:
        if os.path.exists(pipe_path):
            os.unlink(pipe_path)  # Entferne die Pipe
        process.wait()
        print("Executable beendet.")

# Beispiel-Leseprozess
def reader(buffer):
    while True:
        data = buffer.get()
        print(f"Gelesen: {data}")
        if data == b"STOP":
            break

# Prozesse starten
if __name__ == "__main__":
    pipe_path = "/tmp/my_fifo"  # Pfad zur benannten Pipe
    executable_path = "./dein_executable"  # Pfad zum Executable

    writer_process = Process(target=writer_from_fifo, args=(pipe_path, executable_path, buffer))
    reader_process = Process(target=reader, args=(buffer,))

    writer_process.start()
    reader_process.start()

    writer_process.join()
    buffer.put(b"STOP")
    reader_process.join()
