import os

project_name = 'VIZIER'

env_vars = [
	'BASE_URL',
	'FLASK_DEBUG',
	'FIREBASE_AUTH_TOKEN_PATH',	
	'FIREBASE_URL',
	'PRODUCTION',
	'POSTGRES_CONNECTION_STRING'	
]

for env_var in env_vars:	
	vars()[env_var] = os.environ[project_name+'_'+env_var]
