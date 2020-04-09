rm source/core/*
sphinx-apidoc -T -e -o source/core ../nebula

# Remove nebula. and modules strings
find source/core -mindepth 1 -type f -exec sed -i '1 s/nebula\.//g' {} \;
find source/core -mindepth 1 -type f -exec sed -i 's/\ module//g' {} \;

# Remove classes we shouldn't document
#list="obs attribute context_manager dds rx_tx"
#for val in $list; do
#    echo $val
#    sed -i "/$val/d" source/devices/adi.rst
#    rm source/devices/adi.${val}.rst
#done

# Remove extra text
sed -i '/Module.*/q' source/core/nebula.rst
sed -i '/Module/d' source/core/nebula.rst

sed -i 's/nebula\ package/Components/' source/core/nebula.rst
sed -i 's/Submodules//' source/core/nebula.rst
sed -i 's/----------//' source/core/nebula.rst
sed -i 's/===========/=================/' source/core/nebula.rst
mv source/core/nebula.rst source/core/index.rst

make html
