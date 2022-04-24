# variables
cdt=$(date +'%Y-%m-%dT%H:%M:%S')

# path
path='/home/marxcerqueira/repos/Kaggle-HighValue-Custormers-Identification'
path_to_papermill='/home/marxcerqueira/.local/bin/'

# papermill command
$path_to_papermill/papermill $path/src/models/c9.1-mc-deploy02.ipynb $path/reports/c9.1-mc-deploy02-$cdt.ipynb



