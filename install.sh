
#
# Usage: ./install.sh [repo_url]  [repo_sub_folder] [local_target_folder]
#
# ./install.sh "https://github.com/mrjefflarry/ha_coap_service" "./custom_components/coap_server" "./coap_server"
#

#
#
localdir="./coap_server"
component="custom_components/coap_server"
#rurl="$1" localdir="$2" && shift 2

mkdir -p "$localdir"
#mkdir -p "$component"
cd "$localdir"

git init
git remote add -f origin "https://github.com/mrjefflarry/ha_coap_service"

git config core.sparseCheckout true

# Loops over remaining args
#for i; do
echo "/custom_components/coap_server/*" >> .git/info/sparse-checkout
#done

ln -s "/root/config/coap_server/custom_components/coap_server" "/root/config/custom_components/coap_server"

git pull origin main
