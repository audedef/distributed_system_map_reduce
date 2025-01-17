#!/bin/bash

# Variables - NEW

remote_machine="tp-1a201-30"
remote_user="adefornel-24"
remote_path="/home/users/adefornel-24"
local_path="."

login="adefornel-24"
localFolder="./"
todeploy="dossierAdeployer"
remoteFolder="adefornel"
nameOfTheScript="serveurs.py"

# Copier les fichiers .warc.wet depuis la machine distante vers le client uniquement s'ils n'existent pas localement
for fichier in $(ssh "$remote_user@$remote_machine" "ls $remote_path/*.warc.wet"); do
  nom_fichier=$(basename "$fichier")
  if [ ! -f "$local_path/$nom_fichier" ]; then
    scp "$remote_user@$remote_machine:$fichier" "$local_path"
  else
    echo "$nom_fichier déjà présent, copie ignorée."
  fi
done

#create a machines.txt file with the list of computers
computers=($(cat machines.txt))

# Définir la commande ssh pour exécuter la commande à distance
command1=("ssh" "-tt" "$login@${computers[0]}" "rm -rf $remoteFolder; mkdir $remoteFolder;wait;")

# Exécuter la commande ssh sur la première machine
echo ${command1[*]}
"${command1[@]}";wait;

command2=("scp" "-r" "$localFolder$todeploy" "$login@${computers[0]}:$remoteFolder")
echo ${command2[*]}
"${command2[@]}";wait;

for c in ${computers[@]}; do
  #this command goes to the remote folder, waits 3 seconds and executes script
  command3=("ssh" "-tt" "$login@$c" "cd $remoteFolder/$todeploy; python3 $nameOfTheScript; wait;")

  echo ${command3[*]}
  "${command3[@]}" &
done