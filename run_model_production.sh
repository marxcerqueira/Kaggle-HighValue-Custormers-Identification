# variables
cdt=$(date +'%Y-%m-%dT%H:%M:%S')

# path
path='/home/ubuntu/Kaggle-HighValue-Custormers-Identification'
path_to_papermill='/home/ubuntu/.pyenv/versions/HighValue-Customers-Identification/bin'

# papermill command
$path_to_papermill/papermill $path/src/models/c9.1-mc-deploy.ipynb $path/reports/c9.1-mc-deploy-$cdt.ipynb


