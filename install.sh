
# 
# Usage: ./install.sh [repo_url]  [repo_sub_folder] [local_target_folder]
#
# ./install.sh "http://github.com/mrjefflarry/ha_coap_service" "./custom_components/ha_coap_service" "/custom_components/ha_coap_service"
#

rurl="$1" localdir="$2" && shift 2

mkdir -p "$localdir"
cd "$localdir"

git init
git remote add -f origin "$rurl"

git config core.sparseCheckout true

# Loops over remaining args
for i; do
    echo "$i" >> .git/info/sparse-checkout
done

git pull origin master

