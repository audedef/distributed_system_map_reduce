import socket
import json
import struct
import threading
import time
import os


# Lire les adresses des machines à partir du fichier machines.txt
with open('machines.txt', 'r') as file:
    machines = [line.strip() for line in file.readlines()]

tab_fin_phase_1 = [False]*len(machines)
tab_fin_phase_2 = [False]*len(machines)
tab_fin_phase_3 = [False]*len(machines)
tab_fin_phase_4 = [False]*len(machines)
tab_fin_phase_5 = [False]*len(machines)


# Convertir la liste des machines en JSON
machines_json = json.dumps(machines)

block_size = 50 * 1024 * 1024  # 50 Mo en octets


# Chemin des fichiers à combiner
chemin_fichiers = "/Users/macbook/Documents/data_science_master/systemes_repartis/TP"
fichiers_disponibles = [f for f in os.listdir(
    chemin_fichiers) if f.endswith('.warc.wet')]

# Combiner les fichiers sélectionnés en un seul
fichier_combinaison = '/Users/macbook/Documents/data_science_master/systemes_repartis/TP/fichier_combine.warc.wet'
if not os.path.exists(fichier_combinaison):
    with open(fichier_combinaison, 'w') as fichier_combine:
        for nom_fichier in fichiers_disponibles:
            chemin_complet = os.path.join(chemin_fichiers, nom_fichier)
            with open(chemin_complet, 'r') as fichier:
                for ligne in fichier:
                    fichier_combine.write(ligne)
    print(f"Les {len(fichiers_disponibles)} fichiers ont été combinés.")
else:
    print(f"Le fichier combiné existe déjà : {fichier_combinaison}")

# Diviser le fichier en bloc de 50 Mo
blocs = []
with open(fichier_combinaison, 'r') as fichier:
    bloc_courant = []
    taille_courante = 0
    for ligne in fichier:
        taille_courante += len(ligne.encode('utf-8'))
        if taille_courante > block_size:
            blocs.append(bloc_courant)
            bloc_courant = [ligne]
            taille_courante = len(ligne.encode('utf-8'))
        else:
            bloc_courant.append(ligne)
    if bloc_courant:
        blocs.append(bloc_courant)

print(f"Divisé le fichier en {len(blocs)} blocs de 50 Mo.")

# Associer chaque bloc à une machine
blocs_par_machine = {}
for i, bloc in enumerate(blocs):
    machine = machines[i % len(machines)]
    if machine not in blocs_par_machine:
        blocs_par_machine[machine] = []
    blocs_par_machine[machine].append(bloc)


# Dictionnaire pour stocker les connexions
connexions = {}

# Créer les connexions à toutes les machines
for machine in machines:
    try:
        # Créer un socket TCP/IP
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Se connecter à la machine
        client_socket.connect((machine, 8000))
        # Stocker la connexion
        connexions[machine] = client_socket
        print(f"Connexion établie avec {machine}")
    except Exception as e:
        print(f"Erreur lors de la connexion à {machine}: {e}")


def envoyer_message(client_socket, message):
    # Convertir le message en bytes
    message_bytes = message.encode('utf-8')
    # Envoyer la taille du message en utilisant send
    taille_message = struct.pack('!I', len(message_bytes))

    total_envoye = 0
    while total_envoye < len(taille_message):
        envoye = client_socket.send(taille_message[total_envoye:])
        if envoye == 0:
            raise RuntimeError("La connexion a été fermée")
        total_envoye += envoye
    # Envoyer le message
    client_socket.sendall(message_bytes)


def envoyer_messages():
    # Envoyer la liste des machines à chaque machine
    for machine, client_socket in connexions.items():
        try:
            envoyer_message(client_socket, machines_json)
            print(f"Envoyé la liste des machines à {machine}")
        except Exception as e:
            print(f"Erreur lors de l'envoi à {machine}: {e}")

   # Envoyer les blocs aux machines correspondantes
    for machine, blocs in blocs_par_machine.items():
        try:
            client_socket = connexions[machine]
            for bloc in blocs:
                bloc_message = ''.join(bloc)
                envoyer_message(client_socket, bloc_message)
                print(f"Envoyé un bloc à {machine}")
        except Exception as e:
            print(f"Erreur lors de l'envoi à {machine}: {e}")

    # Envoyer le message de fin de phase à chaque machine
    for machine, client_socket in connexions.items():
        try:
            envoyer_message(client_socket, "FIN PHASE 1")
            print(f"Envoyé 'FIN PHASE 1' à {machine}")
        except Exception as e:
            print(f"Erreur lors de l'envoi à {machine}: {e}")


def recevoir_exactement(client_socket, n):
    data = b''
    while len(data) < n:
        packet = client_socket.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connexion fermée par le client")
        data += packet
    return data


def recevoir_message(client_socket):
    # Recevoir la taille du message
    taille_message = struct.unpack(
        '!I', recevoir_exactement(client_socket, 4))[0]
    # Recevoir le message en utilisant la taille
    data = recevoir_exactement(client_socket, taille_message)
    return data.decode('utf-8')


def recevoir_resultat():
    version = 1
    resultat_path = f"resultat_v{version}.txt"
    while os.path.exists(resultat_path):
        version += 1
        resultat_path = f"resultat_v{version}.txt"

    for machine, client_socket in connexions.items():
        try:
            message_reçu = recevoir_message(client_socket)
            if message_reçu == "OK FIN PHASE 1":
                tab_fin_phase_1[machines.index(machine)] = True
                # si toutes les machines ont fini la phase 1
                if all(tab_fin_phase_1):
                    for machine, client_socket in connexions.items():
                        envoyer_message(client_socket, "GO PHASE 2")
                        print(f"Envoyé 'GO PHASE 2' à {machine}")

                    message_reçu = recevoir_message(client_socket)
                    if message_reçu == "FIN PHASE 2":
                        for machine, client_socket in connexions.items():
                            print(f"'FIN PHASE 2' reçu de {machine}")
                            # Attendre que toutes les machines aient fini la phase 2
                            tab_fin_phase_2[machines.index(machine)] = True
                        # si toutes les machines ont fini la phase 2
                        if all(tab_fin_phase_2):
                            for machine, client_socket in connexions.items():
                                envoyer_message(client_socket, "GO PHASE 3")
                                print(f"Envoyé 'GO PHASE 3' à {machine}")

                            message_reçu = recevoir_message(client_socket)
                            if message_reçu:
                                while message_reçu == "FIN PHASE 2":
                                    message_reçu = recevoir_message(
                                        client_socket)
                                if message_reçu == "FIN PHASE 3":
                                    for machine, client_socket in connexions.items():
                                        print(
                                            f"'FIN PHASE 3' reçu de {machine}")
                                        tab_fin_phase_3[machines.index(
                                            machine)] = True
                                    # Toutes les machines ont fini la phase 3
                                    if all(tab_fin_phase_3):
                                        for machine, client_socket in connexions.items():
                                            envoyer_message(
                                                client_socket, "GO PHASE 4")
                                            print(
                                                f"Envoyé 'GO PHASE 4' à {machine}")

                                        message_reçu = recevoir_message(
                                            client_socket)
                                        if message_reçu:
                                            while message_reçu == "FIN PHASE 2":
                                                message_reçu = recevoir_message(
                                                    client_socket)
                                            while message_reçu == "FIN PHASE 3":
                                                message_reçu = recevoir_message(
                                                    client_socket)
                                            if message_reçu == "FIN PHASE 4":
                                                for machine, client_socket in connexions.items():
                                                    print(
                                                        f"'FIN PHASE 4' reçu de {machine}")
                                                    # Attendre que toutes les machines aient fini la phase 4
                                                    tab_fin_phase_4[machines.index(
                                                        machine)] = True
                                                if all(tab_fin_phase_4):
                                                    # Recevoir les quantiles de chaque machine
                                                    quantiles_min = None
                                                    for machine, client_socket in connexions.items():
                                                        message_reçu = recevoir_message(
                                                            client_socket)
                                                        while message_reçu == "FIN PHASE 2":
                                                            message_reçu = recevoir_message(
                                                                client_socket)
                                                        while message_reçu == "FIN PHASE 3":
                                                            message_reçu = recevoir_message(
                                                                client_socket)
                                                        while message_reçu == "FIN PHASE 4":
                                                            message_reçu = recevoir_message(
                                                                client_socket)
                                                        quantiles = json.loads(
                                                            message_reçu)

                                                        # Initialiser les quantiles minimaux s'ils ne sont pas encore définis
                                                        if quantiles_min is None:
                                                            quantiles_min = quantiles
                                                        else:
                                                            # Mettre à jour les quantiles minimaux
                                                            for i, quantile in enumerate(quantiles):
                                                                quantiles_min[i] = min(
                                                                    quantiles_min[i], quantile)

                                                    print(f"Quantiles minimaux déterminés :"
                                                          f"{quantiles_min}")
                                                    # Préparer le dictionnaire des seuils à envoyer aux machines
                                                    seuils = {
                                                        'seuils': quantiles_min}

                                                    for machine, client_socket in connexions.items():
                                                        envoyer_message(
                                                            client_socket, "GO PHASE 5")

                                                        envoyer_message(
                                                            client_socket, json.dumps(seuils))
                                                        print(
                                                            f"Envoyé 'GO PHASE 5' et seuils à {machine}")

                                                    message_reçu = recevoir_message(
                                                        client_socket)
                                                    if message_reçu == "FIN PHASE 5":
                                                        for machine, client_socket in connexions.items():
                                                            print(
                                                                f"'FIN PHASE 5' reçu de {machine}")
                                                            # Attendre que toutes les machines aient fini la phase 5
                                                            tab_fin_phase_5[machines.index(
                                                                machine)] = True
                                                        if all(tab_fin_phase_5):
                                                            for machine, client_socket in connexions.items():
                                                                envoyer_message(
                                                                    client_socket, "GO PHASE 6")
                                                                print(
                                                                    f"Envoyé 'GO PHASE 6' à {machine}")

                                                            # Réception et écriture des résultats
                                                            print(f"Client : Début de la réception des résultats des serveurs. "
                                                                  f"Résultat enregistré dans '{resultat_path}'.")
                                                            with open(resultat_path, 'w') as fichier_resultat:
                                                                for machine, client_socket in connexions.items():
                                                                    client_socket.sendall(
                                                                        b"GO")
                                                                    resultat_recu = recevoir_message(
                                                                        client_socket)
                                                                    while resultat_recu == "FIN PHASE 5":
                                                                        resultat_recu = recevoir_message(
                                                                            client_socket)
                                                                    # Ecrire le dernier résultats dans le fichier output
                                                                    fichier_resultat.write(
                                                                        resultat_recu + "\n")
                                                                    print(f"Client : Résultats de "
                                                                          f"{machine} ajoutés au fichier '{resultat_path}'.")
                                                                    # Envoyer le signal de fin au serveur
                                                                    client_socket.sendall(
                                                                        b"FIN")
                                                                    print(
                                                                        f"Client : Signal de fin envoyé à {machine}.")

                                                            print(f"Client : Fin de la réception des résultats des serveurs."
                                                                  f"Fichier complet : '{resultat_path}'.")

        except Exception as e:
            print(f"Erreur lors de la réception de {machine}: {e}")


# Enregistrer l'heure de début
start_time = time.time()

# Créer et démarrer les threads pour envoyer et recevoir les messages
thread_envoi = threading.Thread(target=envoyer_messages)
thread_reception = threading.Thread(target=recevoir_resultat)

thread_envoi.start()
thread_reception.start()

# Attendre que les threads se terminent
thread_envoi.join()
thread_reception.join()

# Enregistrer l'heure de fin
end_time = time.time()

# Calculer la durée totale
duration = end_time - start_time
# Afficher la durée totale
print(f"Durée totale du processus : {duration:.2f} secondes")
