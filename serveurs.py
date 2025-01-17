import socket
import json
import struct
import threading
import os
import time
import re
import sys
from collections import defaultdict


# Obtenir le nom de la machine
nom_machine = socket.gethostname()
PORT = 8000
PORT2 = 6666
print(f"'{nom_machine}' : Bonjour, je suis la machine ")

# Créer un socket TCP/IP
serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Permet de réutiliser le port
serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Lier le socket à l'adresse et au port avec un maximum de 5 tentatives
for tentative in range(5):
    try:
        serveur_socket.bind(('0.0.0.0', PORT))
        print(f"'{nom_machine}' : Le socket est lié au port {PORT} après "
              f"{tentative + 1} tentative(s).")
        break
    except OSError:
        if tentative < 4:
            # Si le port est déjà utilisé, libérer le port en utilisant la commande kill
            print(f"'{nom_machine}' : Le port {PORT} est déjà utilisé. Tentative de libération du port "
                  f"({tentative + 1}/5)...")
            # Afficher avec print le PID du processus qui utilise le port
            pid = os.popen(f'lsof -t -i:{PORT}').read().strip()
            print(f"'{nom_machine}' : PID du processus qui utilise le port {PORT} :"
                  f" {pid}")
            if pid:
                # Libérer le port et afficher le résultat de kill
                os.system(f'kill -9 {pid}')
                print(f"'{nom_machine}' : Tentative de tuer le processus {pid}.")
            else:
                print(
                    f"'{nom_machine}' : Aucun processus n'utilise le port {PORT}.")
            time.sleep(5)
        else:
            raise Exception(f"'{nom_machine}' : Impossible de lier le socket au port "
                            f"{PORT} après 5 tentatives.")

# Créer un socket TCP/IP
serveur_socket2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Permet de réutiliser le port
serveur_socket2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Lier le socket à l'adresse et au port avec un maximum de 5 tentatives
for tentative in range(5):
    try:
        serveur_socket2.bind(('0.0.0.0', PORT2))
        print(f"'{nom_machine}' : Le socket est lié au port {PORT2} après "
              f"{tentative + 1} tentative(s).")
        break
    except OSError:
        if tentative < 4:
            # Si le port est déjà utilisé, libérer le port en utilisant la commande kill
            print(f"'{nom_machine}' : Le port {PORT2} est déjà utilisé. "
                  f"Tentative de libération du port ({tentative + 1}/5)...")
            # Afficher avec print le PID du processus qui utilise le port
            pid = os.popen(f'lsof -t -i:{PORT2}').read().strip()
            print(f"'{nom_machine}' : PID du processus qui utilise le port "
                  f"{PORT2} : {pid}")
            if pid:
                # Libérer le port et afficher le résultat de kill
                os.system(f'kill -9 {pid}')
                print(f"'{nom_machine}' : Tentative de tuer le processus {pid}.")
            else:
                print(
                    f"'{nom_machine}' : Aucun processus n'utilise le port {PORT2}.")
            time.sleep(5)
        else:
            raise Exception(f"'{nom_machine}' : Impossible de lier le socket au port "
                            f"{PORT2} après 5 tentatives.")


# Écouter les connexions entrantes
serveur_socket.listen(5)
print(f"'{nom_machine}' : PHASE 1 Le serveur écoute sur le port {PORT}...")

serveur_socket2.listen(5)
print(f"'{nom_machine}' : PHASE 2 Le serveur écoute sur le port {PORT2}...")

connexions = {}
connexions_phase_2 = {}
mots_recus_post_shuffle = []
occurrences = {}


def vider_buffer_socket(sock):
    sock.setblocking(0)  # Rendre la socket non bloquante
    while True:
        try:
            data = sock.recv(1024)  # Lire par blocs de 1024 octets
            if not data:
                # Aucun autre message dans le buffer
                break
        except BlockingIOError:
            # Plus de données disponibles à lire
            break
    print("Buffer de la socket vidé.")
    sock.setblocking(1)


def recevoir_exactement(client_socket, n):
    data = b''
    while len(data) < n:
        packet = client_socket.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data


def recevoir_message(client_socket):
    # Recevoir la taille du message
    taille_message_bytes = recevoir_exactement(client_socket, 4)
    if taille_message_bytes is None:
        print("Connexion fermée lors de la réception de la taille du message.")
        return None

    taille_message = struct.unpack('!I', taille_message_bytes)[0]

    # Recevoir le message en utilisant la taille
    data = recevoir_exactement(client_socket, taille_message)
    if data is None:
        print("Connexion fermée lors de la réception du message.")
        return None
    return data.decode('utf-8')


def envoyer_message(client_socket, message):
    try:
        # Convertir le message en bytes
        message_bytes = message.encode('utf-8')
        # Envoyer la taille du message
        client_socket.sendall(struct.pack('!I', len(message_bytes)))
        # Envoyer le message
        client_socket.sendall(message_bytes)
    except Exception as e:
        print(f"Erreur lors de l'envoi du message: {e}")


def gerer_connexion(client_socket, adresse_client):
    print(f"'{nom_machine}' : Connexion acceptée de {adresse_client}")

    # Ajouter la connexion au dictionnaire
    connexions[adresse_client] = client_socket

    nb_message = 0
    machines_reçues = []
    etat = 1

    # Déterminer le chemin du fichier temporaire en RAM
    version = 1
    temp_file_path = f'/dev/shm/mots_temp{version}.txt'
    while os.path.exists(temp_file_path):
        version += 1
        temp_file_path = f'/dev/shm/mots_temp{version}.txt'

    with open(temp_file_path, 'w') as temp_file:
        temp_file.write('')  # Créer le fichier vide

    while etat != 6:
        message_reçu = recevoir_message(client_socket)

        if etat == 1 and nb_message == 0:
            machines_reçues = json.loads(message_reçu)
            nb_message += 1
            continue

        if etat == 1 and nb_message > 0 and message_reçu != "FIN PHASE 1":
            # Découper le message reçu en mots et extraire uniquement les mots
            mots = re.findall(r'\b\w+\b', message_reçu.lower())
            # Stocker chaque mot sous forme de clé-valeur "mot ; 1" dans le fichier temporaire
            with open(temp_file_path, 'a') as temp_file:
                for mot in mots:
                    temp_file.write(f"{mot} : 1\n")
            print(f"'{nom_machine}' : Messages reçus et stockés dans RAM")
            continue

        if message_reçu == "FIN PHASE 1":
            etat = 2

            # Démarrer le thread pour créer les connexions entre les machines distantes
            thread_accepter_phase2 = threading.Thread(
                target=accepter_connexion_phase2)
            thread_accepter_phase2.start()

            envoyer_message(client_socket, "OK FIN PHASE 1")

            # Créer les connexions à toutes les machines
            for machine in machines_reçues:
                try:
                    # Créer un socket TCP/IP
                    client_socket2 = socket.socket(
                        socket.AF_INET, socket.SOCK_STREAM)

                    # Se connecter à la machine
                    client_socket2.connect((machine, PORT2))

                    # Stocker la connexion
                    connexions_phase_2[machine] = client_socket2
                    print(f"{nom_machine}:Connexion établie avec {machine}")

                except Exception as e:
                    print(f"Erreur lors de la connexion à {machine}: {e}")
            continue

        if message_reçu == "GO PHASE 2":
            # Vider la socket pour s'assurer que les messages de la phase 2 seront bien reçues
            vider_buffer_socket(client_socket2)

            # Créer et démarrer le thread d'envoi des paires clé-valeur
            thread_envoi = threading.Thread(target=envoyer_paires_phase_2, args=(
                client_socket2, machines_reçues, temp_file_path))
            thread_envoi.start()

            # Créer et démarrer le thread de réception des paires clé-valeur
            thread_reception = threading.Thread(
                target=recevoir_paires_phase_2, args=(client_socket2, temp_file_path))
            thread_reception.start()

            envoyer_message(client_socket, "FIN PHASE 2")

            etat = 3
            continue

        if message_reçu == "GO PHASE 3":  # phase de reduce
            print(f"{nom_machine}: Début de la phase 3")
            # Appeler la fonction reduce_phase_3 pour traiter les mots reçus
            reduce_phase_3(temp_file_path)
            print(f"'REDUCE PHASE 3 "
                  f"{nom_machine}' : Calcul des occurrences terminé.")
            envoyer_message(client_socket, "FIN PHASE 3")
            print(f"'PHASE 3 {nom_machine}' : Fin de la phase 3")
            etat = 4
            continue

        # tri local et envoi des quantiles au client
        if message_reçu == ("GO PHASE 4"):
            print(
                f"'{nom_machine}' : Phase 4 de tri démarrée")

            # Déterminer la version la plus récente du fichier de résultats du reduce à trier
            version = 1
            output_path = (
                f"/home/users/adefornel-24/reduce_results_"
                f"{nom_machine}_v{version}.txt"
            )
            while os.path.exists(f"/home/users/adefornel-24/reduce_results_{nom_machine}_v{version}.txt"):
                version += 1
            version -= 1  # La dernière version est celle juste avant que la boucle s'arrête
            output_path = (
                f"/home/users/adefornel-24/reduce_results_"
                f"{nom_machine}_v{version}.txt"
            )
            quantiles = tri_local_et_definir_quantiles(
                output_path, nom_machine, len(machines_reçues))

            # Envoyer les quantiles au client
            envoyer_message(client_socket, "FIN PHASE 4")
            envoyer_message(client_socket, json.dumps(quantiles))
            print(f"'{nom_machine}' : Quantiles envoyés au client")
            etat = 5
            continue

        if message_reçu == ("GO PHASE 5"):  # shuffle 2
            seuils_globaux = []
            try:
                message_reçu_seuils = recevoir_message(client_socket)
                while message_reçu_seuils == "GO PHASE 5":
                    message_reçu_seuils = recevoir_message(client_socket)
                seuils = json.loads(message_reçu_seuils)
                seuils_globaux = seuils['seuils']
                print(f"'{nom_machine}' : Seuils globaux reçus :"
                      f"{seuils_globaux}")
            except json.JSONDecodeError as e:
                print(f"Erreur lors du parsing du message JSON : {e}")

            # Lancer la phase de shuffle n°2 et trier les paires localement
            paires_locales, paires_a_envoyer = shuffle2_sort(nom_machine, machines_reçues,
                                                             output_path, seuils_globaux)

            # Déterminer le chemin du fichier de résultats du shuffle2
            version = 1
            shuffle_path = (
                f"/home/users/adefornel-24/tri_shuffle2_results_"
                f"{nom_machine}_v{version}.txt"
            )
            while os.path.exists(shuffle_path):
                version += 1
                shuffle_path = (
                    f"/home/users/adefornel-24/tri_shuffle2_results_"
                    f"{nom_machine}_v{version}.txt"
                )
            print(f"'{nom_machine}' : Fichier de résultats du shuffle2 créé "
                  f": {shuffle_path}")

            # Écrire les paires locales dans le fichier de résultat
            with open(shuffle_path, 'w') as fichier_sortie:
                for mot, count in paires_locales:
                    fichier_sortie.write(f"{mot} : {count}\n")
            print(
                f"'{nom_machine}' : Paires locales écrites dans le fichier de résultat.")

            # Créer et démarrer le thread d'envoi des paires clé-valeur pour la phase 5
            thread_envoi_phase_5 = threading.Thread(
                target=envoyer_paires_phase_5, args=(paires_a_envoyer,))
            thread_envoi_phase_5.start()

            # Créer et démarrer le thread de réception des paires clé-valeur pour la phase 5
            thread_reception_phase_5 = threading.Thread(
                target=recevoir_paires_phase_5, args=(client_socket2, shuffle_path))
            thread_reception_phase_5.start()

            # Déterminer la version la plus récente du fichier de shuffle
            version = 1
            shuffle_path = (
                f"/home/users/adefornel-24/tri_shuffle2_results_"
                f"{nom_machine}_v{version}.txt"
            )
            while os.path.exists(f"/home/users/adefornel-24/tri_shuffle2_results_{nom_machine}_v{version}.txt"):
                version += 1
            version -= 1
            shuffle_path = (
                f"/home/users/adefornel-24/tri_shuffle2_results_"
                f"{nom_machine}_v{version}.txt"
            )

            print(f"'{nom_machine}' : Début du tri final")
            trier_paires_localement(nom_machine, shuffle_path)

            envoyer_message(client_socket, "FIN PHASE 5")
            print(f"'{nom_machine}' : Fin phase 5. Message envoyé au client.")

        if message_reçu == ("GO PHASE 6"):  # envoi des résultats au client
            # Envoyer les résultats du reduce au client :
            envoyer_resultat_au_client(client_socket, nom_machine)
            etat = 6
            break


def choisir_machine_pour_mot(paire, machines_reçues):
    # Extraire le mot de la paire clé-valeur pour l'utiliser dans le partitionnement
    mot = paire.split(" : ")[0].strip()
    # Utiliser une fonction de partitionnement déterministe pour choisir une machine basée sur le mot
    partition_index = hash(mot) % len(machines_reçues)
    return machines_reçues[partition_index]


def envoyer_paires_phase_2(client_socket2, machines_reçues, temp_file_path):
    print(f"'{nom_machine}' : Début de l'envoi des paires clé-valeur pour la phase 2.")

    # Lire les mots du fichier temporaire et les redistribuer selon la logique de hash
    lignes_a_conserver = []
    with open(temp_file_path, 'r') as temp_file:
        for line in temp_file:
            try:
                mot, valeur = line.strip().split(" : ")
                machine_destinataire = choisir_machine_pour_mot(
                    mot, machines_reçues)

                if machine_destinataire == nom_machine:
                    # Garder la paire clé-valeur si elle doit rester sur cette machine
                    lignes_a_conserver.append(line.strip())
                else:
                    # Envoyer la paire clé-valeur à la machine destinataire
                    envoyer_message(connexions_phase_2[machine_destinataire],
                                    f"{mot} : {valeur}")
            except ValueError:
                # Ignorer les lignes mal formatées
                continue

    # Réécrire le fichier temporaire en ne gardant que les paires qui doivent rester sur cette machine
    with open(temp_file_path, 'w') as temp_file:
        for ligne in lignes_a_conserver:
            temp_file.write(f"{ligne}\n")
    print(f"'{nom_machine}' : fichiers temporaires mis à jour")


def recevoir_paires_phase_2(client_socket2, temp_file_path):
    print(f"'{nom_machine}' : Début de la réception des paires clé-valeur des autres machines pour la phase 2.")

    try:
        message_reçu = recevoir_message(client_socket2)
        if message_reçu:
            # Vérifier si le message est bien une paire "mot : occurrence"
            if re.match(r'^.+: \d+$', message_reçu):
                # Extraire le mot et sa valeur et ajouter au fichier temporaire
                with open(temp_file_path, 'a') as temp_file:
                    temp_file.write(f"{message_reçu}\n")
            else:
                print(f"Message mal formaté reçu: '{message_reçu}'")
    except Exception as e:
        print(
            f"Erreur lors de la réception des mots pendant la phase 2 : {e}")


# Fonction pour gérer la phase 3 de reduce
def reduce_phase_3(temp_file_path):
    print(f"'REDUCE PHASE 3 {nom_machine}' : Calcul des occurrences des mots")
    with open(temp_file_path, 'r') as temp_file:
        for line in temp_file:
            mot, count = line.strip().split(" : ")
            count = int(count)
            if mot in occurrences:
                occurrences[mot] += count
            else:
                occurrences[mot] = count

    # Déterminer le chemin du fichier de résultats
    version = 1
    output_path = (
        f"/home/users/adefornel-24/reduce_results_"
        f"{nom_machine}_v{version}.txt"
    )
    while os.path.exists(output_path):
        version += 1
        output_path = (
            f"/home/users/adefornel-24/reduce_results_"
            f"{nom_machine}_v{version}.txt"
        )
    # Créer le fichier de résultats et y écrire les occurrences
    with open(output_path, 'w') as output_file:
        for mot, count in occurrences.items():
            output_file.write(f"{mot} : {count}\n")
    print(f"Résultats du reduce stockés dans {output_path}")


# Étape de tri local des résultats du reduce et définition des quantiles
def tri_local_et_definir_quantiles(output_path, nom_machine, X):

    paires = []
    with open(output_path, 'r') as fichier_resultat:
        for line in fichier_resultat:
            if ':' not in line:
                continue
            try:
                mot, count = line.strip().split(' : ')
                count = int(count)
                paires.append((mot, count))
            except ValueError as e:
                print(f"Erreur lors du parsing de la ligne: "
                      f"'{line.strip()}'. Détails: {e}")
                continue

    # Tri des paires localement
    paires.sort(key=lambda x: x[1])
    print(f"'{nom_machine}' : Tri local des résultats du reduce terminé.")

    # Définir les quantiles 33% et 66%
    taille = len(paires)
    quantiles = []

    if taille > 0:
        for i in range(1, X):
            quantile_index = (i * taille) // X
            quantiles.append(paires[quantile_index][1])
    else:
        quantiles = [0] * (X - 1)

    print(f"'{nom_machine}' : Quantiles définis : {quantiles}")
    return quantiles


# Fonction pour le shuffle n°2
def shuffle2_sort(nom_machine, machines_reçues, output_path, seuils_globaux):

    # Lire les paires depuis le fichier de résultat du reduce
    paires = []
    with open(output_path, 'r') as fichier:
        for line in fichier:
            if ':' not in line:
                continue
            try:
                mot, count = line.strip().split(' : ')
                count = int(count)
                paires.append((mot, count))
            except ValueError:
                print(f"Erreur lors du parsing de la ligne: "
                      f"'{line.strip()}'")
                continue
    print(f"'{nom_machine}' : Paires lues depuis le fichier de résultats du reduce.")

    paires_locales = []  # Paires à garder localement
    paires_a_envoyer = {machine: [] for machine in machines_reçues}
    occurrence_machines = defaultdict(list)

    # Déterminer les machines responsables de chaque quantile
    for i, seuil in enumerate(seuils_globaux):
        occurrence_machines[seuil].append(machines_reçues[i])

    # Répartir les paires en fonction des seuils globaux et gérer les cas d'égalité
    compteur_distribution = defaultdict(int)

    for mot, count in paires:
        machine_destinataire = None

        # Vérifier à quel intervalle appartient la valeur `count`
        for i, seuil in enumerate(seuils_globaux):
            if count <= seuil:
                # Répartition équitable si plusieurs machines gèrent le même seuil
                machines_responsables = occurrence_machines[seuil]
                index_machine = compteur_distribution[seuil] % len(
                    machines_responsables)
                machine_destinataire = machines_responsables[index_machine]
                compteur_distribution[seuil] += 1
                break

        # Si aucune machine n'a été déterminée, attribuer la paire à la dernière machine
        if machine_destinataire is None:
            machine_destinataire = machines_reçues[-1]

        # Ajouter la paire à la bonne machine
        if nom_machine == machine_destinataire:
            paires_locales.append((mot, count))
        else:
            paires_a_envoyer[machine_destinataire].append((mot, count))

    print(
        f"'{nom_machine}' : Paires triées selon les seuils et réparties équitablement.")
    return paires_locales, paires_a_envoyer


# Fonction d'envoi des paires pour la phase 5 (shuffle n°2)
def envoyer_paires_phase_5(paires_a_envoyer):
    print(f"'{nom_machine}' : Début de l'envoi des paires clé-valeur pour la phase 5.")

    # Envoyer les paires à chaque machine destinataire
    for machine, paires in paires_a_envoyer.items():
        for mot, count in paires:
            envoyer_message(connexions_phase_2[machine],
                            f"{mot} : {count}")


# Fonction de réception des paires pour la phase 5 (shuffle n°2)
def recevoir_paires_phase_5(client_socket2, shuffle_path):
    print(f"'{nom_machine}' : Début de la réception des paires clé-valeur des autres machines pour la phase 5.")

    with open(shuffle_path, 'a') as fichier_sortie:
        try:
            # Recevoir un message de la socket client_socket2
            message_reçu = recevoir_message(client_socket2)
            if not message_reçu:
                print(f"Pas de message reçu de {client_socket2}")
            # Vérifier si le message est bien une paire "mot : occurrence"
            elif re.match(r'^.+: \d+$', message_reçu):
                # Écrire directement la paire dans le fichier de résultat
                fichier_sortie.write(f"{message_reçu}\n")
                # print(f"'{nom_machine}' : Mot reçu et écrit dans le fichier : {message_reçu}")
            else:
                print(f"Message mal formaté reçu: '{message_reçu}'")

        except Exception as e:
            print(
                f"Erreur lors de la réception des mots pendant la phase 5 : {e}")


# Fonction de tri local des paires pour la phase 5 (shuffle n°2)
def trier_paires_localement(nom_machine, shuffle_path):
    # Lire les paires du fichier
    paires = []
    with open(shuffle_path, 'r') as fichier:
        for line in fichier:
            try:
                mot, valeur = line.strip().split(" : ")
                valeur = int(valeur)
                paires.append((mot, valeur))
            except ValueError as e:
                print(f"Erreur lors du parsing de la ligne: "
                      f"'{line.strip()}'. Détails: {e}")
                continue

    # Trier les paires : d'abord par occurrence croissante, puis par ordre alphabétique
    paires_triées = sorted(paires, key=lambda x: (x[1], x[0]))

    # Écrire les paires triées dans le fichier (ou un nouveau fichier si nécessaire)
    with open(shuffle_path, 'w') as fichier:
        for mot, valeur in paires_triées:
            fichier.write(f"{mot} : {valeur}\n")

    print(f"'{nom_machine}' : Tri local terminé et paires écrites dans "
          f"'{shuffle_path}'.")


def envoyer_resultat_au_client(client_socket, nom_machine):
    # Attendre un message "GO" du client pour commencer l'envoi et synchroniser les envois dans le bon ordre
    signal = client_socket.recv(2)
    if signal != b"GO":
        print(f"'{nom_machine}' : Signal de départ non reçu, envoi annulé.")
        return
    # Déterminer la version la plus récente du fichier de shuffle
    version = 1
    shuffle_path = (
        f"/home/users/adefornel-24/tri_shuffle2_results_"
        f"{nom_machine}_v{version}.txt"
    )
    while os.path.exists(shuffle_path):
        version += 1
        shuffle_path = (
            f"/home/users/adefornel-24/tri_shuffle2_results_"
            f"{nom_machine}_v{version}.txt"
        )
    version -= 1
    shuffle_path = (
        f"/home/users/adefornel-24/tri_shuffle2_results_"
        f"{nom_machine}_v{version}.txt"
    )

    print(f"'{nom_machine}' : Envoi des résultats triés au client depuis "
          f"'{shuffle_path}'.")

    # Lire le contenu du fichier résultat et l'envoyer au client
    try:
        with open(shuffle_path, 'r') as fichier:
            resultat = fichier.read()

        # Utiliser la fonction envoyer_message pour envoyer les données
        envoyer_message(client_socket, resultat)
        print(f"'{nom_machine}' : Résultat final trié envoyé au client.")

        # Attendre le signal de fin du client pour fermer le serveur
        signal_fin = client_socket.recv(3)  # Attendre un signal "FIN"
        if signal_fin == b"FIN":
            print(
                f"'{nom_machine}' : Signal de fin reçu du client. Fermeture du serveur.")
            fermer_serveur(client_socket, serveur_socket, nom_machine)

    except Exception as e:
        print(f"Erreur lors de l'envoi du fichier au client : {e}")


def accepter_connexion_phase1():
    # Accepter une nouvelle connexion
    client_socket, adresse_client = serveur_socket.accept()
    # Créer un thread pour gérer la connexion
    thread_connexion = threading.Thread(
        target=gerer_connexion, args=(client_socket, adresse_client))
    thread_connexion.start()


def accepter_connexion_phase2():
    while True:
        # Accepter une nouvelle connexion
        print(f"'PHASE 2 {nom_machine}' : En attente de connexion...")
        client_socket2, adresse_client = serveur_socket2.accept()
        print(f"'PHASE 2 {nom_machine}' : Connexion acceptée de "
              f"{adresse_client}")
        # Stocker la connexion acceptée dans le dictionnaire
        connexions_phase_2[adresse_client] = client_socket2
        print(f"'{nom_machine}' : Connexion enregistrée pour {adresse_client}")


def fermer_serveur(client_socket, serveur_socket, nom_machine):
    try:
        # Fermer la connexion client
        client_socket.close()
        print(f"'{nom_machine}' : Connexion client fermée.")

        # Fermer la socket du serveur si elle est encore ouverte
        if serveur_socket:
            serveur_socket.close()
            print(f"'{nom_machine}' : Socket serveur fermée.")
    except Exception as e:
        print(f"Erreur lors de la fermeture du serveur : {e}")

    # Quitter le programme proprement
    sys.exit(0)


# Créer et démarrer le thread pour accepter les connexions
thread_accepter = threading.Thread(target=accepter_connexion_phase1)
thread_accepter.start()

# Attendre que les threads se terminent (ce qui n'arrivera probablement jamais)
thread_accepter.join()
