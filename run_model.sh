# variables
cdt=$(date +'%Y-%m-%dT%H:%M:%S')

# path
path='/home/marxcerqueira/repos/Kaggle-HighValue-Custormers-Identification'
path_to_papermill='/home/marxcerqueira/.local/bin/'

# papermill command
$path_to_papermill/papermill $path/src/models/c9.0-mc-deploy.ipynb $path/reports/c9.0-mc-deploy-$cdt.ipynb



