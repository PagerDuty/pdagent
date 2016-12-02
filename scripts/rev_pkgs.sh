echo '!!!! REMOVING PACKAGES !!!!'
scripts/rm_pkgs.sh
echo '!!!! BUILDING PACKAGES !!!!'
scons local-repo gpg-home=build-linux/gnupg
