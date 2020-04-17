sudo mv /usr/bin/nm /usr/bin/nm-backup
sudo ln -s /usr/local/bin/llvm-nm /usr/bin/nm
sudo mv /usr/bin/x86_64-linux-gnu-ar /usr/bin/x86_64-linux-gnu-ar-backup
sudo ln -s /usr/local/bin/llvm-ar /usr/bin/x86_64-linux-gnu-ar
sudo mv /usr/bin/x86_64-linux-gnu-gcc /usr/bin/x86_64-linux-gnu-gcc-backup
sudo ln -s /usr/local/bin/clang-scfi /usr/bin/x86_64-linux-gnu-gcc
sudo mv /usr/bin/x86_64-linux-gnu-ranlib /usr/bin/x86_64-linux-gnu-ranlib-backup
sudo ln -s /bin/true /usr/bin/x86_64-linux-gnu-ranlib